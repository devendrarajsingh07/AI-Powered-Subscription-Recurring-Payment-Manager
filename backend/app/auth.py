"""Credential operations are the sole pre-auth database lookup exception (users only)."""

import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from threading import Lock
from time import monotonic

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app import repositories as repo
from app.config import get_settings
from app.db import get_db
from app.models import User

bearer = HTTPBearer(auto_error=False)
DEV_DEMO_EMAIL = "subtrack-demo@example.org"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode(), bcrypt.gensalt(rounds=get_settings().bcrypt_rounds)
    ).decode()


@lru_cache
def dummy_hash() -> bytes:
    return hash_password("DummyLoginCredential42!").encode()


def credentials_user(db, email: str, password: str):
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if get_settings().environment != "development" and email.strip().lower() == DEV_DEMO_EMAIL:
        user = None
    candidate = user.password_hash.encode() if user else dummy_hash()
    # bcrypt compares in constant time; missing accounts also perform a bcrypt check.
    try:
        valid = bcrypt.checkpw(password.encode(), candidate)
    except ValueError:
        valid = False
    return user if valid and user else None


def register_user(db, email: str, password: str):
    if get_settings().environment != "development" and email.strip().lower() == DEV_DEMO_EMAIL:
        raise HTTPException(
            403, {"code": "demo_disabled", "message": "Development demo account is disabled"}
        )
    user = User(email=email.strip().lower(), password_hash=hash_password(password))
    db.add(user)
    db.flush()
    return user


def issue_token(user_id: uuid.UUID):
    config = get_settings()
    secret = config.jwt_secret.get_secret_value()
    if len(secret) < 32:
        raise RuntimeError("JWT configuration is invalid")
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(minutes=config.jwt_access_minutes),
            "iss": config.jwt_issuer,
            "aud": config.jwt_audience,
        },
        secret,
        algorithm="HS256",
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db=Depends(get_db)
) -> User:
    unauthorized = HTTPException(
        401,
        {"code": "unauthorized", "message": "Invalid or expired credentials"},
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not credentials:
        raise unauthorized
    config = get_settings()
    try:
        claims = jwt.decode(
            credentials.credentials,
            config.jwt_secret.get_secret_value(),
            algorithms=["HS256"],
            audience=config.jwt_audience,
            issuer=config.jwt_issuer,
            options={"require": ["sub", "exp", "iat", "iss", "aud"]},
        )
        user_id = uuid.UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise unauthorized from None
    user = repo.get_user(db, user_id)
    if user is None:
        raise unauthorized
    if config.environment != "development" and user.email == DEV_DEMO_EMAIL:
        raise unauthorized
    return user


class AuthLimiter:
    def __init__(self):
        self.events = defaultdict(deque)
        self.lock = Lock()

    def clear(self):
        with self.lock:
            self.events.clear()

    def check(self, request: Request, action: str):
        config = get_settings()
        maximum = config.auth_register_limit if action == "register" else config.auth_login_limit
        key = (request.client.host if request.client else "unknown", action)
        now = monotonic()
        with self.lock:
            expired = [
                item
                for item, values in self.events.items()
                if not values or values[-1] <= now - config.auth_window_seconds
            ]
            for item in expired:
                del self.events[item]
            # Bound memory independently of incoming, potentially attacker-controlled addresses.
            if key not in self.events and len(self.events) >= 10000:
                raise HTTPException(429, {"code": "rate_limited", "message": "Try again later"})
            window = self.events[key]
            while window and window[0] <= now - config.auth_window_seconds:
                window.popleft()
            if len(window) >= maximum:
                raise HTTPException(
                    429,
                    {"code": "rate_limited", "message": "Try again later"},
                    headers={"Retry-After": str(config.auth_window_seconds)},
                )
            window.append(now)


limiter = AuthLimiter()
