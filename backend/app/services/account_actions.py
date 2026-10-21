"""Single-use hashed account codes; raw codes live only in the bounded delivery call."""

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from html import escape

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.account_security import audit, digest
from app.config import get_settings
from app.models import AccountToken, User
from app.services.notifier import Mail, address, get_notifier


def issue(db, user_id, kind):
    if kind not in ("verify", "reset"):
        raise ValueError("Unknown account action")
    now = datetime.now(timezone.utc)
    db.execute(
        update(AccountToken)
        .where(
            AccountToken.user_id == user_id,
            AccountToken.kind == kind,
            AccountToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    raw = secrets.token_urlsafe(32)
    db.add(
        AccountToken(
            user_id=user_id,
            kind=kind,
            token_digest=digest(raw, "account-" + kind),
            expires_at=now + timedelta(minutes=get_settings().account_token_minutes),
        )
    )
    return raw


def consume(db, raw, kind):
    row = db.scalar(
        select(AccountToken).where(
            AccountToken.token_digest == digest(raw, "account-" + kind), AccountToken.kind == kind
        )
    )
    invalid = HTTPException(400, {"code": "invalid_token", "message": "Code is invalid or expired"})
    if row is None:
        raise invalid
    user = db.scalar(select(User).where(User.id == row.user_id).with_for_update())
    if user is None:
        raise invalid
    db.refresh(row)
    if user is None or row.used_at or row.expires_at <= datetime.now(timezone.utc):
        raise invalid
    row.used_at = datetime.now(timezone.utc)
    return user


def deliver(engine, user_id, kind, raw=None):
    """Background after committed token. Failures are safe; request a new code to retry."""
    cfg = get_settings()
    with Session(engine) as db, db.begin():
        # Deletion waits for delivery and then purges the outbox, never the reverse.
        user = db.scalar(select(User).where(User.id == user_id).with_for_update())
        if user is None:
            return
        try:
            get_notifier(cfg).send(render_account(user_id, user.email, kind, raw, cfg))
            event = "account_mail_sent"
        except Exception:
            event = "account_mail_failed"
        audit(db, user_id, event)


def render_account(user_id, recipient, kind, raw, cfg):
    title = {
        "verify": "Verify your SubTrack email",
        "reset": "Reset your SubTrack password",
        "changed": "Your SubTrack password changed",
    }[kind]
    body = (
        f"{title}.\n\nEnter this single-use code in SubTrack: {raw}\n"
        f"It expires in {cfg.account_token_minutes} minutes.\n"
        if raw
        else (
            "Your password changed and all sessions were revoked. "
            "If this was not you, contact the operator.\n"
        )
    )
    body += (
        "\nIgnore an unexpected request. Never share this code.\n"
        "For demo and educational use.\nSettings: " + cfg.web_origin.rstrip("/") + "/settings"
    )
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = (
        address(cfg.smtp_from or "subtrack@example.org"),
        address(recipient),
        title,
    )
    mail_id = uuid.uuid4()
    message["Message-ID"] = f"<{mail_id}@subtrack.local>"
    message.set_content(body)
    message.add_alternative(
        "<html><body><pre>" + escape(body) + "</pre></body></html>", subtype="html"
    )
    return Mail(user_id, mail_id, recipient, message)
