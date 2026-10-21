"""Live-provider production controls. Offline stays the safe default and the fallback.

Order of precedence for a live-capable client: env kill switch, shared DB kill switch (immediate on
every instance), global daily request/token caps shared through PostgreSQL. Anything else that
prevents a live answer (provider error, quota) falls back visibly to the offline assistant.
Token usage is an *estimate* (characters / 4); it is a safety cap, not provider billing.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings

KILL = "kill_switch"
CAP = "daily_cap"
ERROR = "provider_error"


def is_live(client):
    """An explicit `live` flag wins; else live when a live provider is configured."""
    return bool(getattr(client, "live", get_settings().llm_provider != "fake"))


def today(cfg=None):
    return datetime.now(ZoneInfo((cfg or get_settings()).app_timezone)).date()


def forced_offline(engine):
    with Session(engine) as db:
        return bool(db.scalar(text("SELECT offline_forced FROM llm_switch WHERE id = 1")))


def set_switch(engine, forced):
    with Session(engine) as db, db.begin():
        db.execute(
            text(
                "INSERT INTO llm_switch (id, offline_forced) VALUES (1, :forced) "
                "ON CONFLICT (id) DO UPDATE SET offline_forced = :forced, updated_at = now()"
            ),
            {"forced": forced},
        )


def usage(engine):
    with Session(engine) as db:
        row = db.execute(
            text("SELECT requests, tokens, fallbacks, errors FROM llm_usage WHERE day = :day"),
            {"day": today()},
        ).one_or_none()
    return dict(zip(("requests", "tokens", "fallbacks", "errors"), row or (0, 0, 0, 0)))


def peek(engine):
    """Read-only: the reason live would be bypassed right now, or None. Counts nothing."""
    cfg = get_settings()
    if cfg.llm_kill_switch or forced_offline(engine):
        return KILL
    used = usage(engine)
    if (
        used["requests"] >= cfg.llm_global_daily_requests
        or used["tokens"] >= cfg.llm_global_daily_tokens
    ):
        return CAP
    return None


def reserve(engine):
    """Return None when a live call may proceed (and count it), else the offline reason."""
    cfg = get_settings()
    if cfg.llm_kill_switch or forced_offline(engine):
        return KILL
    with Session(engine) as db, db.begin():
        # Atomic across instances: the row is only incremented while under both caps.
        row = db.execute(
            text(
                "INSERT INTO llm_usage (day, requests) VALUES (:day, 1) "
                "ON CONFLICT (day) DO UPDATE SET requests = llm_usage.requests + 1 "
                "WHERE llm_usage.requests < :requests AND llm_usage.tokens < :tokens "
                "RETURNING requests"
            ),
            {
                "day": today(cfg),
                "requests": cfg.llm_global_daily_requests,
                "tokens": cfg.llm_global_daily_tokens,
            },
        ).one_or_none()
    return None if row else CAP


def route(engine, client):
    """Return (client, fallback_reason). Never raises; offline clients pass through untouched."""
    if not is_live(client):
        return client, None
    reason = reserve(engine)
    if reason is None:
        return client, None
    note(engine, "fallbacks")
    from app.services.llm.fake import OfflineLLM

    return OfflineLLM(), reason


def note(engine, column, amount=1):
    if column not in ("tokens", "fallbacks", "errors"):
        raise ValueError("Unknown counter")
    with Session(engine) as db, db.begin():
        db.execute(
            text(
                f"INSERT INTO llm_usage (day, {column}) VALUES (:day, :n) "
                f"ON CONFLICT (day) DO UPDATE SET {column} = llm_usage.{column} + :n"
            ),
            {"day": today(), "n": amount},
        )
