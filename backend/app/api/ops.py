"""Internal, token-gated, content-free metrics. Not part of the public OpenAPI contract.

Only counts, ages and rates: never descriptions, merchants, amounts, addresses or user IDs.
Disabled (404) unless an operator sets OPS_METRICS_TOKEN to a long random value.
"""

import hmac
from datetime import datetime, timedelta, timezone

from fastapi import Request
from sqlalchemy import func, select

from app import auth
from app import models as m
from app.api.routes import Db, fail, router
from app.config import get_settings
from app.services import llm_controls as controls


def authorize(request: Request):
    expected = get_settings().ops_metrics_token.get_secret_value()
    if len(expected) < 32:
        fail(404, "not_found", "Not found")
    auth.limiter.check(request, "ops-metrics")
    supplied = request.headers.get("x-ops-token", "")
    if not hmac.compare_digest(supplied.encode(), expected.encode()):
        fail(404, "not_found", "Not found")


def collect(db, *, now=None):
    now = now or datetime.now(timezone.utc)
    count = func.count()
    jobs = {
        f"{kind}:{status}": n
        for kind, status, n in db.execute(
            select(m.DurableJob.kind, m.DurableJob.status, count).group_by(
                m.DurableJob.kind, m.DurableJob.status
            )
        )
    }
    active = m.DurableJob.status.in_(("staging", "queued", "running"))
    oldest = db.scalar(
        select(func.min(m.DurableJob.created_at)).where(m.DurableJob.status == "queued")
    )
    chat_total = db.scalar(select(count).where(m.ChatMessage.role == "assistant"))
    chat_blocked = db.scalar(
        select(count).where(m.ChatMessage.role == "assistant", m.ChatMessage.verified.is_(False))
    )
    usage = db.execute(
        select(
            func.coalesce(func.sum(m.StatementUsage.attempts), 0),
            func.coalesce(func.sum(m.StatementUsage.failures), 0),
            func.coalesce(func.sum(m.StatementUsage.flagged_rows), 0),
            func.coalesce(func.sum(m.StatementUsage.edited_rows), 0),
        )
    ).one()
    return {
        "generated_at": now.isoformat(),
        "queue": {
            "depth": db.scalar(select(count).where(active)),
            "oldest_queued_age_seconds": int((now - oldest).total_seconds()) if oldest else 0,
            "dead_letter_total": db.scalar(
                select(count).where(m.DurableJob.status == "dead_letter")
            ),
            "by_kind_status": jobs,
        },
        "alerts": {
            status: n
            for status, n in db.execute(select(m.Alert.status, count).group_by(m.Alert.status))
        },
        "security_events_24h": {
            kind: n
            for kind, n in db.execute(
                select(m.SecurityEvent.kind, count)
                .where(m.SecurityEvent.created_at >= now - timedelta(hours=24))
                .group_by(m.SecurityEvent.kind)
            )
        },
        "chat": {
            "assistant_messages": chat_total,
            "verifier_blocked": chat_blocked,
            "verifier_block_rate": round(chat_blocked / chat_total, 4) if chat_total else 0.0,
        },
        "statements": {
            "attempts": int(usage[0]),
            "failures": int(usage[1]),
            "flagged_rows": int(usage[2]),
            "edited_rows": int(usage[3]),
            "edit_rate": round(int(usage[3]) / int(usage[2]), 4) if int(usage[2]) else 0.0,
        },
        "llm": {
            "provider_live": get_settings().llm_provider != "fake",
            "kill_switch": bool(
                get_settings().llm_kill_switch or controls.forced_offline(db.get_bind())
            ),
            "today": controls.usage(db.get_bind()),
            "caps": {
                "requests": get_settings().llm_global_daily_requests,
                "tokens": get_settings().llm_global_daily_tokens,
            },
        },
        "email": {
            "suppressed_accounts": db.scalar(
                select(count).select_from(m.User).where(m.User.alerts_suppressed_at.is_not(None))
            ),
            "support_reports_24h": db.scalar(
                select(count)
                .select_from(m.SupportReport)
                .where(m.SupportReport.created_at >= now - timedelta(hours=24))
            ),
        },
        "accounts_total": db.scalar(select(count).select_from(m.User)),
    }


@router.get("/ops/metrics", include_in_schema=False)
def metrics(request: Request, db: Db):
    authorize(request)
    return collect(db)
