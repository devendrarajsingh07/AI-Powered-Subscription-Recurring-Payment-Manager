"""Bearer access plus host-only rotating refresh cookies; all persistence is user-scoped."""

import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select, update

from app.account_security import audit, digest
from app.config import get_settings
from app.models import AuthSession, RefreshToken, User

COOKIE = "subtrack_refresh"
COOKIE_PATH = "/api/v1/auth"


def denied():
    return HTTPException(401, {"code": "unauthorized", "message": "Invalid or expired credentials"})


def csrf(raw):
    return digest(raw, "csrf")


def check_origin(request):
    if request.headers.get("origin") != get_settings().web_origin:
        raise HTTPException(
            403, {"code": "csrf_failed", "message": "Request origin could not be verified"}
        )


def cookie(response, raw):
    if get_settings().auth_session_mode == "demo":
        return
    response.set_cookie(
        COOKIE,
        raw,
        httponly=True,
        secure=get_settings().environment != "development"
        or get_settings().web_origin.startswith("https://"),
        samesite="strict",
        path=COOKIE_PATH,
        max_age=get_settings().auth_refresh_days * 86400,
    )


def clear_cookie(response):
    response.delete_cookie(
        COOKIE,
        path=COOKIE_PATH,
        httponly=True,
        samesite="strict",
        secure=get_settings().environment != "development"
        or get_settings().web_origin.startswith("https://"),
    )


def new_refresh(db, user_id, session):
    raw = secrets.token_urlsafe(48)
    db.add(
        RefreshToken(
            user_id=user_id,
            session_id=session.id,
            token_digest=digest(raw, "refresh"),
            expires_at=session.expires_at,
        )
    )
    return raw


def start(db, user):
    cfg = get_settings()
    session = AuthSession(
        user_id=user.id,
        expires_at=datetime.now(timezone.utc)
        + (
            timedelta(minutes=cfg.jwt_access_minutes)
            if cfg.auth_session_mode == "demo"
            else timedelta(days=cfg.auth_refresh_days)
        ),
    )
    db.add(session)
    db.flush()
    return session, new_refresh(db, user.id, session) if cfg.auth_session_mode == "strict" else None


def lookup(db, raw):
    if not raw or len(raw) > 128:
        raise denied()
    # Deliberate pre-auth opaque-token lookup: identity never comes from caller input.
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_digest == digest(raw, "refresh")))
    if row is None:
        raise denied()
    return row


def refresh(db, request):
    raw = cookie_request(request)
    old = lookup(db, raw)
    user = db.scalar(select(User).where(User.id == old.user_id).with_for_update())
    if user is None:
        raise denied()
    session = db.scalar(
        select(AuthSession)
        .where(AuthSession.user_id == old.user_id, AuthSession.id == old.session_id)
        .with_for_update()
    )
    if session is None:
        raise denied()
    db.refresh(old)
    now = datetime.now(timezone.utc)
    if session.revoked_at or session.expires_at <= now or old.expires_at <= now:
        raise denied()
    if old.used_at:
        session.revoked_at = now
        audit(db, user.id, "refresh_reuse")
        db.commit()  # Persist revocation even though this request is rejected.
        raise denied()
    old.used_at = now
    return user, session, new_refresh(db, user.id, session)


def cookie_request(request):
    check_origin(request)
    raw = request.cookies.get(COOKIE)
    proof = request.headers.get("x-csrf-token", "")
    if (
        not raw
        or len(proof) != 64
        or not proof.isascii()
        or not hmac.compare_digest(csrf(raw), proof)
    ):
        raise HTTPException(
            403, {"code": "csrf_failed", "message": "Request token could not be verified"}
        )
    return raw


def revoke_all(db, user):
    user.auth_version += 1
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
