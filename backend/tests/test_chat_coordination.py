"""Independent clients share PostgreSQL counts and fenced leases; no process-local state."""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from test_durable_queue import owner

from app import models as m
from app import repositories as repo
from app.config import get_settings
from app.services.chat import stream_turn
from app.services.chat_coordination import ChatGate
from app.services.llm.fake import FakeLLM


def test_limits_shared_across_gate_instances_and_scoped_to_owner(db, pg_engine, monkeypatch):
    monkeypatch.setenv("CHAT_MINUTE_LIMIT", "2")
    get_settings.cache_clear()
    first, second = owner(db), owner(db)
    db.commit()
    a, b = ChatGate(pg_engine), ChatGate(pg_engine)
    for gate in (a, b):
        token = gate.acquire(first)
        gate.release(first, token)
    with pytest.raises(HTTPException) as error:
        a.acquire(first)
    assert error.value.status_code == 429 and error.value.detail["code"] == "rate_limited"
    token = b.acquire(second)
    assert a.is_busy(second) and not a.is_busy(first)
    b.release(second, token)


def test_abandoned_api_lease_expires_and_old_release_cannot_unlock_successor(db, pg_engine):
    user_id = owner(db)
    db.commit()
    now = datetime.now(timezone.utc)
    a, b = ChatGate(pg_engine), ChatGate(pg_engine)
    first = a.acquire(user_id, now=now)
    with pytest.raises(HTTPException) as error:
        b.acquire(user_id, now=now)
    assert error.value.detail["code"] == "chat_busy"
    later = now + timedelta(seconds=get_settings().chat_timeout_seconds + 6)
    second = b.acquire(user_id, now=later)
    a.release(user_id, first, now=later)
    assert a.is_busy(user_id, now=later)
    b.release(user_id, second, now=later)
    assert not a.is_busy(user_id, now=later)


def test_daily_cap_uses_ist_midnight_not_utc_or_financial_fixture_day(db, pg_engine, monkeypatch):
    monkeypatch.setenv("CHAT_DAILY_LIMIT", "1")
    get_settings.cache_clear()
    user_id = owner(db)
    db.commit()
    gate = ChatGate(pg_engine)
    before = datetime(2026, 10, 18, 18, 29, 59, tzinfo=timezone.utc)
    first = gate.acquire(user_id, now=before)
    gate.release(user_id, first, now=before)
    with pytest.raises(HTTPException):
        gate.acquire(user_id, now=before)
    after = before + timedelta(seconds=2)
    second = gate.acquire(user_id, now=after)
    gate.release(user_id, second, now=after)
    row = db.scalar(select(m.ChatLease).where(m.ChatLease.user_id == user_id))
    assert row.daily_day.isoformat() == "2026-10-19" and row.daily_count == 1


def test_stale_turn_cannot_publish_history_or_release_new_claim(db, pg_engine):
    user_id = owner(db)
    db.commit()
    gate = ChatGate(pg_engine)
    first = gate.acquire(user_id)
    row = db.scalar(select(m.ChatLease).where(m.ChatLease.user_id == user_id))
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    second = gate.acquire(user_id)

    class Connected:
        async def is_disconnected(self):
            return False

    async def run():
        return [
            chunk
            async for chunk in stream_turn(
                Connected(),
                pg_engine,
                user_id,
                uuid.uuid4(),
                "monthly total",
                datetime.now(timezone.utc).date(),
                FakeLLM(),
                first,
            )
        ]

    events = asyncio.run(run())
    assert any("event: error" in event for event in events)
    assert not any("event: final" in event for event in events)
    assert repo.count_owned(db, user_id, m.ChatMessage) == 0
    assert gate.is_busy(user_id)
    gate.release(user_id, second)
    repo.delete_data(db, user_id)
    db.commit()
    assert repo.count_owned(db, user_id, m.ChatLease) == 0
