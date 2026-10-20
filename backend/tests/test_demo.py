import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from test_api import account, expected_totals, load, subs, wait

from app import models as m
from app import repositories as repo
from app.config import Settings, get_settings
from app.services.demo import dataset
from scripts.seed_demo import seed


def demo_load(client, headers):
    started = client.post("/api/v1/demo/load", headers=headers)
    assert started.status_code == 202, started.text
    result, _ = wait(client, headers, started.json()["id"])
    assert result["status"] == "done", result
    return result


@pytest.mark.parametrize(
    "as_of", [date(2026, 10, 18), date(2027, 2, 28), date(2028, 2, 29), date(2029, 1, 1)]
)
def test_relative_generator_deterministic_and_independent_labels(as_of):
    from app.services.demo import MAPPING
    from app.services.detector import detect_recurring
    from app.services.ingestion import parse_csv

    first, truth = dataset(as_of)
    assert (first, truth) == dataset(as_of)
    assert truth["as_of"] == str(as_of)
    detections = detect_recurring(parse_csv(first, MAPPING).transactions, as_of=as_of)
    assert len(detections) == len(truth["patterns"]) == 16


def test_demo_real_pipeline_idempotency_defaults_and_removal(api_client, db):
    headers, user = account(api_client)
    result = demo_load(api_client, headers)
    assert result["source"] == "demo" and result["demo_as_of"] == "2026-10-18"
    _, truth = dataset(date(2026, 10, 18))
    assert result["detected_count"] == len(truth["patterns"]) == 16
    expected = expected_totals(truth["patterns"])
    summary = api_client.get("/api/v1/summary", headers=headers).json()
    assert Decimal(summary["monthly_equivalent"]) == expected[0]
    before = subs(api_client, headers)
    assert demo_load(api_client, headers)["id"] == result["id"]
    assert subs(api_client, headers) == before
    assert api_client.get("/api/v1/budget", headers=headers).json()["monthly_limit"] == str(
        expected[0] - Decimal(100)
    )
    assert (
        api_client.get("/api/v1/settings/alerts", headers=headers).json()["notification_email"]
        == "demo@example.org"
    )
    # Opposite-direction mixing is also refused; deletion restores empty account, not logout.
    response = api_client.post(
        "/api/v1/uploads",
        headers=headers,
        files={"file": ("x.csv", dataset(date(2026, 10, 18))[0])},
        data={
            "mapping": '{"date":"date","description":"description","amount":"amount","type":"type"}'
        },
    )
    assert response.status_code == 409
    response = api_client.delete("/api/v1/demo/data", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["deleted"]["uploads"] == 1
    assert subs(api_client, headers) == []
    assert api_client.get("/api/v1/auth/me", headers=headers).status_code == 200
    assert (
        api_client.get("/api/v1/settings/alerts", headers=headers).json()["notification_email"]
        is None
    )
    assert api_client.get("/api/v1/budget", headers=headers).json()["monthly_limit"] is None
    assert api_client.delete("/api/v1/demo/data", headers=headers).json()["deleted"]["uploads"] == 0
    load(api_client, headers)
    assert api_client.post("/api/v1/demo/load", headers=headers).status_code == 409


def test_demo_removal_does_not_touch_other_user_or_real_uploads(api_client):
    a, _ = account(api_client)
    b, _ = account(api_client)
    demo_load(api_client, a)
    real = load(api_client, b)
    assert api_client.delete("/api/v1/demo/data", headers=b).json()["deleted"]["uploads"] == 0
    assert api_client.delete("/api/v1/demo/data", headers=a).status_code == 200
    assert len(subs(api_client, b)) == 16
    assert api_client.get(f"/api/v1/uploads/{real['id']}", headers=b).status_code == 200


def test_concurrent_demo_load_reuses_one_upload(api_client):
    headers, _ = account(api_client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda _: api_client.post("/api/v1/demo/load", headers=headers), range(2))
        )
    assert all(r.status_code == 202 for r in results)
    assert len({r.json()["id"] for r in results}) == 1
    assert wait(api_client, headers, results[0].json()["id"])[0]["status"] == "done"


def test_demo_user_preferences_survive_removal(api_client):
    headers, _ = account(api_client)
    demo_load(api_client, headers)
    api_client.put("/api/v1/budget", headers=headers, json={"monthly_limit": "123.45"})
    api_client.put(
        "/api/v1/settings/alerts",
        headers=headers,
        json={"lead_time_days": 4, "notification_email": "chosen@example.org", "enabled": True},
    )
    assert api_client.delete("/api/v1/demo/data", headers=headers).status_code == 200
    assert api_client.get("/api/v1/budget", headers=headers).json()["monthly_limit"] == "123.45"
    assert (
        api_client.get("/api/v1/settings/alerts", headers=headers).json()["notification_email"]
        == "chosen@example.org"
    )


def test_seed_reuses_real_pipeline_and_is_idempotent(pg_engine, db):
    first = seed(pg_engine, as_of=date(2026, 10, 18))
    assert seed(pg_engine, as_of=date(2026, 10, 19)) == first
    user = db.scalar(select(m.User).where(m.User.email == "subtrack-demo@example.org"))
    assert repo.count_owned(db, user.id, m.Subscription) == 16
    assert repo.count_owned(db, user.id, m.Upload) == 1


def test_dev_demo_credential_and_existing_tokens_never_work_outside_dev(api_client, monkeypatch):
    headers, _ = account(api_client, email="subtrack-demo@example.org")
    monkeypatch.setattr(get_settings(), "environment", "production")
    assert api_client.get("/api/v1/auth/me", headers=headers).status_code == 401
    from test_api import PASSWORD

    response = api_client.post(
        "/api/v1/auth/login", json={"email": "subtrack-demo@example.org", "password": PASSWORD}
    )
    assert response.status_code == 401
    response = api_client.post(
        "/api/v1/auth/register", json={"email": "subtrack-demo@example.org", "password": PASSWORD}
    )
    assert response.status_code == 403


def test_demo_disabled_and_rate_limited(api_client, monkeypatch):
    headers, _ = account(api_client)
    monkeypatch.setattr(get_settings(), "demo_enabled", False)
    assert api_client.post("/api/v1/demo/load", headers=headers).status_code == 404
    monkeypatch.setattr(get_settings(), "demo_enabled", True)
    monkeypatch.setattr(get_settings(), "auth_login_limit", 1)
    assert api_client.post("/api/v1/demo/load", headers=headers).status_code == 202
    assert api_client.post("/api/v1/demo/load", headers=headers).status_code == 429


def production(**extra):
    return Settings(
        _env_file=None,
        environment="production",
        app_test_as_of="",
        demo_enabled=False,
        registration_mode="closed",
        notifier_provider="smtp",
        web_origin="https://subtrack.example.org",
        jwt_secret=secrets.token_urlsafe(48),
        **extra,
    )


@pytest.mark.parametrize(
    "field,value",
    [("demo_enabled", True), ("app_test_as_of", "2026-10-18"), ("notifier_provider", "console")],
)
def test_production_guards(field, value):
    values = dict(
        environment="production",
        app_test_as_of="",
        demo_enabled=False,
        registration_mode="closed",
        notifier_provider="smtp",
        web_origin="https://subtrack.example.org",
        jwt_secret=secrets.token_urlsafe(48),
    )
    values[field] = value
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_production_valid_and_no_adversarial_or_seed(monkeypatch):
    cfg = production()
    monkeypatch.setattr("app.config.get_settings", lambda: cfg)
    from app.services.llm.fake import FakeLLM

    with pytest.raises(RuntimeError, match="test-only"):
        FakeLLM(fabricate=True)
    monkeypatch.setattr("scripts.seed_demo.get_settings", lambda: cfg)
    with pytest.raises(RuntimeError, match="development"):
        seed()
    monkeypatch.setattr("app.jobs.get_settings", lambda: cfg)
    from app.jobs import run_jobs

    with pytest.raises(RuntimeError, match="simulated"):
        run_jobs(None, as_of=date(2026, 10, 18))
    monkeypatch.setattr("app.services.notifier.get_settings", lambda: cfg)
    from app.services.notifier import ConsoleNotifier, DeliveryError

    with pytest.raises(DeliveryError):
        ConsoleNotifier(cfg.outbox_dir).send(None)


@pytest.mark.parametrize(
    "secret", ["a" * 50, "replace-with-a-random-secret-at-least-32-characters", "short"]
)
def test_non_development_weak_jwt_fails(secret):
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            environment="test",
            jwt_secret=secret,
            web_origin="http://localhost:5173",
        )


def test_explicit_cors_and_security_headers(api_client, monkeypatch):
    monkeypatch.delenv("WEB_ORIGIN", raising=False)
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            environment="test",
            jwt_secret=secrets.token_urlsafe(48),
        )
    response = api_client.get("/api/v1/health/ready")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
