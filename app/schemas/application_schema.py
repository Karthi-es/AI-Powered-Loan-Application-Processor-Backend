from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class ApplicationCreateRequest(BaseModel):
	applicant_name: str = Field(min_length=1, max_length=255)
	email: EmailStr
	loan_amount: float = Field(gt=0)

	stated_monthly_income: float = Field(ge=0)
	employment_status: str = Field(min_length=1, max_length=32)
	documented_monthly_income: float | None = Field(default=None, ge=0)
	bank_ending_balance: float | None = None
	bank_has_overdrafts: bool | None = None
	bank_has_consistent_deposits: bool | None = None
	monthly_withdrawals: float | None = Field(default=None, ge=0)
	monthly_deposits: float | None = Field(default=None, ge=0)


class ScoreBreakdownResponse(BaseModel):
	income_verification_score: float
	income_level_score: float
	account_stability_score: float
	employment_status_score: float
	debt_to_income_score: float
	total_score: float
	score_version: int

	weights_snapshot: dict[str, Any]
	thresholds_snapshot: dict[str, Any]
	income_tolerance_snapshot: float


class ApplicationResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: str
	applicant_name: str
	email: EmailStr

	loan_amount: float
	approved_amount: float | None = None

	stated_monthly_income: float
	employment_status: str
	documented_monthly_income: float
	bank_ending_balance: float
	bank_has_overdrafts: bool
	bank_has_consistent_deposits: bool
	monthly_withdrawals: float
	monthly_deposits: float

	score_total: float | None = None
	score_version: int
	status: str
	final_decision: str | None = None
	admin_review_note: str | None = None

	retry_count: int
	last_retry_at: datetime | None = None
	created_at: datetime
	updated_at: datetime

	score_breakdown: ScoreBreakdownResponse | None = None


class AdminApplicationFilterQuery(BaseModel):
	status: str | None = None


class AdminReviewRequest(BaseModel):
	decision: str = Field(pattern="^(approve|deny|partially_approve)$")
	note: str = Field(min_length=1, max_length=1000)
	reduced_loan_amount: float | None = Field(default=None, gt=0)

	@model_validator(mode="after")
	def validate_reduced_amount(self) -> "AdminReviewRequest":
		if self.decision == "partially_approve" and self.reduced_loan_amount is None:
			raise ValueError("reduced_loan_amount is required for partially_approve decisions.")
		if self.decision != "partially_approve" and self.reduced_loan_amount is not None:
			raise ValueError("reduced_loan_amount is only valid for partially_approve decisions.")
		return self


class ErrorResponse(BaseModel):
	error_code: str
	message: str
	details: dict[str, Any] = Field(default_factory=dict)


class BulkApplicationItemRequest(BaseModel):
	scenario: int | str
	input: ApplicationCreateRequest


class BulkApplicationItemResult(BaseModel):
	scenario: int | str
	success: bool
	application: ApplicationResponse | None = None
	error: ErrorResponse | None = None


class BulkApplicationResponse(BaseModel):
	total_items: int
	success_count: int
	failure_count: int
	results: list[BulkApplicationItemResult]
