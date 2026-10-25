"""Live-provider production controls. Offline stays the safe default and the fallback.

Order of precedence for a live-capable client: env kill switch, shared DB kill switch (immediate on
every instance), global daily request/token caps shared through PostgreSQL. Anything else that
prevents a live answer (provider error, quota) falls back visibly to the offline assistant.

Every individual provider request (each chat round, each transport retry, each category
suggestion) must first pass `guard`/`reserve`: the kill switch is re-read and one request plus an
estimated token budget (input characters / 4 + the configured output maximum) is reserved
atomically *before* the call. Reservations are never refunded, so failed or retried calls still
count. Token figures are a conservative estimate and a safety cap, not provider billing.
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


class Bypass(Exception):
    """Raised before a provider request that must not be sent; carries the offline reason."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def estimate(*texts):
    """Conservative per-request budget: input characters / 4 plus the full output allowance."""
    return sum(len(t) for t in texts) // 4 + 1 + get_settings().llm_max_tokens


def reserve(engine, tokens=0):
    """Reserve one provider request and `tokens`; None when it may be sent, else the reason."""
    cfg = get_settings()
    if cfg.llm_kill_switch or forced_offline(engine):
        return KILL
    if tokens > cfg.llm_global_daily_tokens or cfg.llm_global_daily_requests < 1:
        return CAP
    with Session(engine) as db, db.begin():
        # Atomic across instances: the row is only incremented while both caps still hold
        # *including* this reservation, so concurrent callers can never overshoot.
        row = db.execute(
            text(
                "INSERT INTO llm_usage (day, requests, tokens) VALUES (:day, 1, :n) "
                "ON CONFLICT (day) DO UPDATE SET requests = llm_usage.requests + 1, "
                "tokens = llm_usage.tokens + :n "
                "WHERE llm_usage.requests + 1 <= :requests AND llm_usage.tokens + :n <= :tokens "
                "RETURNING requests"
            ),
            {
                "day": today(cfg),
                "n": tokens,
                "requests": cfg.llm_global_daily_requests,
                "tokens": cfg.llm_global_daily_tokens,
            },
        ).one_or_none()
    return None if row else CAP


def guard(engine, client, tokens):
    """Call immediately before every live provider request; raises Bypass when it must not go."""
    if not is_live(client):
        return
    reason = reserve(engine, tokens)
    if reason is not None:
        raise Bypass(reason)


def guard_user(engine, client, tokens, authenticated_user_id):
    """Recheck consent/account existence before *each* attempt, including transport retries."""
    if not is_live(client):
        return
    from app import repositories as repo
    from app.services.llm import LLMError

    with Session(engine) as db:
        account = repo.get_user(db, authenticated_user_id)
        if account is None or not account.live_opt_in:
            raise LLMError("Live AI consent is required. No further data was sent.")
    guard(engine, client, tokens)


def route(engine, client):
    """Return (client, fallback_reason) for a new request. Counts nothing: an invalid request
    that is rejected afterwards consumes no shared quota. Reservation happens per provider call."""
    if not is_live(client):
        return client, None
    reason = peek(engine)
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
