import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email import policy
from email.parser import BytesParser

import pytest
from sqlalchemy import select
from test_api import PASSWORD, account

from app import models as m
from app.config import get_settings
from app.services.sessions import COOKIE, COOKIE_PATH


def setup_mail(monkeypatch, tmp_path, verify=False):
    monkeypatch.setenv("OUTBOX_DIR", str(tmp_path))
    monkeypatch.setenv("REQUIRE_EMAIL_VERIFICATION", str(verify).lower())
    get_settings.cache_clear()


def code_from_outbox(path, kind):
    for file in path.rglob("*.eml"):
        mail = BytesParser(policy=policy.default).parsebytes(file.read_bytes())
        if kind.lower() in str(mail["Subject"]).lower():
            match = re.search(
                r"single-use code in SubTrack: ([\w-]+)",
                mail.get_body(preferencelist=("plain",)).get_content(),
            )
            if match:
                return match[1]
    pytest.fail("Expected account email was not produced")


def origin():
    return {"Origin": get_settings().web_origin}


def csrf(client):
    response = client.post("/api/v1/auth/csrf", headers=origin())
    assert response.status_code == 200, response.text
    return response.json()["csrf_token"]


@pytest.mark.parametrize("password", ["Password123!", "Welcome2026!", "Qwerty123456!"])
def test_offline_common_password_check(api_client, password):
    assert (
        api_client.post(
            "/api/v1/auth/register", json={"email": "weak@example.org", "password": password}
        ).status_code
        == 422
    )


def test_email_verification_required_single_use_and_hash_only(
    api_client, db, monkeypatch, tmp_path, caplog
):
    setup_mail(monkeypatch, tmp_path, verify=True)
    body = {"email": "verified@example.org", "password": PASSWORD}
    registered = api_client.post("/api/v1/auth/register", json=body)
    assert registered.status_code == 201 and registered.json()["verification_required"]
    assert api_client.post("/api/v1/auth/login", json=body).status_code == 403
    token = code_from_outbox(tmp_path, "verify")
    row = db.scalar(select(m.AccountToken))
    assert row.token_digest != token and token not in registered.text and token not in caplog.text
    assert api_client.post("/api/v1/auth/email/confirm", json={"token": token}).status_code == 200
    assert api_client.post("/api/v1/auth/email/confirm", json={"token": token}).status_code == 400
    login = api_client.post("/api/v1/auth/login", json=body)
    assert login.status_code == 200
    headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    assert api_client.get("/api/v1/auth/me", headers=headers).json()["email_verified"]


def test_anonymous_bootstrap_is_normal_but_refresh_still_requires_cookie_and_csrf(api_client):
    result = api_client.post("/api/v1/auth/csrf", headers=origin())
    assert result.status_code == 200 and result.json() == {"csrf_token": None}
    assert api_client.post("/api/v1/auth/csrf").status_code == 403
    assert api_client.post("/api/v1/auth/refresh", headers=origin()).status_code == 403


def test_session_endpoint_has_its_own_shared_rate_limit(api_client, monkeypatch):
    monkeypatch.setenv("AUTH_SESSION_LIMIT", "2")
    get_settings.cache_clear()
    for _ in range(2):
        assert api_client.post("/api/v1/auth/csrf", headers=origin()).status_code == 200
    assert api_client.post("/api/v1/auth/csrf", headers=origin()).status_code == 429


@pytest.mark.parametrize("kind,path", [("verify", "email/confirm"), ("reset", "password/reset")])
def test_account_code_expiry_and_wrong_kind(api_client, db, monkeypatch, tmp_path, kind, path):
    setup_mail(monkeypatch, tmp_path)
    account(api_client, "codes@example.org")
    endpoint = "email/request" if kind == "verify" else "password/request"
    api_client.post("/api/v1/auth/" + endpoint, json={"email": "codes@example.org"})
    token = code_from_outbox(tmp_path, kind)
    row = db.scalar(select(m.AccountToken).where(m.AccountToken.kind == kind))
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    body = {"token": token, **({"password": "NewPasswordSecure42!"} if kind == "reset" else {})}
    assert api_client.post("/api/v1/auth/" + path, json=body).status_code == 400
    assert (
        api_client.post("/api/v1/auth/email/confirm", json={"token": "x" * 43}).status_code == 400
    )


@pytest.mark.parametrize("path", ["email/request", "password/request"])
def test_requests_do_not_enumerate_and_resend_invalidates(api_client, monkeypatch, tmp_path, path):
    setup_mail(monkeypatch, tmp_path)
    account(api_client, "eligible@example.org")
    known = api_client.post("/api/v1/auth/" + path, json={"email": "eligible@example.org"})
    unknown = api_client.post("/api/v1/auth/" + path, json={"email": "absent@example.org"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    first = code_from_outbox(tmp_path, "verify" if path.startswith("email") else "reset")
    api_client.post("/api/v1/auth/" + path, json={"email": "eligible@example.org"})
    confirm = "email/confirm" if path.startswith("email") else "password/reset"
    body = {
        "token": first,
        **({"password": "NewPasswordSecure42!"} if confirm.startswith("password") else {}),
    }
    assert api_client.post("/api/v1/auth/" + confirm, json=body).status_code == 400


def test_reset_revokes_all_sessions_without_touching_other_users(api_client, monkeypatch, tmp_path):
    setup_mail(monkeypatch, tmp_path)
    first, _ = account(api_client, "reset@example.org")
    again = api_client.post(
        "/api/v1/auth/login", json={"email": "reset@example.org", "password": PASSWORD}
    )
    second, _ = account(api_client, "other@example.org")
    api_client.post("/api/v1/auth/password/request", json={"email": "reset@example.org"})
    token = code_from_outbox(tmp_path, "reset")
    body = {"token": token, "password": "ReplacementSecure42!"}
    assert api_client.post("/api/v1/auth/password/reset", json=body).status_code == 200
    assert api_client.post("/api/v1/auth/password/reset", json=body).status_code == 400
    for old in (first, {"Authorization": "Bearer " + again.json()["access_token"]}):
        assert api_client.get("/api/v1/auth/me", headers=old).status_code == 401
    assert api_client.get("/api/v1/auth/me", headers=second).status_code == 200
    assert (
        api_client.post(
            "/api/v1/auth/login", json={"email": "reset@example.org", "password": PASSWORD}
        ).status_code
        == 401
    )
    assert (
        api_client.post(
            "/api/v1/auth/login", json={"email": "reset@example.org", "password": body["password"]}
        ).status_code
        == 200
    )
    assert any(
        "password changed"
        in BytesParser(policy=policy.default).parsebytes(f.read_bytes())["Subject"].lower()
        for f in tmp_path.rglob("*.eml")
    )


def test_rotation_cookie_attributes_and_reuse_revokes_access(api_client, db):
    headers, _ = account(api_client)
    raw = api_client.cookies.get(COOKIE)
    header = csrf(api_client)
    rotated = api_client.post("/api/v1/auth/refresh", headers={**origin(), "X-CSRF-Token": header})
    assert rotated.status_code == 200
    assert api_client.cookies.get(COOKIE) != raw
    cookie = rotated.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie and f"Path={COOKIE_PATH}" in cookie
    new_headers = {"Authorization": "Bearer " + rotated.json()["access_token"]}
    assert api_client.get("/api/v1/auth/me", headers=new_headers).status_code == 200
    reused = api_client.post(
        "/api/v1/auth/refresh",
        headers={**origin(), "X-CSRF-Token": header, "Cookie": f"{COOKIE}={raw}"},
    )
    assert reused.status_code == 401
    assert api_client.get("/api/v1/auth/me", headers=new_headers).status_code == 401
    assert api_client.get("/api/v1/auth/me", headers=headers).status_code == 401
    rows = list(db.scalars(select(m.RefreshToken)))
    assert all(row.token_digest != raw for row in rows)


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Origin": "https://evil.example"},
        {"Origin": "http://localhost:5173", "X-CSRF-Token": "wrong"},
    ],
)
def test_refresh_requires_origin_and_csrf(api_client, headers):
    access, _ = account(api_client)
    assert api_client.post("/api/v1/auth/refresh", headers=headers).status_code == 403
    assert api_client.get("/api/v1/auth/me", headers=access).status_code == 200


@pytest.mark.parametrize("proof", [b"\xff" * 64, b"x" * 1000])
def test_invalid_csrf_header_encoding_and_length_fail_cleanly(api_client, proof):
    headers, _ = account(api_client)
    response = api_client.post(
        "/api/v1/auth/refresh",
        headers=[
            (b"Origin", get_settings().web_origin.encode()),
            (b"X-CSRF-Token", proof),
        ],
    )
    assert response.status_code == 403
    assert api_client.get("/api/v1/auth/me", headers=headers).status_code == 200


def test_secure_cookie_for_https_and_issuer_is_not_trusted_origin(api_client, monkeypatch):
    monkeypatch.setenv("WEB_ORIGIN", "https://web.example.org")
    get_settings.cache_clear()
    account(api_client, "https@example.org")
    response = api_client.post(
        "/api/v1/auth/login", json={"email": "https@example.org", "password": PASSWORD}
    )
    assert "Secure" in response.headers["set-cookie"]
    assert (
        api_client.post("/api/v1/auth/csrf", headers={"Origin": "https://evil.example"}).status_code
        == 403
    )


def test_logout_and_logout_everywhere_are_revocable(api_client):
    one, user = account(api_client)
    token = api_client.post(
        "/api/v1/auth/login", json={"email": user["email"], "password": PASSWORD}
    ).json()
    two = {"Authorization": "Bearer " + token["access_token"]}
    assert api_client.post("/api/v1/auth/logout", headers=one).status_code == 200
    assert api_client.get("/api/v1/auth/me", headers=one).status_code == 401
    assert api_client.get("/api/v1/auth/me", headers=two).status_code == 200
    assert api_client.post("/api/v1/auth/logout-all", headers=two).status_code == 200
    assert api_client.get("/api/v1/auth/me", headers=two).status_code == 401


def test_cookie_logout_needs_csrf_and_revokes_without_access_jwt(api_client):
    first, _ = account(api_client)
    raw, header = api_client.cookies.get(COOKIE), csrf(api_client)
    second, _ = account(api_client)
    cookie = {**origin(), "Cookie": f"{COOKIE}={raw}"}
    assert api_client.post("/api/v1/auth/logout-cookie", headers=cookie).status_code == 403
    assert api_client.get("/api/v1/auth/me", headers=first).status_code == 200
    result = api_client.post(
        "/api/v1/auth/logout-cookie",
        headers={
            **cookie,
            "X-CSRF-Token": header,
        },
    )
    assert result.status_code == 200 and "Max-Age=0" in result.headers["set-cookie"]
    assert api_client.get("/api/v1/auth/me", headers=first).status_code == 401
    assert api_client.get("/api/v1/auth/me", headers=second).status_code == 200


def test_concurrent_refresh_detects_reuse_and_revokes_winner(api_client):
    account(api_client)
    raw, header = api_client.cookies.get(COOKIE), csrf(api_client)

    def attempt(_):
        return api_client.post(
            "/api/v1/auth/refresh",
            headers={**origin(), "Cookie": f"{COOKIE}={raw}", "X-CSRF-Token": header},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert sorted(r.status_code for r in results) == [200, 401]
    winner = next(r.json() for r in results if r.status_code == 200)
    assert (
        api_client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer " + winner["access_token"]}
        ).status_code
        == 401
    )


def test_session_expiry_and_delete_cascade(api_client, db):
    headers, _ = account(api_client)
    row = db.scalar(select(m.AuthSession))
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    assert api_client.get("/api/v1/auth/me", headers=headers).status_code == 401
    fresh, user = account(api_client)
    response = api_client.delete("/api/v1/me/data", headers=fresh)
    assert response.status_code == 200
    assert response.json()["deleted"]["auth_sessions"] == 1
    assert response.json()["deleted"]["refresh_tokens"] == 1
    assert response.json()["deleted"]["login_backoffs"] == 1
    import uuid

    for table in (m.AuthSession, m.RefreshToken, m.AccountToken, m.LoginBackoff):
        assert not list(db.scalars(select(table).where(table.user_id == uuid.UUID(user["id"]))))


def test_account_backoff_applies_to_unknown_and_known(api_client, db, monkeypatch):
    monkeypatch.setenv("AUTH_LOGIN_LIMIT", "100")
    get_settings.cache_clear()
    account(api_client, "known@example.org")
    for email in ("known@example.org", "missing@example.org"):
        for _ in range(3):
            assert (
                api_client.post(
                    "/api/v1/auth/login", json={"email": email, "password": "IncorrectPassword42!"}
                ).status_code
                == 401
            )
        blocked = api_client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        assert blocked.status_code == 429
    assert all(
        "example.org" not in repr(row.__dict__) for row in db.scalars(select(m.LoginBackoff))
    )


def test_account_mail_failure_is_safe_and_retryable(api_client, db, monkeypatch):
    class Broken:
        def send(self, _):
            raise RuntimeError("secret content must not leak")

    monkeypatch.setattr("app.services.account_actions.get_notifier", lambda _: Broken())
    account(api_client, "failure@example.org")
    result = api_client.post("/api/v1/auth/password/request", json={"email": "failure@example.org"})
    assert result.status_code == 202 and "secret" not in result.text
    assert "account_mail_failed" in list(db.scalars(select(m.SecurityEvent.kind)))


def test_verification_gate_rejects_existing_unverified_access_before_upload(
    api_client,
    monkeypatch,
    tmp_path,
):
    headers, _ = account(api_client)
    setup_mail(monkeypatch, tmp_path, verify=True)
    for path in ("/uploads", "/uploads/preview", "/demo/load"):
        assert api_client.post("/api/v1" + path, headers=headers).status_code == 403


def test_codes_are_bound_to_owner_and_action_and_reject_identity_override(
    api_client,
    db,
    monkeypatch,
    tmp_path,
):
    setup_mail(monkeypatch, tmp_path)
    _, first = account(api_client, "first@example.org")
    _, second = account(api_client, "second@example.org")
    api_client.post("/api/v1/auth/email/request", json={"email": first["email"]})
    code = code_from_outbox(tmp_path, "verify")
    assert (
        api_client.post(
            "/api/v1/auth/password/reset",
            json={
                "token": code,
                "password": "ReplacementSecure42!",
            },
        ).status_code
        == 400
    )
    assert (
        api_client.post(
            "/api/v1/auth/email/confirm",
            json={
                "token": code,
                "user_id": second["id"],
            },
        ).status_code
        == 422
    )
    assert api_client.post("/api/v1/auth/email/confirm", json={"token": code}).status_code == 200
    db.expire_all()
    import uuid

    assert db.get(m.User, uuid.UUID(first["id"])).email_verified_at is not None
    assert db.get(m.User, uuid.UUID(second["id"])).email_verified_at is None


def test_reset_token_atomic_consumption_under_concurrent_requests(
    api_client, monkeypatch, tmp_path
):
    setup_mail(monkeypatch, tmp_path)
    account(api_client, "parallel@example.org")
    api_client.post("/api/v1/auth/password/request", json={"email": "parallel@example.org"})
    code = code_from_outbox(tmp_path, "reset")

    def attempt(_):
        return api_client.post(
            "/api/v1/auth/password/reset",
            json={
                "token": code,
                "password": "ReplacementSecure42!",
            },
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, range(2))) == [200, 400]


def test_verification_email_delivered_to_real_local_smtp(api_client, monkeypatch, db):
    import socket

    from aiosmtpd.controller import Controller

    class Sink:
        def __init__(self):
            self.messages = []

        async def handle_DATA(self, server, session, envelope):
            self.messages.append(envelope.original_content)
            return "250 Accepted"

    with socket.socket() as reserve:
        reserve.bind(("127.0.0.1", 0))
        port = reserve.getsockname()[1]
    sink = Sink()
    controller = Controller(sink, hostname="127.0.0.1", port=port)
    controller.start()
    try:
        for key, value in dict(
            SMTP_HOST="127.0.0.1",
            SMTP_PORT=str(port),
            SMTP_SECURITY="none",
            NOTIFIER_PROVIDER="smtp",
            REQUIRE_EMAIL_VERIFICATION="true",
        ).items():
            monkeypatch.setenv(key, value)
        get_settings.cache_clear()
        response = api_client.post(
            "/api/v1/auth/register",
            json={
                "email": "local-inbox@example.org",
                "password": PASSWORD,
            },
        )
        assert response.status_code == 201
        assert len(sink.messages) == 1
        message = BytesParser(policy=policy.default).parsebytes(sink.messages[0])
        code = re.search(
            r"single-use code in SubTrack: ([\w-]+)",
            message.get_body(preferencelist=("plain",)).get_content(),
        ).group(1)
        assert code not in response.text
        assert (
            api_client.post("/api/v1/auth/email/confirm", json={"token": code}).status_code == 200
        )
        assert "account_mail_sent" in list(db.scalars(select(m.SecurityEvent.kind)))
    finally:
        controller.stop()
