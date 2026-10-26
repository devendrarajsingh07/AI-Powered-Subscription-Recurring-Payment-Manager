import os
import re
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import uploads
from app.api import account as account_routes  # noqa: F401 - registers account routes
from app.api import chat as chat_routes  # noqa: F401 - registers routes on the shared router
from app.api import lifecycle as lifecycle_routes  # noqa: F401 - unsubscribe, events, reports
from app.api import ops as ops_routes  # noqa: F401 - internal token-gated metrics
from app.api import receipts as receipt_routes  # noqa: F401 - offline, opt-in receipt foundation
from app.api.routes import router
from app.config import get_settings
from app.db import get_db, get_engine
from app.middleware import SafetyMiddleware
from app.migrations import database_at_head


@asynccontextmanager
async def lifespan(app):
    if get_settings().environment == "production":
        raise RuntimeError(
            "Private beta launch is blocked: verified email, revocable cookie sessions, "
            "durable workers and operational launch gates are not complete"
        )
    if len(get_settings().jwt_secret.get_secret_value()) < 32:
        raise RuntimeError("JWT_SECRET must contain at least 32 characters")
    if get_settings().public_demo_only:
        from app.services.demo_retention import purge_demo_accounts

        purge_demo_accounts(get_engine())
    instance = None
    scheduler = None
    if uploads.get_worker not in app.dependency_overrides:
        instance = uploads.start_worker()
        # With durable jobs the separate worker is the single scheduler owner; API replicas
        # never run alert delivery. Inline mode (single-process free demo) keeps its scheduler.
        if get_settings().job_mode != "postgres" and (
            get_settings().scheduler_enabled or get_settings().public_demo_only
        ):
            from app.scheduler import start_scheduler

            scheduler = start_scheduler(get_engine())
    try:
        yield
    finally:
        if scheduler:
            scheduler.shutdown(wait=True)
        if instance:
            instance.close()


app = FastAPI(
    title="SubTrack API",
    version="1.0.0",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
    description="Educational use with uploaded or simulated INR data. "
    "Monetary JSON values are decimal strings. JWT identity scopes every business route.",
)
app.add_middleware(SafetyMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().web_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
)
app.include_router(router)


def documented_openapi():
    if app.openapi_schema is None:
        from app import schemas as s

        document = get_openapi(
            title=app.title, version=app.version, routes=app.routes, description=app.description
        )
        for model in (s.ChatFinal, s.ChatStatus, s.ChatStreamError, s.RowEdit):
            document["components"]["schemas"][model.__name__] = model.model_json_schema()
        document["paths"]["/api/v1/chat"]["post"]["x-sse-events"] = {
            "status": {"$ref": "#/components/schemas/ChatStatus"},
            "final": {"$ref": "#/components/schemas/ChatFinal"},
            "error": {"$ref": "#/components/schemas/ChatStreamError"},
        }
        document["paths"]["/api/v1/uploads"]["post"]["x-review-edits-schema"] = {
            "type": "array",
            "items": {"$ref": "#/components/schemas/RowEdit"},
        }
        app.openapi_schema = document
    return app.openapi_schema


app.openapi = documented_openapi


class Health(BaseModel):
    status: str
    # Deployed source commit (set by the host, e.g. Render's RENDER_GIT_COMMIT). Lets a release
    # pipeline prove the NEW revision is serving, not an old instance that is still healthy.
    revision: str | None = None


def revision():
    value = os.environ.get("RENDER_GIT_COMMIT", "").strip().lower()
    return value if re.fullmatch(r"[0-9a-f]{40}", value) else None


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, _exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "validation_error", "message": "Invalid request data"}},
    )


@app.exception_handler(StarletteHTTPException)
async def http_error(_request, exc):
    detail = (
        exc.detail
        if isinstance(exc.detail, dict)
        else {"code": "http_error", "message": "Request could not be completed"}
    )
    return JSONResponse(status_code=exc.status_code, content={"error": detail}, headers=exc.headers)


@app.get("/api/v1/health", response_model=Health, tags=["health"])
def health():
    """Liveness only; readiness additionally checks PostgreSQL and migration state."""
    return Health(status="ok", revision=revision())


@app.get("/api/v1/health/ready", response_model=Health, tags=["health"])
def ready(db: Session = Depends(get_db)):
    try:
        if not database_at_head(db):
            raise ValueError("Unexpected migration version")
    except (SQLAlchemyError, ValueError):
        return JSONResponse(
            status_code=503,
            content={"error": {"code": "not_ready", "message": "Database is not ready"}},
        )
    return Health(status="ready", revision=revision())
