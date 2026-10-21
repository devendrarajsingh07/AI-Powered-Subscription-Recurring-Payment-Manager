"""Atomic PostgreSQL fixed windows shared by API instances; never trust forwarded IP headers."""

import uuid
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import case, delete, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.account_security import digest
from app.config import get_settings
from app.db import get_engine
from app.models import RateLimitBucket


class AuthLimiter:
    def __init__(self, engine=None):
        self.engine = engine

    def clear(self):
        """Test harness reset, never exposed through HTTP or available in production."""
        if get_settings().environment == "production":
            raise RuntimeError("Production limits cannot be cleared")
        with Session(self.engine or get_engine()) as db, db.begin():
            db.execute(delete(RateLimitBucket))

    def check(self, request, action):
        cfg = get_settings()
        maximum = cfg.auth_register_limit if action == "register" else cfg.auth_login_limit
        if action in ("csrf", "refresh"):
            maximum = cfg.auth_session_limit
        window = cfg.auth_window_seconds
        peer = request.client.host if request.client else "unknown"
        key = digest(action + "\0" + peer, "rate-limit")
        expired = RateLimitBucket.expires_at <= func.now()
        expiry = func.now() + timedelta(seconds=window)
        statement = (
            insert(RateLimitBucket)
            .values(
                id=uuid.uuid4(),
                key_digest=key,
                count=1,
                expires_at=expiry,
            )
            .on_conflict_do_update(
                index_elements=[RateLimitBucket.key_digest],
                set_={
                    "count": case(
                        (expired, 1), else_=func.least(RateLimitBucket.count + 1, maximum + 1)
                    ),
                    "expires_at": case((expired, expiry), else_=RateLimitBucket.expires_at),
                },
            )
            .returning(RateLimitBucket.count)
        )
        try:
            with Session(self.engine or get_engine()) as db, db.begin():
                # Bounded retention for anonymous address buckets, without a process-local janitor.
                db.execute(delete(RateLimitBucket).where(RateLimitBucket.expires_at < func.now()))
                count = db.scalar(statement)
        except SQLAlchemyError:
            raise HTTPException(
                503, {"code": "limiter_unavailable", "message": "Please try again shortly"}
            ) from None
        if count > maximum:
            raise HTTPException(
                429,
                {"code": "rate_limited", "message": "Try again later"},
                headers={"Retry-After": str(window)},
            )
