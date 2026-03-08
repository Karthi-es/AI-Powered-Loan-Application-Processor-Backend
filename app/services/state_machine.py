from __future__ import annotations

from app.errors.custom_errors import InvalidStateTransitionError
from app.models.application import ApplicationStatus


ALLOWED_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
	#added flagged_for_review without breaking approved, denied flow
	ApplicationStatus.submitted: {ApplicationStatus.processing},
	ApplicationStatus.processing: {
		ApplicationStatus.approved,
		ApplicationStatus.denied,
		ApplicationStatus.flagged_for_review,
	},
	#added partially_approved scenario as well
	ApplicationStatus.flagged_for_review: {
		ApplicationStatus.approved,
		ApplicationStatus.denied,
		ApplicationStatus.partially_approved,
	},
	#added partialy_approved scenario as first class state with approved status
	ApplicationStatus.approved: {ApplicationStatus.disbursement_queued},
	ApplicationStatus.partially_approved: {ApplicationStatus.disbursement_queued},
	ApplicationStatus.disbursement_queued: {
		ApplicationStatus.disbursed,
		ApplicationStatus.disbursement_failed,
		ApplicationStatus.flagged_for_review,
	},
	ApplicationStatus.disbursement_failed: {
		ApplicationStatus.disbursement_queued,
		ApplicationStatus.flagged_for_review,
	},
	ApplicationStatus.denied: set(),
	ApplicationStatus.disbursed: set(),
}


def can_transition(from_status: ApplicationStatus, to_status: ApplicationStatus) -> bool:
	return to_status in ALLOWED_TRANSITIONS.get(from_status, set())


def validate_transition(from_status: ApplicationStatus, to_status: ApplicationStatus) -> None:
	if from_status == to_status:
		# idempotent self-transition is allowed for safe reprocessing paths.
		return

	if not can_transition(from_status, to_status):
		raise InvalidStateTransitionError(
			from_status=from_status.value,
			to_status=to_status.value,
			details={
				"allowed_next_states": [status.value for status in sorted(ALLOWED_TRANSITIONS.get(from_status, set()), key=lambda x: x.value)],
			},
		)


def transition(from_status: ApplicationStatus, to_status: ApplicationStatus) -> ApplicationStatus:
	validate_transition(from_status, to_status)
	return to_status
