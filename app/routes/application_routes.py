from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.errors.custom_errors import ApplicationError
from app.models.application import Application, ApplicationStatus
from app.models.score_breakdown import ApplicationScoreBreakdown
from app.schemas.application_schema import (
	ApplicationCreateRequest,
	ApplicationResponse,
	BulkApplicationItemRequest,
	BulkApplicationItemResult,
	BulkApplicationResponse,
	ErrorResponse,
	ScoreBreakdownResponse,
)
from app.services.duplicate_service import DuplicateService
from app.services.score_engine import ScoreEngine
from app.services.state_machine import transition

router = APIRouter(prefix="/applications", tags=["applications"])


def _build_response(app_obj: Application, breakdown: ApplicationScoreBreakdown) -> ApplicationResponse:
	return ApplicationResponse(
		id=app_obj.id,
		applicant_name=app_obj.applicant_name,
		email=app_obj.email,
		loan_amount=app_obj.loan_amount,
		approved_amount=app_obj.approved_amount,
		stated_monthly_income=app_obj.stated_monthly_income,
		employment_status=app_obj.employment_status,
		documented_monthly_income=app_obj.documented_monthly_income,
		bank_ending_balance=app_obj.bank_ending_balance,
		bank_has_overdrafts=app_obj.bank_has_overdrafts,
		bank_has_consistent_deposits=app_obj.bank_has_consistent_deposits,
		monthly_withdrawals=app_obj.monthly_withdrawals,
		monthly_deposits=app_obj.monthly_deposits,
		score_total=app_obj.score_total,
		score_version=app_obj.score_version,
		status=app_obj.status.value,
		final_decision=app_obj.final_decision.value if app_obj.final_decision else None,
		admin_review_note=app_obj.admin_review_note,
		retry_count=app_obj.retry_count,
		last_retry_at=app_obj.last_retry_at,
		created_at=app_obj.created_at,
		updated_at=app_obj.updated_at,
		score_breakdown=ScoreBreakdownResponse(
			income_verification_score=breakdown.income_verification_score,
			income_level_score=breakdown.income_level_score,
			account_stability_score=breakdown.account_stability_score,
			employment_status_score=breakdown.employment_status_score,
			debt_to_income_score=breakdown.debt_to_income_score,
			total_score=breakdown.total_score,
			score_version=breakdown.score_version,
			weights_snapshot=breakdown.weights_snapshot,
			thresholds_snapshot=breakdown.thresholds_snapshot,
			income_tolerance_snapshot=breakdown.income_tolerance_snapshot,
		),
	)


@router.post("", response_model=ApplicationResponse, status_code=201)
def submit_application(payload: ApplicationCreateRequest, db: Session = Depends(get_db)) -> ApplicationResponse:
	return _submit_application_internal(payload, db)


def _submit_application_internal(payload: ApplicationCreateRequest, db: Session) -> ApplicationResponse:
	duplicate_service = DuplicateService()
	duplicate_service.ensure_not_duplicate(db, email=str(payload.email), loan_amount=payload.loan_amount)

	app_obj = Application(
		applicant_name=payload.applicant_name,
		email=str(payload.email),
		loan_amount=payload.loan_amount,
		stated_monthly_income=payload.stated_monthly_income,
		employment_status=payload.employment_status,
		documented_monthly_income=(payload.documented_monthly_income if payload.documented_monthly_income is not None else 0.0),
		bank_ending_balance=(payload.bank_ending_balance if payload.bank_ending_balance is not None else 0.0),
		bank_has_overdrafts=(payload.bank_has_overdrafts if payload.bank_has_overdrafts is not None else False),
		bank_has_consistent_deposits=(
			payload.bank_has_consistent_deposits if payload.bank_has_consistent_deposits is not None else False
		),
		monthly_withdrawals=(payload.monthly_withdrawals if payload.monthly_withdrawals is not None else 0.0),
		monthly_deposits=(payload.monthly_deposits if payload.monthly_deposits is not None else 0.0),
		status=ApplicationStatus.submitted,
	)

	# Enforced transitions: submitted -> processing -> decision
	app_obj.status = transition(app_obj.status, ApplicationStatus.processing)

	score_engine = ScoreEngine()
	score_result = score_engine.score_application(
		loan_amount=payload.loan_amount,
		stated_monthly_income=payload.stated_monthly_income,
		employment_status=payload.employment_status,
		documented_monthly_income=payload.documented_monthly_income,
		bank_ending_balance=payload.bank_ending_balance,
		bank_has_overdrafts=payload.bank_has_overdrafts,
		bank_has_consistent_deposits=payload.bank_has_consistent_deposits,
		monthly_withdrawals=payload.monthly_withdrawals,
		monthly_deposits=payload.monthly_deposits,
	)

	decision_status = ApplicationStatus(score_result.decision)
	app_obj.status = transition(app_obj.status, decision_status)
	if app_obj.status in {ApplicationStatus.approved, ApplicationStatus.partially_approved}:
		app_obj.status = transition(app_obj.status, ApplicationStatus.disbursement_queued)
	app_obj.score_total = score_result.total_score

	db.add(app_obj)
	db.flush()

	settings = get_settings()
	breakdown = ApplicationScoreBreakdown(
		application_id=app_obj.id,
		income_verification_score=score_result.income_verification_score,
		income_level_score=score_result.income_level_score,
		account_stability_score=score_result.account_stability_score,
		employment_status_score=score_result.employment_status_score,
		debt_to_income_score=score_result.debt_to_income_score,
		total_score=score_result.total_score,
		score_version=app_obj.score_version,
		weights_snapshot={
			"income_verification_weight": settings.scoring.income_verification_weight,
			"income_level_weight": settings.scoring.income_level_weight,
			"account_stability_weight": settings.scoring.account_stability_weight,
			"employment_status_weight": settings.scoring.employment_status_weight,
			"debt_to_income_weight": settings.scoring.debt_to_income_weight,
		},
		thresholds_snapshot={
			"auto_approve": settings.thresholds.auto_approve,
			"manual_review": settings.thresholds.manual_review,
		},
		income_tolerance_snapshot=settings.income_tolerance,
	)
	db.add(breakdown)
	db.commit()
	db.refresh(app_obj)
	db.refresh(breakdown)

	return _build_response(app_obj, breakdown)


@router.post("/bulk", response_model=BulkApplicationResponse, status_code=201)
def submit_applications_bulk(
	payload: list[BulkApplicationItemRequest],
	db: Session = Depends(get_db),
) -> BulkApplicationResponse:
	results: list[BulkApplicationItemResult] = []

	for item in payload:
		try:
			application = _submit_application_internal(item.input, db)
			results.append(
				BulkApplicationItemResult(
					scenario=item.scenario,
					success=True,
					application=application,
				)
			)
		except ApplicationError as exc:
			db.rollback()
			results.append(
				BulkApplicationItemResult(
					scenario=item.scenario,
					success=False,
					error=ErrorResponse(
						error_code=exc.error_code,
						message=exc.message,
						details=exc.details,
					),
				)
			)
		except Exception as exc:  # noqa: BLE001
			db.rollback()
			results.append(
				BulkApplicationItemResult(
					scenario=item.scenario,
					success=False,
					error=ErrorResponse(
						error_code="bulk_item_processing_error",
						message="Unexpected error while processing bulk item.",
						details={"error": str(exc)},
					),
				)
			)

	success_count = sum(1 for result in results if result.success)
	failure_count = len(results) - success_count

	return BulkApplicationResponse(
		total_items=len(results),
		success_count=success_count,
		failure_count=failure_count,
		results=results,
	)
