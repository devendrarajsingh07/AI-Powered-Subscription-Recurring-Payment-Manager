"""Public-host controls are enforced by the API, including direct/chunked file requests."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app import models as m
from app.auth import DEV_DEMO_EMAIL, hash_password
from app.config import Settings, get_settings
from app.services.demo_retention import purge_demo_accounts
from app.services.notifier import ConsoleNotifier, Mail


def public_mode(monkeypatch):
    monkeypatch.setenv("PUBLIC_DEMO_ONLY", "true")
    monkeypatch.setenv("AUTH_SESSION_MODE", "demo")
    get_settings.cache_clear()


def visitor(client):
    response = client.post("/api/v1/auth/demo")
    assert response.status_code == 200, response.text
    assert "set-cookie" not in response.headers
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_public_demo_disposable_isolation_no_refresh_or_shared_login(api_client, monkeypatch, db):
    public_mode(monkeypatch)
    first, second = visitor(api_client), visitor(api_client)
    a = api_client.get("/api/v1/auth/me", headers=first).json()
    b = api_client.get("/api/v1/auth/me", headers=second).json()
    assert a["id"] != b["id"] and a["email"].endswith("@example.org")
    assert db.scalar(select(func.count()).select_from(m.RefreshToken)) == 0
    assert (
        api_client.post(
            "/api/v1/auth/login",
            json={
                "email": DEV_DEMO_EMAIL,
                "password": "SubTrackDemo2026!",
            },
        ).status_code
        == 403
    )
    assert (
        api_client.post(
            "/api/v1/auth/register",
            json={
                "email": "person@example.org",
                "password": "SyntheticVisitor42!",
            },
        ).status_code
        == 403
    )
    assert (
        api_client.post(
            "/api/v1/auth/refresh",
            headers={
                "Origin": get_settings().web_origin,
                "X-CSRF-Token": "anything",
            },
        ).status_code
        == 401
    )
    api_client.put("/api/v1/budget", headers=first, json={"monthly_limit": "99.00"})
    assert api_client.get("/api/v1/budget", headers=second).json()["monthly_limit"] is None


@pytest.mark.parametrize("extension", ["csv", "pdf", "png"])
@pytest.mark.parametrize("path", ["/uploads", "/uploads/preview"])
def test_public_demo_refuses_upload_before_body_parsing(api_client, monkeypatch, extension, path):
    public_mode(monkeypatch)
    headers = visitor(api_client)
    response = api_client.post(
        "/api/v1" + path, headers=headers, files={"file": ("private." + extension, b"not parsed")}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "demo_data_only"
    # Even malformed multipart and oversized chunked bytes never reach parsing/extraction.
    response = api_client.post("/api/v1" + path, headers=headers, content=iter([b"x"] * 3))
    assert response.status_code == 403


def test_demo_expiry_purges_only_disposable_and_shared_local_account(
    api_client,
    monkeypatch,
    db,
    pg_engine,
    tmp_path,
    capsys,
):
    monkeypatch.setenv("OUTBOX_DIR", str(tmp_path))
    ordinary = m.User(email="local@example.org", password_hash=hash_password("SyntheticVisitor42!"))
    shared = m.User(email=DEV_DEMO_EMAIL, password_hash=ordinary.password_hash)
    db.add_all([ordinary, shared])
    db.commit()
    keep = ordinary.id
    public_mode(monkeypatch)
    token = visitor(api_client)
    user_id = api_client.get("/api/v1/auth/me", headers=token).json()["id"]
    import uuid

    disposable = db.get(m.User, uuid.UUID(user_id))
    disposable.demo_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    disposable_id = disposable.id
    from email.message import EmailMessage

    transport = ConsoleNotifier(tmp_path)
    message = EmailMessage()
    message.set_content("Synthetic lifecycle verification only")
    kept_mail_id = uuid.uuid4()
    transport.send(Mail(keep, kept_mail_id, "demo@example.org", message))
    transport.send(Mail(disposable_id, uuid.uuid4(), "demo@example.org", message))
    assert len(list(tmp_path.rglob("*.eml"))) == 2
    assert api_client.get("/api/v1/auth/me", headers=token).status_code == 401
    assert purge_demo_accounts(pg_engine) == 2
    import json

    report = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert report == {"event": "public_demo_purge", "shared_before": 1, "removed": 2}
    assert purge_demo_accounts(pg_engine) == 0
    db.expire_all()
    assert db.get(m.User, keep) is not None
    assert db.get(m.User, disposable_id) is None
    assert len(list(tmp_path.rglob("*.eml"))) == 1
    assert transport.delivered(keep, kept_mail_id)
    assert not transport.user_directory(disposable_id).exists()


def test_config_public_demo_fail_closed(monkeypatch):
    for changes in (
        {"llm_provider": "gemini"},
        {"auth_session_mode": "strict"},
        {"notifier_provider": "smtp"},
        {"require_email_verification": True},
    ):
        with pytest.raises(ValidationError):
            Settings(
                _env_file=None,
                **dict(
                    {
                        "public_demo_only": True,
                        "auth_session_mode": "demo",
                    },
                    **changes,
                ),
            )


@pytest.mark.parametrize(
    "changes",
    [
        {"public_demo_only": True},
        {"auth_session_mode": "demo"},
        {"web_origin": "https://app.vercel.app", "api_origin": "https://api.onrender.com"},
        {"auth_cookie_site": "onrender.com"},
        {"api_origin": "https://api.unrelated.org"},
    ],
)
def test_production_rejects_demo_or_cross_site_session_configuration(changes, monkeypatch):
    import secrets

    monkeypatch.delenv("REGISTRATION_MODE", raising=False)
    values = dict(
        environment="production",
        jwt_secret=secrets.token_urlsafe(48),
        web_origin="https://app.example.org",
        api_origin="https://api.example.org",
        auth_cookie_site="example.org",
        demo_enabled=False,
        app_test_as_of="",
        notifier_provider="smtp",
    )
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **dict(values, **changes))


def test_shared_seed_forbidden_on_public_demo(monkeypatch):
    from scripts.seed_demo import seed

    public_mode(monkeypatch)
    with pytest.raises(RuntimeError, match="local development"):
        seed()


def test_public_demo_purge_is_scheduled_even_when_email_schedule_is_disabled(
    monkeypatch, pg_engine
):
    from app.scheduler import start_scheduler

    public_mode(monkeypatch)
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    get_settings.cache_clear()
    scheduler = start_scheduler(pg_engine)
    try:
        jobs = scheduler.get_jobs()
        assert [job.id for job in jobs] == ["purge-disposable-demos"]
        assert jobs[0].trigger.interval.total_seconds() == 900
    finally:
        scheduler.shutdown(wait=True)


@pytest.mark.parametrize(
    "web,api,site,expected",
    [
        ("https://app.example.org", "https://api.example.org", "example.org", True),
        ("https://app.example.co.uk", "https://api.example.co.uk", "example.co.uk", True),
        ("https://app.github.io", "https://api.github.io", "github.io", False),
        ("https://app.vercel.app", "https://api.onrender.com", "vercel.app", False),
        ("https://app.example.org.evil.com", "https://api.example.org", "example.org", False),
        ("https://app.example.org/path", "https://api.example.org", "example.org", False),
        ("https://app.example.org", "http://api.example.org", "example.org", False),
    ],
)
def test_public_suffix_same_site_validation(web, api, site, expected):
    from app.sites import same_site_siblings

    assert same_site_siblings(web, api, site) is expected
