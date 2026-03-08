from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.application import Application, ApplicationStatus, ReviewDecision
from app.models.audit import AuditEvent
from app.models.score_breakdown import ApplicationScoreBreakdown
from app.schemas.application_schema import AdminReviewRequest, ApplicationResponse, ScoreBreakdownResponse
from app.services.state_machine import transition

router = APIRouter(prefix="/admin", tags=["admin"])
security = HTTPBasic()


def _authenticate_admin(credentials: HTTPBasicCredentials = Depends(security)) -> str:
	settings = get_settings()
	valid_user = secrets.compare_digest(credentials.username, settings.admin.username)
	valid_pass = secrets.compare_digest(credentials.password, settings.admin.password)

	if not (valid_user and valid_pass):
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Invalid admin credentials.",
			headers={"WWW-Authenticate": "Basic"},
		)
	return credentials.username


def _to_response(app_obj: Application, breakdown: ApplicationScoreBreakdown | None = None) -> ApplicationResponse:
	score_breakdown = None
	if breakdown is not None:
		score_breakdown = ScoreBreakdownResponse(
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
		)

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
		score_breakdown=score_breakdown,
	)


@router.get("/applications", response_model=list[ApplicationResponse])
def list_applications(
	status_filter: str | None = Query(default=None, alias="status"),
	_: str = Depends(_authenticate_admin),
	db: Session = Depends(get_db),
) -> list[ApplicationResponse]:
	stmt = select(Application).order_by(Application.created_at.desc())

	if status_filter:
		try:
			enum_status = ApplicationStatus(status_filter)
		except ValueError as exc:
			raise HTTPException(status_code=400, detail=f"Invalid status '{status_filter}'.") from exc
		stmt = stmt.where(Application.status == enum_status)

	applications = db.execute(stmt).scalars().all()
	return [_to_response(application) for application in applications]


@router.get("/applications/{application_id}", response_model=ApplicationResponse)
def get_application_detail(
	application_id: str,
	_: str = Depends(_authenticate_admin),
	db: Session = Depends(get_db),
) -> ApplicationResponse:
	application = db.get(Application, application_id)
	if application is None:
		raise HTTPException(status_code=404, detail="Application not found.")

	breakdown_stmt = (
		select(ApplicationScoreBreakdown)
		.where(ApplicationScoreBreakdown.application_id == application_id)
		.order_by(ApplicationScoreBreakdown.score_version.desc())
		.limit(1)
	)
	breakdown = db.execute(breakdown_stmt).scalars().first()
	return _to_response(application, breakdown)


@router.post("/applications/{application_id}/review", response_model=ApplicationResponse)
def review_application(
	application_id: str,
	payload: AdminReviewRequest,
	admin_username: str = Depends(_authenticate_admin),
	db: Session = Depends(get_db),
) -> ApplicationResponse:
	application = db.get(Application, application_id)
	if application is None:
		raise HTTPException(status_code=404, detail="Application not found.")

	from_status = application.status
	if payload.decision == "approve":
		to_status = ApplicationStatus.approved
		application.final_decision = ReviewDecision.approve
		application.approved_amount = application.loan_amount
	elif payload.decision == "deny":
		to_status = ApplicationStatus.denied
		application.final_decision = ReviewDecision.deny
		application.approved_amount = None
	else:
		#Validation check for partial approval with reduced loan amount
		assert payload.reduced_loan_amount is not None
		if payload.reduced_loan_amount > application.loan_amount:
			raise HTTPException(status_code=400, detail="reduced_loan_amount cannot exceed loan_amount.")
		to_status = ApplicationStatus.partially_approved
		application.final_decision = ReviewDecision.partially_approve
		application.approved_amount = payload.reduced_loan_amount

	application.status = transition(application.status, to_status)
	if application.status in {ApplicationStatus.approved, ApplicationStatus.partially_approved}:
		application.status = transition(application.status, ApplicationStatus.disbursement_queued)
	application.admin_review_note = payload.note

	audit = AuditEvent(
		application_id=application.id,
		event_type="manual_review",
		from_status=from_status,
		to_status=to_status,
		actor=admin_username,
		note=payload.note,
		event_metadata={"decision": payload.decision, "approved_amount": application.approved_amount},
	)
	db.add(audit)

	db.commit()
	db.refresh(application)

	breakdown_stmt = (
		select(ApplicationScoreBreakdown)
		.where(ApplicationScoreBreakdown.application_id == application_id)
		.order_by(ApplicationScoreBreakdown.score_version.desc())
		.limit(1)
	)
	breakdown = db.execute(breakdown_stmt).scalars().first()
	return _to_response(application, breakdown)
