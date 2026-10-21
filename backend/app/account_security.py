"""Pre-auth invitation lookup is a deliberate exception to authenticated repositories."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select

from app.config import get_settings
from app.models import RegistrationInvite, SecurityEvent, User

EVENTS = frozenset(
    {
        "registered",
        "login",
        "login_failed",
        "export",
        "invite_created",
        "invite_revoked",
        "email_verified",
        "reset_requested",
        "password_changed",
        "logout",
        "logout_all",
        "refresh_reuse",
        "account_mail_sent",
        "account_mail_failed",
        "email_suppressed",
        "alert_unsubscribed",
        "support_report",
    }
)


def digest(value, purpose):
    return hmac.new(
        get_settings().jwt_secret.get_secret_value().encode(),
        (purpose + "\0" + value).encode(),
        hashlib.sha256,
    ).hexdigest()


def audit(db, user_id, kind):
    if kind not in EVENTS:
        raise ValueError("Unknown security event")
    db.add(SecurityEvent(user_id=user_id, kind=kind))


def create_invite(db, user_id, email, *, hours=48, now=None):
    if not 1 <= hours <= 168:
        raise ValueError("Invite lifetime must be 1–168 hours")
    if db.get(User, user_id) is None:
        raise ValueError("Issuing account does not exist")
    now = now or datetime.now(timezone.utc)
    token = secrets.token_urlsafe(32)
    row = RegistrationInvite(
        user_id=user_id,
        token_digest=digest(token, "invite"),
        email_digest=digest(email.strip().lower(), "email"),
        expires_at=now + timedelta(hours=hours),
    )
    db.add(row)
    audit(db, user_id, "invite_created")
    db.flush()
    return row, token


def revoke_invite(db, user_id, invite_id):
    row = db.scalar(
        select(RegistrationInvite)
        .where(
            RegistrationInvite.user_id == user_id,
            RegistrationInvite.id == invite_id,
        )
        .with_for_update()
    )
    if row is None:
        raise ValueError("Invite not found")
    row.revoked_at = datetime.now(timezone.utc)
    audit(db, user_id, "invite_revoked")


def consume_invite(db, email, token):
    mode = get_settings().registration_mode
    if mode == "open":
        return
    denied = HTTPException(
        403,
        {
            "code": "registration_unavailable",
            "message": "Registration is closed or requires a valid invitation",
        },
    )
    if mode == "closed" or not token:
        raise denied
    row = db.scalar(
        select(RegistrationInvite)
        .where(
            RegistrationInvite.token_digest == digest(token, "invite"),
            RegistrationInvite.email_digest == digest(email.strip().lower(), "email"),
            RegistrationInvite.used_at.is_(None),
            RegistrationInvite.revoked_at.is_(None),
            RegistrationInvite.expires_at > datetime.now(timezone.utc),
        )
        .with_for_update()
    )
    if row is None:
        raise denied
    row.used_at = datetime.now(timezone.utc)
