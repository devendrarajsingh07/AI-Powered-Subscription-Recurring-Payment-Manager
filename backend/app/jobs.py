"""Same PostgreSQL-serialized job for the scheduler and explicit-clock CLI."""

import argparse
import json
import logging
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app import models as m
from app import repositories as repo
from app.config import get_settings
from app.db import get_engine
from app.services.alerts import generate
from app.services.insights import regenerate
from app.services.notifier import ConsoleNotifier, DeliveryError, SmtpNotifier, get_notifier, render

logger = logging.getLogger("subtrack.alerts")
LOCK_KEY = 734936241


def recover_console(db, user_id, transport):
    recovered = 0
    for row in repo.list_owned(db, user_id, m.Alert, limit=None):
        snapshot = row.delivery_snapshot
        if row.status in ("sent", "failed") or not snapshot or snapshot["provider"] != "console":
            continue
        if transport.delivered(user_id, row.id):
            row.payload, row.recipient = snapshot["payload"], snapshot["recipient"]
            row.sent_at = datetime.fromisoformat(snapshot["attempted_at"])
            row.status, row.next_attempt_at, row.safe_failure_reason = "sent", None, None
            recovered += 1
    return recovered


def business_date(now, zone):
    if now.tzinfo is None:
        raise ValueError("An aware timestamp is required")
    return now.astimezone(ZoneInfo(zone)).date()


def run_jobs(engine, *, as_of=None, now=None, notifier=None, retry_only=False):
    """retry_only: short-interval loop that only re-attempts due `retrying` deliveries."""
    cfg = get_settings()
    if cfg.environment == "production" and (as_of is not None or now is not None):
        raise RuntimeError("Production forbids simulated alert clocks")
    now = now or (
        datetime.combine(as_of, time(9), ZoneInfo(cfg.app_timezone)).astimezone(timezone.utc)
        if as_of
        else datetime.now(timezone.utc)
    )
    day = as_of or business_date(now, cfg.app_timezone)
    transport = notifier or get_notifier(cfg)
    console = (
        transport if isinstance(transport, ConsoleNotifier) else ConsoleNotifier(cfg.outbox_dir)
    )
    provider = (
        "console"
        if isinstance(transport, ConsoleNotifier)
        else "smtp"
        if isinstance(transport, SmtpNotifier)
        else "custom"
    )
    stats = dict(created=0, sent=0, failed=0, locked=0)
    with engine.connect() as guard:
        acquired = guard.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY})
        guard.commit()
        if not acquired:
            stats["locked"] = 1
            return stats
        try:
            # System job enumerates IDs only; all financial reads below take a user scope.
            with Session(engine) as db:
                users = list(
                    db.scalars(
                        select(m.Alert.user_id)
                        .where(m.Alert.status == "retrying", m.Alert.next_attempt_at <= now)
                        .distinct()
                    )
                    if retry_only
                    else db.scalars(select(m.User.id))
                )
            for user_id in users:
                with Session(engine) as db, db.begin():
                    if repo.get_user(db, user_id, lock=True) is None:
                        continue
                    if not retry_only:
                        stats["sent"] += recover_console(db, user_id, console)
                        regenerate(db, user_id, as_of=day)
                        stats["created"] += generate(db, user_id, as_of=day, now=now)
                    ids = [
                        row.id
                        for row in repo.list_owned(
                            db,
                            user_id,
                            m.Alert,
                            m.Alert.status.in_(
                                ["retrying"] if retry_only else ["pending", "retrying"]
                            ),
                            m.Alert.send_on <= day,
                            limit=None,
                        )
                        if row.next_attempt_at is None or row.next_attempt_at <= now
                    ]
                for alert_id in ids:
                    claimed = False
                    with Session(engine) as db, db.begin():
                        generate(db, user_id, as_of=day, now=now)
                        row = repo.get_owned(db, user_id, m.Alert, alert_id)
                        if (
                            not row
                            or row.status not in ("pending", "retrying")
                            or row.send_on > day
                        ):
                            continue
                        if row.attempt_count >= cfg.alert_max_attempts:
                            row.status, row.safe_failure_reason = (
                                "failed",
                                "Delivery confirmation unavailable; retry limit reached",
                            )
                            stats["failed"] += 1
                            continue
                        row.attempt_count += 1
                        row.last_attempt_at = now
                        row.delivery_snapshot = dict(
                            payload=row.payload,
                            recipient=row.recipient,
                            attempted_at=now.isoformat(),
                            provider=provider,
                        )
                        row.next_attempt_at = now + timedelta(
                            seconds=min(
                                86400, cfg.alert_retry_seconds * 2 ** (row.attempt_count - 1)
                            )
                        )
                        row.status, row.safe_failure_reason = (
                            "retrying",
                            "Awaiting delivery confirmation",
                        )
                        claimed = True
                    if not claimed:
                        continue
                    # Persist the claim, then revalidate under the account lock before I/O.
                    with Session(engine) as db, db.begin():
                        generate(db, user_id, as_of=day, now=now)
                        row = repo.get_owned(db, user_id, m.Alert, alert_id)
                        if not row or row.status != "retrying" or row.send_on > day:
                            continue
                        if (
                            row.payload != row.delivery_snapshot["payload"]
                            or row.recipient != row.delivery_snapshot["recipient"]
                        ):
                            row.status, row.next_attempt_at = "pending", now
                            row.safe_failure_reason = (
                                "Preferences or facts changed; waiting for next check"
                            )
                            continue
                        try:
                            transport.send(render(row, settings=cfg))
                        except Exception as exc:
                            if provider == "console" and console.delivered(user_id, row.id):
                                stats["sent"] += recover_console(db, user_id, console)
                                continue
                            permanent = isinstance(exc, DeliveryError) and exc.permanent
                            terminal = row.attempt_count >= cfg.alert_max_attempts or permanent
                            row.status = "failed" if terminal else "retrying"
                            row.safe_failure_reason = (
                                "Delivery failed; address or message is invalid"
                                if permanent
                                else "Delivery failed; retry limit reached"
                                if terminal
                                else "Delivery failed; retry scheduled"
                            )
                            stats["failed"] += int(terminal)
                        else:
                            row.status, row.sent_at = "sent", now
                            row.next_attempt_at, row.safe_failure_reason = None, None
                            stats["sent"] += 1
                        logger.info(
                            "Alert processed alert_id=%s attempt_count=%d status=%s",
                            row.id,
                            row.attempt_count,
                            row.status,
                        )
        finally:
            guard.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY})
            guard.commit()
    logger.info(
        "Alert job completed created_count=%d sent_count=%d", stats["created"], stats["sent"]
    )
    return stats


def main():
    parser = argparse.ArgumentParser(description="Generate and deliver due SubTrack alerts")
    parser.add_argument("command", choices=["run"])
    parser.add_argument("--as-of", type=date.fromisoformat)
    args = parser.parse_args()
    try:
        result = run_jobs(get_engine(), as_of=args.as_of)
    except Exception:
        print(json.dumps({"error": "Alert job could not complete; check recorded delivery states"}))
        return 1
    print(json.dumps(result))  # Counts only.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
