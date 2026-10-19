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
from app.api import chat as chat_routes  # noqa: F401 - registers routes on the shared router
from app.api.routes import router
from app.config import get_settings
from app.db import get_db, get_engine
from app.middleware import SafetyMiddleware
from app.migrations import database_at_head


@asynccontextmanager
async def lifespan(app):
    if len(get_settings().jwt_secret.get_secret_value()) < 32:
        raise RuntimeError("JWT_SECRET must contain at least 32 characters")
    instance = None
    scheduler = None
    if uploads.get_worker not in app.dependency_overrides:
        instance = uploads.start_worker()
        if get_settings().scheduler_enabled:
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
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(router)


def documented_openapi():
    if app.openapi_schema is None:
        from app import schemas as s

        document = get_openapi(
            title=app.title, version=app.version, routes=app.routes, description=app.description
        )
        for model in (s.ChatFinal, s.ChatStatus, s.ChatStreamError):
            document["components"]["schemas"][model.__name__] = model.model_json_schema()
        document["paths"]["/api/v1/chat"]["post"]["x-sse-events"] = {
            "status": {"$ref": "#/components/schemas/ChatStatus"},
            "final": {"$ref": "#/components/schemas/ChatFinal"},
            "error": {"$ref": "#/components/schemas/ChatStreamError"},
        }
        app.openapi_schema = document
    return app.openapi_schema


app.openapi = documented_openapi


class Health(BaseModel):
    status: str


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
    return Health(status="ok")


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
    return Health(status="ready")
