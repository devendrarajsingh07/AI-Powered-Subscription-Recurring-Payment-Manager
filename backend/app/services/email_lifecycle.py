"""Provider-agnostic suppression and signed one-click unsubscribe. No content, counts only."""

import hashlib
import hmac
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select

from app import models as m
from app.account_security import audit
from app.config import get_settings

KINDS = ("hard_bounce", "complaint")


def sign(user_id):
    key = get_settings().jwt_secret.get_secret_value().encode()
    return hmac.new(key, b"unsubscribe\0" + str(user_id).encode(), hashlib.sha256).hexdigest()


def verify(user_id, token):
    return isinstance(token, str) and hmac.compare_digest(sign(user_id), token)


def unsubscribe_urls(user_id):
    cfg = get_settings()
    query = f"u={user_id}&t={sign(user_id)}"
    return (
        cfg.api_origin.rstrip("/") + "/api/v1/alerts/unsubscribe?" + query,
        cfg.web_origin.rstrip("/") + "/unsubscribe?" + query,
    )


def suppress(db, address, kind):
    """A bounce/complaint for an address suppresses every account currently delivering to it."""
    if kind not in KINDS:
        raise ValueError("Unknown email event")
    target = address.strip().lower()
    now = datetime.now(timezone.utc)
    users = db.scalars(
        select(m.User)
        .where(func.lower(func.coalesce(m.User.notification_email, "")) == target)
        .with_for_update()
    ).all()
    for user in users:
        user.alerts_suppressed_at, user.alerts_suppressed_reason = now, kind
        # Outstanding messages for this address can no longer be delivered.
        for alert in db.scalars(
            select(m.Alert).where(
                m.Alert.user_id == user.id, m.Alert.status.in_(("pending", "retrying"))
            )
        ):
            alert.status = "skipped"
            alert.safe_failure_reason = (
                "Email delivery suppressed after a bounce or complaint; update your address"
            )
            alert.next_attempt_at = None
        audit(db, user.id, "email_suppressed")
    return len(users)


def parse_user(value):
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None
