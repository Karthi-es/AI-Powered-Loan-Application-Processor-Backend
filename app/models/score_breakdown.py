from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ApplicationScoreBreakdown(Base):
    __tablename__ = "application_score_breakdowns"
    __table_args__ = (
        UniqueConstraint("application_id", "score_version", name="uq_score_breakdown_app_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )

    income_verification_score: Mapped[float] = mapped_column(Float, nullable=False)
    income_level_score: Mapped[float] = mapped_column(Float, nullable=False)
    account_stability_score: Mapped[float] = mapped_column(Float, nullable=False)
    employment_status_score: Mapped[float] = mapped_column(Float, nullable=False)
    debt_to_income_score: Mapped[float] = mapped_column(Float, nullable=False)

    total_score: Mapped[float] = mapped_column(Float, nullable=False)
    score_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    weights_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    thresholds_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    income_tolerance_snapshot: Mapped[float] = mapped_column(Float, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
