"""Account-keyed exponential backoff for known and unknown emails, shared in PostgreSQL."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.account_security import digest
from app.config import get_settings
from app.models import LoginBackoff


def locked(db, email):
    key = digest(email.strip().lower(), "login-account")
    now = datetime.now(timezone.utc)
    db.execute(
        insert(LoginBackoff)
        .values(id=uuid.uuid4(), key_digest=key, failures=0, expires_at=now + timedelta(days=1))
        .on_conflict_do_nothing(index_elements=[LoginBackoff.key_digest])
    )
    row = db.scalar(select(LoginBackoff).where(LoginBackoff.key_digest == key).with_for_update())
    if row.expires_at <= now:
        row.failures, row.blocked_until = 0, None
    if row.blocked_until and row.blocked_until > now:
        raise HTTPException(
            429,
            {"code": "rate_limited", "message": "Try again later"},
            headers={
                "Retry-After": str(max(1, int((row.blocked_until - now).total_seconds()) + 1))
            },
        )
    return row


def failed(row):
    now = datetime.now(timezone.utc)
    row.failures = min(row.failures + 1, 20)
    row.expires_at = now + timedelta(days=1)
    threshold = get_settings().account_backoff_threshold
    if row.failures >= threshold:
        row.blocked_until = now + timedelta(seconds=min(900, 2 ** (row.failures - threshold)))
