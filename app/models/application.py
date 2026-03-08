from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ApplicationStatus(str, enum.Enum):
	submitted = "submitted"
	processing = "processing"
	approved = "approved"
	denied = "denied"
	flagged_for_review = "flagged_for_review"
	partially_approved = "partially_approved"
	disbursement_queued = "disbursement_queued"
	disbursed = "disbursed"
	disbursement_failed = "disbursement_failed"


class ReviewDecision(str, enum.Enum):
	approve = "approve"
	deny = "deny"
	partially_approve = "partially_approve"


class Application(Base):
	__tablename__ = "applications"

	id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

	applicant_name: Mapped[str] = mapped_column(String(255), nullable=False)
	email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

	loan_amount: Mapped[float] = mapped_column(Float, nullable=False)
	approved_amount: Mapped[float | None] = mapped_column(Float, nullable=True)

	stated_monthly_income: Mapped[float] = mapped_column(Float, nullable=False)
	employment_status: Mapped[str] = mapped_column(String(32), nullable=False)
	documented_monthly_income: Mapped[float] = mapped_column(Float, nullable=False)
	bank_ending_balance: Mapped[float] = mapped_column(Float, nullable=False)
	bank_has_overdrafts: Mapped[bool] = mapped_column(Boolean, nullable=False)
	bank_has_consistent_deposits: Mapped[bool] = mapped_column(Boolean, nullable=False)
	monthly_withdrawals: Mapped[float] = mapped_column(Float, nullable=False)
	monthly_deposits: Mapped[float] = mapped_column(Float, nullable=False)

	score_total: Mapped[float | None] = mapped_column(Float, nullable=True)
	score_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

	status: Mapped[ApplicationStatus] = mapped_column(
		Enum(ApplicationStatus, native_enum=False),
		nullable=False,
		default=ApplicationStatus.submitted,
		index=True,
	)
	final_decision: Mapped[ReviewDecision | None] = mapped_column(
		Enum(ReviewDecision, native_enum=False), nullable=True
	)
	admin_review_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)

	retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
	last_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
	updated_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
	)
