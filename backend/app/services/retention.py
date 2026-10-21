"""Documented retention. Counts only: never log or return content, addresses or amounts.

Periods are configuration (see docs/PRIVACY.md). Account deletion removes everything at once;
this job only bounds how long *finished* operational records outlive their usefulness.
Backups and provider-side copies are outside this job and are documented separately.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import models as m
from app.config import get_settings

FINISHED_JOBS = ("done", "dead_letter", "cancelled")
FINISHED_ALERTS = ("sent", "skipped", "failed")


def purge(engine, *, now=None):
    cfg = get_settings()
    now = now or datetime.now(timezone.utc)
    jobs_before = now - timedelta(days=cfg.retain_job_days)
    chat_before = now - timedelta(days=cfg.retain_chat_days)
    audit_before = now - timedelta(days=cfg.retain_audit_days)
    alerts_before = (now - timedelta(days=cfg.retain_alert_days)).date()
    counts = dict(jobs=0, chat=0, alerts=0, audit=0, sessions=0, account_codes=0)
    # System maintenance enumerates IDs only; every delete below is scoped to one owner.
    with Session(engine) as db:
        users = list(db.scalars(select(m.User.id)))
    for user_id in users:
        with Session(engine) as db, db.begin():
            owner = db.scalar(
                select(m.User.id).where(m.User.id == user_id).with_for_update(skip_locked=True)
            )
            if owner is None:  # Deleted or busy; a busy owner is revisited on the next pass.
                continue
            counts["jobs"] += db.execute(
                delete(m.DurableJob).where(
                    m.DurableJob.user_id == user_id,
                    m.DurableJob.status.in_(FINISHED_JOBS),
                    m.DurableJob.updated_at < jobs_before,
                )
            ).rowcount
            counts["chat"] += db.execute(
                delete(m.ChatMessage).where(
                    m.ChatMessage.user_id == user_id, m.ChatMessage.created_at < chat_before
                )
            ).rowcount
            counts["alerts"] += db.execute(
                delete(m.Alert).where(
                    m.Alert.user_id == user_id,
                    m.Alert.status.in_(FINISHED_ALERTS),
                    m.Alert.send_on < alerts_before,
                )
            ).rowcount
            counts["audit"] += db.execute(
                delete(m.SecurityEvent).where(
                    m.SecurityEvent.user_id == user_id, m.SecurityEvent.created_at < audit_before
                )
            ).rowcount
            counts["sessions"] += db.execute(
                delete(m.AuthSession).where(
                    m.AuthSession.user_id == user_id,
                    m.AuthSession.expires_at < now - timedelta(days=1),
                )
            ).rowcount
            counts["account_codes"] += db.execute(
                delete(m.AccountToken).where(
                    m.AccountToken.user_id == user_id,
                    m.AccountToken.expires_at < now - timedelta(days=1),
                )
            ).rowcount
    with Session(engine) as db, db.begin():
        # Failed logins for unknown emails have no owner; bound them by the same audit period.
        counts["audit"] += db.execute(
            delete(m.SecurityEvent).where(
                m.SecurityEvent.user_id.is_(None), m.SecurityEvent.created_at < audit_before
            )
        ).rowcount
    return counts
