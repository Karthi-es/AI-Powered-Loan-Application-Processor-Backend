from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DisbursementWebhookRequest(BaseModel):
	application_id: str = Field(min_length=1)
	status: str = Field(pattern="^(success|failed)$")
	transaction_id: str = Field(min_length=1, max_length=128)
	timestamp: datetime


class DisbursementWebhookResponse(BaseModel):
	application_id: str
	transaction_id: str
	status: str
	idempotent_replay: bool = False
	message: str
