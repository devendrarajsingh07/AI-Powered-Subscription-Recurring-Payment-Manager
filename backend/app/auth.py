"""Credential operations are the sole pre-auth database lookup exception (users only)."""

import uuid
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app import repositories as repo
from app.config import get_settings
from app.db import get_db
from app.models import User
from app.rate_limits import AuthLimiter

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


limiter = AuthLimiter()
