from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db

app = FastAPI(title="SubTrack API", version="0.1.0", openapi_url="/api/v1/openapi.json")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().web_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


class Health(BaseModel):
    status: str


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, _exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "validation_error", "message": "Invalid request data"}},
    )


@app.get("/api/v1/health", response_model=Health, tags=["health"])
def health():
    """Liveness only; readiness additionally checks PostgreSQL and migration state."""
    return Health(status="ok")


@app.get("/api/v1/health/ready", response_model=Health, tags=["health"])
def ready(db: Session = Depends(get_db)):
    try:
        version = db.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        if version != "0001_scaffold":
            raise ValueError("Unexpected migration version")
    except (SQLAlchemyError, ValueError):
        return JSONResponse(
            status_code=503,
            content={"error": {"code": "not_ready", "message": "Database is not ready"}},
        )
    return Health(status="ready")

