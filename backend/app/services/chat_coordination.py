"""Shared per-user chat budgets and expiring, fenced in-flight leases."""

import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app import models as m
from app import repositories as repo
from app.config import get_settings
from app.db import get_engine


class ChatGate:
    def __init__(self, engine=None):
        self.engine = engine

    def clear(self):
        if get_settings().environment == "production":
            raise RuntimeError("Production chat coordination cannot be cleared")
        # Test-only reset; never available through HTTP/operator runtime paths.
        with Session(self.engine or get_engine()) as db, db.begin():
            db.execute(delete(m.ChatLease))

    def acquire(self, user_id, *, engine=None, db=None, now=None):
        now = now or datetime.now(timezone.utc)
        if db is not None:
            return self._acquire(db, user_id, now)
        with Session(engine or self.engine or get_engine()) as session, session.begin():
            return self._acquire(session, user_id, now)

    def _acquire(self, db, user_id, now):
        cfg = get_settings()
        if repo.get_user(db, user_id, lock=True) is None:
            raise HTTPException(
                401, {"code": "unauthorized", "message": "Account no longer exists"}
            )
        row = db.scalar(select(m.ChatLease).where(m.ChatLease.user_id == user_id).with_for_update())
        day = now.astimezone(ZoneInfo(cfg.app_timezone)).date()
        if row is not None and row.expires_at > now:
            raise HTTPException(429, {"code": "chat_busy", "message": "A chat is already running"})
        if row is None:
            row = repo.create_owned(
                db,
                user_id,
                m.ChatLease,
                claim_token=uuid.uuid4(),
                expires_at=now,
                minute_count=0,
                minute_reset=now,
                daily_count=0,
                daily_day=day,
            )
        if row.minute_reset <= now:
            row.minute_count, row.minute_reset = 0, now + timedelta(seconds=60)
        if row.daily_day != day:
            row.daily_count, row.daily_day = 0, day
        if row.minute_count >= cfg.chat_minute_limit or row.daily_count >= cfg.chat_daily_limit:
            raise HTTPException(429, {"code": "rate_limited", "message": "Try again shortly"})
        row.minute_count += 1
        row.daily_count += 1
        row.claim_token = uuid.uuid4()
        # A killed API releases capacity by expiry; no process-local ownership survives restart.
        row.expires_at = now + timedelta(seconds=cfg.chat_timeout_seconds + 5)
        return row.claim_token

    def release(self, user_id, token, *, engine=None, now=None):
        with Session(engine or self.engine or get_engine()) as db, db.begin():
            db.execute(
                update(m.ChatLease)
                .where(
                    m.ChatLease.user_id == user_id,
                    m.ChatLease.claim_token == token,
                )
                .values(expires_at=now or datetime.now(timezone.utc))
            )

    def is_busy(self, user_id, *, engine=None, now=None):
        with Session(engine or self.engine or get_engine()) as db:
            return (
                db.scalar(
                    select(m.ChatLease.id).where(
                        m.ChatLease.user_id == user_id,
                        m.ChatLease.expires_at > (now or datetime.now(timezone.utc)),
                    )
                )
                is not None
            )
