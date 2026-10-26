"""Account actions accept only opaque codes. Business endpoints never authenticate via cookies."""

from datetime import datetime, timezone

from fastapi import BackgroundTasks, Depends, HTTPException, Request, Response
from fastapi.security import APIKeyCookie
from sqlalchemy import select

from app import auth
from app import schemas as s
from app.account_security import audit
from app.api.routes import CurrentUser, Db, router
from app.config import get_settings
from app.models import AuthSession, User
from app.services import account_actions as actions
from app.services import sessions

refresh_security = Depends(APIKeyCookie(name=sessions.COOKIE, auto_error=False))


@router.get("/auth/config", response_model=s.AuthConfig, tags=["auth"])
def auth_config():
    cfg = get_settings()
    return dict(
        public_demo_only=cfg.public_demo_only,
        receipt_import_enabled=(
            cfg.receipt_import_enabled and not cfg.public_demo_only
            and cfg.environment != "production" and cfg.llm_provider == "fake"
        ),
        session_mode=cfg.auth_session_mode,
        notice="Public demo — do not upload real statements or personal data"
        if cfg.public_demo_only
        else "Educational use with uploaded or simulated data",
        legal_version=cfg.legal_version,
        legal_acceptance_required=cfg.legal_acceptance_required,
    )


@router.post("/auth/demo", response_model=s.Token, tags=["auth"])
def disposable_demo(request: Request, db: Db):
    import secrets
    import uuid
    from datetime import timedelta

    cfg = get_settings()
    if not cfg.public_demo_only:
        from app.api.routes import fail

        fail(404, "not_found", "Public demo sessions are disabled")
    auth.limiter.check(request, "demo-session")
    user = auth.register_user(
        db, f"visitor-{uuid.uuid4().hex}@example.org", secrets.token_urlsafe(32)
    )
    user.demo_expires_at = datetime.now(timezone.utc) + timedelta(hours=cfg.demo_account_ttl_hours)
    family, _ = sessions.start(db, user)
    audit(db, user.id, "login")
    db.commit()
    return dict(
        access_token=auth.issue_token(user.id, session_id=family.id, version=user.auth_version),
        expires_in=cfg.jwt_access_minutes * 60,
    )


@router.post(
    "/auth/csrf", response_model=s.CsrfResult, tags=["auth"], dependencies=[refresh_security]
)
def csrf(request: Request, db: Db):
    require_strict()
    sessions.check_origin(request)
    auth.limiter.check(request, "csrf")
    raw = request.cookies.get(sessions.COOKIE)
    try:
        row = sessions.lookup(db, raw)
    except HTTPException as exc:
        if exc.status_code != 401:
            raise
        return dict(csrf_token=None)
    family = db.scalar(
        select(AuthSession).where(
            AuthSession.user_id == row.user_id, AuthSession.id == row.session_id
        )
    )
    now = datetime.now(timezone.utc)
    if (
        row.used_at
        or row.expires_at <= now
        or family is None
        or family.revoked_at
        or family.expires_at <= now
    ):
        return dict(csrf_token=None)
    return dict(csrf_token=sessions.csrf(raw))


def require_strict():
    if get_settings().auth_session_mode != "strict":
        raise sessions.denied()


@router.post(
    "/auth/refresh", response_model=s.Token, tags=["auth"], dependencies=[refresh_security]
)
def refresh(request: Request, response: Response, db: Db):
    require_strict()
    auth.limiter.check(request, "refresh")
    user, family, raw = sessions.refresh(db, request)
    if get_settings().require_email_verification and user.email_verified_at is None:
        raise sessions.denied()
    db.commit()
    sessions.cookie(response, raw)
    return dict(
        access_token=auth.issue_token(user.id, session_id=family.id, version=user.auth_version),
        expires_in=get_settings().jwt_access_minutes * 60,
        csrf_token=sessions.csrf(raw),
    )


@router.post("/auth/logout", response_model=s.MessageResult, tags=["auth"])
def logout(request: Request, response: Response, user: CurrentUser, db: Db):
    row = db.scalar(
        select(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.id == request.state.session_id)
        .with_for_update()
    )
    row.revoked_at = datetime.now(timezone.utc)
    audit(db, user.id, "logout")
    db.commit()
    sessions.clear_cookie(response)
    return dict(message="Signed out")


@router.post(
    "/auth/logout-cookie",
    response_model=s.MessageResult,
    tags=["auth"],
    dependencies=[refresh_security],
)
def cookie_logout(request: Request, response: Response, db: Db):
    require_strict()
    auth.limiter.check(request, "refresh")
    raw = sessions.cookie_request(request)
    token = sessions.lookup(db, raw)
    user = db.scalar(select(User).where(User.id == token.user_id).with_for_update())
    if user is not None:
        row = db.scalar(
            select(AuthSession)
            .where(
                AuthSession.user_id == user.id,
                AuthSession.id == token.session_id,
            )
            .with_for_update()
        )
        if row is not None:
            row.revoked_at = datetime.now(timezone.utc)
            audit(db, user.id, "logout")
        db.commit()
    sessions.clear_cookie(response)
    return dict(message="Signed out")


@router.post("/auth/logout-all", response_model=s.MessageResult, tags=["auth"])
def logout_all(response: Response, user: CurrentUser, db: Db):
    db.refresh(user, with_for_update=True)
    sessions.revoke_all(db, user)
    audit(db, user.id, "logout_all")
    db.commit()
    sessions.clear_cookie(response)
    return dict(message="All sessions revoked")


def request_action(body, request, db, background, kind):
    auth.limiter.check(request, "account-" + kind)
    user = (
        None
        if get_settings().public_demo_only
        else db.scalar(select(User).where(User.email == str(body.email)).with_for_update())
    )
    if user is not None and (kind != "verify" or user.email_verified_at is None):
        raw = actions.issue(db, user.id, kind)
        if kind == "reset":
            audit(db, user.id, "reset_requested")
        db.commit()
        background.add_task(actions.deliver, db.get_bind(), user.id, kind, raw)
    return dict(message="If this address is eligible, an email will arrive with a single-use code")


@router.post("/auth/email/request", response_model=s.MessageResult, status_code=202, tags=["auth"])
def request_verification(
    body: s.EmailRequest, request: Request, db: Db, background: BackgroundTasks
):
    return request_action(body, request, db, background, "verify")


@router.post("/auth/email/confirm", response_model=s.MessageResult, tags=["auth"])
def confirm_email(body: s.AccountCode, request: Request, db: Db):
    auth.limiter.check(request, "confirm-email")
    user = actions.consume(db, body.token.get_secret_value(), "verify")
    user.email_verified_at = datetime.now(timezone.utc)
    audit(db, user.id, "email_verified")
    db.commit()
    return dict(message="Email verified. You can sign in.")


@router.post(
    "/auth/password/request", response_model=s.MessageResult, status_code=202, tags=["auth"]
)
def request_reset(body: s.EmailRequest, request: Request, db: Db, background: BackgroundTasks):
    return request_action(body, request, db, background, "reset")


@router.post("/auth/password/reset", response_model=s.MessageResult, tags=["auth"])
def reset_password(body: s.ResetPassword, request: Request, db: Db, background: BackgroundTasks):
    auth.limiter.check(request, "reset-password")
    user = actions.consume(db, body.token.get_secret_value(), "reset")
    user.password_hash = auth.hash_password(body.password.get_secret_value())
    sessions.revoke_all(db, user)
    audit(db, user.id, "password_changed")
    user_id, engine = user.id, db.get_bind()
    db.commit()
    background.add_task(actions.deliver, engine, user_id, "changed")
    return dict(message="Password changed. Sign in again on each device.")
