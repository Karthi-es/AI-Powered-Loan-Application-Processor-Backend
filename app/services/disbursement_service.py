from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.application import Application, ApplicationStatus
from app.models.audit import AuditEvent
from app.models.disbursement_event import DisbursementEvent, DisbursementWebhookStatus
from app.services.state_machine import transition


@dataclass
class DisbursementWebhookResult:
	application_id: str
	transaction_id: str
	status: str
	idempotent_replay: bool
	message: str


class DisbursementService:
	def __init__(self) -> None:
		self.settings = get_settings()

	def escalate_timed_out_disbursements(self, db: Session) -> int:
		timeout_cutoff = datetime.now(timezone.utc) - timedelta(
			seconds=self.settings.disbursement.webhook_timeout_seconds
		)

		stmt = (
			select(Application)
			.where(Application.status == ApplicationStatus.disbursement_queued)
			.where(Application.updated_at <= timeout_cutoff)
		)
		stale_apps = db.execute(stmt).scalars().all()

		escalated = 0
		for app in stale_apps:
			previous = app.status
			app.status = transition(app.status, ApplicationStatus.flagged_for_review)
			db.add(
				AuditEvent(
					application_id=app.id,
					event_type="webhook_timeout_escalation",
					from_status=previous,
					to_status=ApplicationStatus.flagged_for_review,
					actor="system",
					note="Disbursement webhook not received within timeout window.",
					event_metadata={
						"webhook_timeout_seconds": self.settings.disbursement.webhook_timeout_seconds,
					},
				)
			)
			escalated += 1

		return escalated

	def _append_audit(
		self,
		db: Session,
		*,
		app: Application,
		event_type: str,
		from_status: ApplicationStatus | None,
		to_status: ApplicationStatus | None,
		note: str,
		transaction_id: str,
		retry_id: str | None = None,
		metadata: dict | None = None,
	) -> None:
		db.add(
			AuditEvent(
				application_id=app.id,
				event_type=event_type,
				from_status=from_status,
				to_status=to_status,
				actor="system",
				note=note,
				transaction_id=transaction_id,
				retry_id=retry_id,
				event_metadata=metadata,
			)
		)

	def process_webhook(
		self,
		db: Session,
		*,
		application_id: str,
		transaction_id: str,
		status: str,
		provider_timestamp: datetime,
		raw_payload: dict | None = None,
	) -> DisbursementWebhookResult:
		self.escalate_timed_out_disbursements(db)

		existing = db.execute(
			select(DisbursementEvent).where(DisbursementEvent.transaction_id == transaction_id)
		).scalars().first()
		if existing is not None:
			app = db.get(Application, existing.application_id)
			if app is not None:
				self._append_audit(
					db,
					app=app,
					event_type="webhook_replay_ignored",
					from_status=app.status,
					to_status=app.status,
					note="Webhook replay detected; no state change applied.",
					transaction_id=transaction_id,
					metadata={"existing_event_id": existing.id},
				)
				db.commit()
			return DisbursementWebhookResult(
				application_id=existing.application_id,
				transaction_id=transaction_id,
				status=existing.status.value,
				idempotent_replay=True,
				message="Replay detected. No state change applied.",
			)

		app = db.get(Application, application_id)
		if app is None:
			raise ValueError("Application not found.")

		if app.status == ApplicationStatus.disbursed:
			self._append_audit(
				db,
				app=app,
				event_type="webhook_ignored_already_disbursed",
				from_status=app.status,
				to_status=app.status,
				note="Webhook ignored because application is already disbursed.",
				transaction_id=transaction_id,
			)
			db.commit()
			return DisbursementWebhookResult(
				application_id=application_id,
				transaction_id=transaction_id,
				status="success",
				idempotent_replay=True,
				message="Application already disbursed. No state change applied.",
			)

		incoming_status = DisbursementWebhookStatus(status)
		from_status = app.status

		if app.status in {ApplicationStatus.approved, ApplicationStatus.partially_approved}:
			app.status = transition(app.status, ApplicationStatus.disbursement_queued)
			self._append_audit(
				db,
				app=app,
				event_type="disbursement_queued",
				from_status=from_status,
				to_status=ApplicationStatus.disbursement_queued,
				note="Application queued for disbursement.",
				transaction_id=transaction_id,
			)

		if incoming_status == DisbursementWebhookStatus.success:
			previous = app.status
			app.status = transition(app.status, ApplicationStatus.disbursed)
			self._append_audit(
				db,
				app=app,
				event_type="disbursement_success",
				from_status=previous,
				to_status=ApplicationStatus.disbursed,
				note="Disbursement provider reported success.",
				transaction_id=transaction_id,
			)
			message = "Disbursement marked successful."
		else:
			previous = app.status
			app.status = transition(app.status, ApplicationStatus.disbursement_failed)
			self._append_audit(
				db,
				app=app,
				event_type="disbursement_failed",
				from_status=previous,
				to_status=ApplicationStatus.disbursement_failed,
				note="Disbursement provider reported failure.",
				transaction_id=transaction_id,
			)

			if app.retry_count < self.settings.disbursement.retry_attempts:
				app.retry_count += 1
				app.last_retry_at = datetime.now(timezone.utc)

				retry_id = f"retry_{uuid.uuid4().hex[:12]}"
				retry_from = app.status
				app.status = transition(app.status, ApplicationStatus.disbursement_queued)
				self._append_audit(
					db,
					app=app,
					event_type="disbursement_retry_queued",
					from_status=retry_from,
					to_status=ApplicationStatus.disbursement_queued,
					note="Retry queued after disbursement failure.",
					transaction_id=transaction_id,
					retry_id=retry_id,
					metadata={
						"retry_attempt": app.retry_count,
						"max_retry_attempts": self.settings.disbursement.retry_attempts,
					},
				)
				message = "Disbursement failed; retry queued."
			else:
				fail_from = app.status
				app.status = transition(app.status, ApplicationStatus.flagged_for_review)
				self._append_audit(
					db,
					app=app,
					event_type="disbursement_retry_exhausted",
					from_status=fail_from,
					to_status=ApplicationStatus.flagged_for_review,
					note="Retry attempts exhausted; escalated for manual review.",
					transaction_id=transaction_id,
					metadata={
						"retry_attempt": app.retry_count,
						"max_retry_attempts": self.settings.disbursement.retry_attempts,
					},
				)
				message = "Disbursement failed; retries exhausted and escalated for review."

		event = DisbursementEvent(
			application_id=application_id,
			transaction_id=transaction_id,
			status=incoming_status,
			provider_timestamp=provider_timestamp,
			is_replay=False,
			raw_payload=raw_payload,
		)
		db.add(event)
		db.commit()

		return DisbursementWebhookResult(
			application_id=application_id,
			transaction_id=transaction_id,
			status=incoming_status.value,
			idempotent_replay=False,
			message=message,
		)
