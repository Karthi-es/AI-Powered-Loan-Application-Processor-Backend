from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors.custom_errors import DuplicateApplicationError
from app.models.application import Application


class DuplicateService:
	def __init__(self) -> None:
		self.settings = get_settings()

	def ensure_not_duplicate(self, db: Session, *, email: str, loan_amount: float) -> None:
		window_start = datetime.utcnow() - timedelta(minutes=self.settings.duplicate_window_minutes)

		stmt = (
			select(Application)
			.where(Application.email == email)
			.where(Application.loan_amount == loan_amount)
			.where(Application.created_at >= window_start)
			.order_by(Application.created_at.desc())
			.limit(1)
		)

		existing = db.execute(stmt).scalars().first()
		if existing:
			raise DuplicateApplicationError(existing_application_id=existing.id)
