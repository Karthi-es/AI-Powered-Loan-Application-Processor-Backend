from __future__ import annotations

from typing import Any


class ApplicationError(Exception):
	"""Base class for domain errors with structured response metadata."""

	def __init__(
		self,
		message: str,
		*,
		error_code: str,
		http_status: int,
		details: dict[str, Any] | None = None,
	) -> None:
		super().__init__(message)
		self.message = message
		self.error_code = error_code
		self.http_status = http_status
		self.details = details or {}


class InvalidStateTransitionError(ApplicationError):
	def __init__(
		self,
		from_status: str,
		to_status: str,
		details: dict[str, Any] | None = None,
	) -> None:
		super().__init__(
			f"Invalid state transition from '{from_status}' to '{to_status}'.",
			error_code="invalid_state_transition",
			http_status=409,
			details={"from_status": from_status, "to_status": to_status, **(details or {})},
		)


class DuplicateApplicationError(ApplicationError):
	def __init__(
		self,
		existing_application_id: str,
		details: dict[str, Any] | None = None,
	) -> None:
		super().__init__(
			"Duplicate application detected within the configured time window.",
			error_code="duplicate_application",
			http_status=409,
			details={"existing_application_id": existing_application_id, **(details or {})},
		)


class WebhookReplayError(ApplicationError):
	def __init__(
		self,
		transaction_id: str,
		details: dict[str, Any] | None = None,
	) -> None:
		super().__init__(
			f"Webhook replay detected for transaction_id '{transaction_id}'.",
			error_code="webhook_replay",
			http_status=200,
			details={"transaction_id": transaction_id, **(details or {})},
		)
