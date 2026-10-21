"""Real PostgreSQL checks; no email/refresh/durable-worker completion is implied."""

import json
import secrets
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_api import PASSWORD, account, load

from app import models as m
from app.account_security import audit, create_invite, digest, revoke_invite
from app.config import Settings, get_settings


def mode(monkeypatch, value):
    monkeypatch.setenv("REGISTRATION_MODE", value)
    get_settings.cache_clear()


def test_closed_registration_and_existing_login(api_client, monkeypatch):
    headers, user = account(api_client)
    mode(monkeypatch, "closed")
    denied = api_client.post(
        "/api/v1/auth/register", json={"email": "blocked@example.org", "password": PASSWORD}
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "registration_unavailable"
    assert (
        api_client.post(
            "/api/v1/auth/login", json={"email": user["email"], "password": PASSWORD}
        ).status_code
        == 200
    )
    assert api_client.get("/api/v1/auth/me", headers=headers).status_code == 200


def test_invite_is_email_bound_hashed_single_use(api_client, db, monkeypatch):
    _, owner = account(api_client)
    invite, token = create_invite(db, uuid.UUID(owner["id"]), "Invited@Example.org")
    invite_id = invite.id
    db.commit()
    assert invite.token_digest != token and len(invite.token_digest) == 64
    assert invite.email_digest != "invited@example.org"
    mode(monkeypatch, "invite")
    body = {"email": "wrong@example.org", "password": PASSWORD, "invite_code": token}
    assert api_client.post("/api/v1/auth/register", json=body).status_code == 403
    body["email"] = " INVITED@example.org "
    assert api_client.post("/api/v1/auth/register", json=body).status_code == 201
    assert api_client.post("/api/v1/auth/register", json=body).status_code == 403
    db.expire_all()
    assert db.get(m.RegistrationInvite, invite_id).used_at is not None
    assert token not in repr(db.get(m.RegistrationInvite, invite_id).__dict__)


@pytest.mark.parametrize("condition", ["expired", "revoked", "missing", "random"])
def test_invite_rejection_is_generic(api_client, db, monkeypatch, condition):
    _, owner = account(api_client)
    row, token = create_invite(db, uuid.UUID(owner["id"]), "invited@example.org")
    if condition == "expired":
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    elif condition == "revoked":
        revoke_invite(db, uuid.UUID(owner["id"]), row.id)
    db.commit()
    mode(monkeypatch, "invite")
    body = {"email": "invited@example.org", "password": PASSWORD}
    if condition != "missing":
        body["invite_code"] = secrets.token_urlsafe(32) if condition == "random" else token
    response = api_client.post("/api/v1/auth/register", json=body)
    assert response.status_code == 403
    assert (
        response.json()["error"]["message"]
        == "Registration is closed or requires a valid invitation"
    )


def test_two_concurrent_registrations_consume_once(api_client, db, monkeypatch):
    _, owner = account(api_client)
    _, token = create_invite(db, uuid.UUID(owner["id"]), "invited@example.org")
    db.commit()
    mode(monkeypatch, "invite")
    body = {"email": "invited@example.org", "password": PASSWORD, "invite_code": token}
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(lambda _: api_client.post("/api/v1/auth/register", json=body), range(2))
        )
    assert sorted(response.status_code for response in responses) == [201, 403]


def test_duplicate_account_rolls_back_invite_consumption(api_client, db, monkeypatch):
    _, owner = account(api_client)
    row, token = create_invite(db, uuid.UUID(owner["id"]), owner["email"])
    row_id = row.id
    db.commit()
    mode(monkeypatch, "invite")
    response = api_client.post(
        "/api/v1/auth/register",
        json={"email": owner["email"], "password": PASSWORD, "invite_code": token},
    )
    assert response.status_code == 409
    db.expire_all()
    assert db.get(m.RegistrationInvite, row_id).used_at is None


def test_revoke_cannot_target_other_issuer(api_client, db):
    _, first = account(api_client)
    _, second = account(api_client)
    row, _ = create_invite(db, uuid.UUID(first["id"]), "invited@example.org")
    db.commit()
    with pytest.raises(ValueError, match="not found"):
        revoke_invite(db, uuid.UUID(second["id"]), row.id)


def test_production_defaults_closed_and_rejects_open(monkeypatch):
    monkeypatch.delenv("REGISTRATION_MODE", raising=False)
    values = dict(
        _env_file=None,
        environment="production",
        demo_enabled=False,
        notifier_provider="smtp",
        app_test_as_of="",
        web_origin="https://web.example.org",
        api_origin="https://api.example.org",
        auth_cookie_site="example.org",
        jwt_secret=secrets.token_urlsafe(48),
    )
    assert Settings(**values).registration_mode == "closed"
    with pytest.raises(ValidationError):
        Settings(**values, registration_mode="open")


def test_digest_separates_purposes():
    assert digest("same", "email") != digest("same", "invite")


def test_security_events_are_content_free_and_cascade(api_client, db, caplog):
    headers, user = account(api_client)
    api_client.post(
        "/api/v1/auth/login", json={"email": "missing@example.org", "password": PASSWORD}
    )
    api_client.get("/api/v1/me/export", headers=headers)
    rows = list(db.scalars(select(m.SecurityEvent)))
    assert {row.kind for row in rows} >= {"registered", "login", "login_failed", "export"}
    serialized = repr(
        [
            {column.name: getattr(row, column.name) for column in m.SecurityEvent.__table__.columns}
            for row in rows
        ]
    )
    assert user["email"] not in serialized and PASSWORD not in serialized
    assert user["email"] not in caplog.text and PASSWORD not in caplog.text
    with pytest.raises(ValueError):
        audit(db, uuid.UUID(user["id"]), "arbitrary-private-content")
    assert api_client.delete("/api/v1/me/data", headers=headers).status_code == 200
    db.expire_all()
    assert (
        db.scalar(
            select(func.count())
            .select_from(m.SecurityEvent)
            .where(m.SecurityEvent.user_id == uuid.UUID(user["id"]))
        )
        == 0
    )


def test_export_is_complete_scoped_and_excludes_secrets(api_client, db):
    first, user = account(api_client)
    second, other = account(api_client)
    load(api_client, first)
    response = api_client.get("/api/v1/me/export", headers=first)
    assert response.status_code == 200
    assert 'attachment; filename="subtrack-data.json"' == response.headers["content-disposition"]
    assert response.headers["cache-control"] == "no-store"
    payload = response.json()
    assert payload["profile"]["email"] == user["email"]
    assert len(payload["transactions"]) == 399 and len(payload["subscriptions"]) == 16
    assert all(isinstance(row["amount"], str) for row in payload["transactions"])
    assert all(row["user_id"] == user["id"] for row in payload["transactions"])
    assert other["email"] not in response.text
    for forbidden in (
        "password_hash",
        "token_digest",
        "email_digest",
        "access_token",
        "refresh_token",
    ):
        assert forbidden not in response.text
    assert api_client.get("/api/v1/me/export", headers=second).json()["transactions"] == []
    assert api_client.get("/api/v1/me/export").status_code == 401


def test_schema_owned_invite_deleted_with_issuer(api_client, pg_engine):
    headers, user = account(api_client)
    with Session(pg_engine) as db, db.begin():
        create_invite(db, uuid.UUID(user["id"]), "invited@example.org")
    api_client.delete("/api/v1/me/data", headers=headers)
    with Session(pg_engine) as db:
        assert db.scalar(select(func.count()).select_from(m.RegistrationInvite)) == 0


def test_api_hsts(api_client):
    assert (
        api_client.get("/api/v1/health").headers["strict-transport-security"] == "max-age=15552000"
    )


def test_invite_not_returned_in_openapi_examples(api_client):
    spec = api_client.get("/api/v1/openapi.json").json()
    assert "invite_code" in spec["components"]["schemas"]["Register"]["properties"]
    assert "/api/v1/me/export" in spec["paths"]
    assert "token_digest" not in json.dumps(spec)


def test_shared_limiter_concurrent_instances_and_restart(pg_engine, monkeypatch):
    from fastapi import HTTPException
    from starlette.requests import Request

    from app.rate_limits import AuthLimiter

    monkeypatch.setenv("AUTH_LOGIN_LIMIT", "5")
    get_settings.cache_clear()
    peers = [AuthLimiter(pg_engine), AuthLimiter(pg_engine)]
    request = Request({"type": "http", "client": ("192.0.2.1", 1234)})

    def attempt(index):
        try:
            peers[index % 2].check(request, "login")
            return 200
        except HTTPException as exc:
            return exc.status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(20)))
    assert results.count(200) == 5 and results.count(429) == 15
    with pytest.raises(HTTPException) as denied:
        AuthLimiter(pg_engine).check(request, "login")
    assert denied.value.status_code == 429
    with Session(pg_engine) as db, db.begin():
        rows = list(db.scalars(select(m.RateLimitBucket)))
        assert len(rows) == 1
        assert "192.0.2.1" not in repr(rows[0].__dict__)
        rows[0].expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    AuthLimiter(pg_engine).check(request, "login")


def test_limiter_store_failure_fails_closed(monkeypatch):
    from fastapi import HTTPException
    from sqlalchemy.exc import OperationalError
    from starlette.requests import Request

    from app.rate_limits import AuthLimiter

    class Broken:
        def __enter__(self):
            raise OperationalError("private SQL", {}, Exception("private connection details"))

        def __exit__(self, *_):
            pass

    monkeypatch.setattr("app.rate_limits.Session", lambda _: Broken())
    request = Request({"type": "http", "client": ("192.0.2.1", 1234)})
    with pytest.raises(HTTPException) as denied:
        AuthLimiter(object()).check(request, "login")
    assert denied.value.status_code == 503
    assert "private" not in repr(denied.value.detail)


def test_incomplete_beta_cannot_start_as_production(monkeypatch):
    import asyncio
    from types import SimpleNamespace

    from app.main import app, lifespan

    monkeypatch.setattr("app.main.get_settings", lambda: SimpleNamespace(environment="production"))

    async def start():
        async with lifespan(app):
            pytest.fail("Incomplete beta must not start")

    with pytest.raises(RuntimeError, match="Private beta launch is blocked"):
        asyncio.run(start())
