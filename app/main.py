from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.database import Base, engine
from app.errors.custom_errors import ApplicationError

# Import models so SQLAlchemy metadata is populated before create_all.
from app.models import application as _application_model  # noqa: F401
from app.models import audit as _audit_model  # noqa: F401
from app.models import disbursement_event as _disbursement_event_model  # noqa: F401
from app.models import score_breakdown as _score_breakdown_model  # noqa: F401
from app.routes.admin_routes import router as admin_router
from app.routes.application_routes import router as application_router
from app.routes.webhook_routes import router as webhook_router

app = FastAPI(title="AI-Powered Loan Application Processor Backend")

#Global exception handling
@app.exception_handler(ApplicationError)
def handle_application_error(_, exc: ApplicationError) -> JSONResponse:
	return JSONResponse(
		status_code=exc.http_status,
		content={
			"error_code": exc.error_code,
			"message": exc.message,
			"details": exc.details,
		},
	)


@app.on_event("startup")
def on_startup() -> None:
	Base.metadata.create_all(bind=engine)


@app.get("/health")
def health() -> dict[str, str]:
	return {"status": "ok"}


app.include_router(application_router)
app.include_router(admin_router)
app.include_router(webhook_router)
