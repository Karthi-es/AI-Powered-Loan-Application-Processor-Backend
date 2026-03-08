from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.application import ApplicationStatus


class AuditEvent(Base):
	__tablename__ = "audit_events"

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	application_id: Mapped[str] = mapped_column(
		String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
	)

	event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
	from_status: Mapped[ApplicationStatus | None] = mapped_column(
		Enum(ApplicationStatus, native_enum=False), nullable=True
	)
	to_status: Mapped[ApplicationStatus | None] = mapped_column(
		Enum(ApplicationStatus, native_enum=False), nullable=True
	)

	actor: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
	note: Mapped[str | None] = mapped_column(String(1000), nullable=True)

	retry_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
	transaction_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

	event_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
