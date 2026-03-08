from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.webhook_schema import DisbursementWebhookRequest, DisbursementWebhookResponse
from app.services.disbursement_service import DisbursementService

router = APIRouter(prefix="/webhook", tags=["webhook"])


@router.post("/disbursement", response_model=DisbursementWebhookResponse)
def disbursement_webhook(
	payload: DisbursementWebhookRequest,
	db: Session = Depends(get_db),
) -> DisbursementWebhookResponse:
	service = DisbursementService()
	try:
		result = service.process_webhook(
			db,
			application_id=payload.application_id,
			transaction_id=payload.transaction_id,
			status=payload.status,
			provider_timestamp=payload.timestamp,
			raw_payload=payload.model_dump(mode="json"),
		)
	except ValueError as exc:
		raise HTTPException(status_code=404, detail=str(exc)) from exc

	return DisbursementWebhookResponse(
		application_id=result.application_id,
		transaction_id=result.transaction_id,
		status=result.status,
		idempotent_replay=result.idempotent_replay,
		message=result.message,
	)
