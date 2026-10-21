"""WP7: suppression, signed one-click unsubscribe, content-safe problem reports, legal version."""

import uuid

from phase5_helpers import owner
from test_api import account

from app import models as m
from app import repositories as repo
from app.config import get_settings
from app.services import email_lifecycle as lifecycle

TOKEN = "e" * 24 + "ops-events-synthetic-token-1234"


def user_row(db, user_id):
    db.expire_all()
    return db.get(m.User, user_id)


def test_signed_unsubscribe_turns_alerts_off_and_forged_links_do_nothing(api_client, db):
    row = owner(db)
    db.commit()
    url = f"/api/v1/alerts/unsubscribe?u={row.id}&t="
    bad = api_client.post(url + "0" * 64)
    assert bad.status_code == 200 and user_row(db, row.id).alerts_enabled is True
    other = api_client.post(
        f"/api/v1/alerts/unsubscribe?u={uuid.uuid4()}&t={lifecycle.sign(row.id)}"
    )
    assert other.status_code == 200 and user_row(db, row.id).alerts_enabled is True
    junk = api_client.post("/api/v1/alerts/unsubscribe?u=not-a-uuid&t=x")
    assert junk.status_code == 200 and junk.json() == bad.json()
    good = api_client.post(url + lifecycle.sign(row.id))
    assert good.status_code == 200 and good.json() == bad.json()  # No oracle for valid links.
    assert user_row(db, row.id).alerts_enabled is False
    assert api_client.post(url + lifecycle.sign(row.id)).status_code == 200  # Idempotent.


def test_email_events_need_the_ops_token_and_suppress_matching_accounts(
    api_client, db, monkeypatch
):
    row = owner(db, notification_email="Bounce@Example.org")
    other = owner(db, notification_email="fine@example.org")
    db.commit()
    body = dict(address="bounce@example.org", kind="hard_bounce")
    assert api_client.post("/api/v1/ops/email-events", json=body).status_code == 404
    assert api_client.post("/api/v1/ops/email-events").status_code == 404  # No body oracle.
    monkeypatch.setenv("OPS_METRICS_TOKEN", TOKEN)
    get_settings.cache_clear()
    assert api_client.post("/api/v1/ops/email-events", json=body).status_code == 404
    done = api_client.post("/api/v1/ops/email-events", json=body, headers={"X-Ops-Token": TOKEN})
    assert done.status_code == 200 and done.json() == dict(suppressed_accounts=1)
    assert user_row(db, row.id).alerts_suppressed_reason == "hard_bounce"
    assert user_row(db, other.id).alerts_suppressed_reason is None
    bad_kind = dict(address="bounce@example.org", kind="opened")
    assert (
        api_client.post(
            "/api/v1/ops/email-events", json=bad_kind, headers={"X-Ops-Token": TOKEN}
        ).status_code
        == 422
    )


def test_suppressed_address_skips_alerts_and_new_address_clears_suppression(api_client, db):
    headers, user = account(api_client)
    uid = uuid.UUID(user["id"])
    settings = api_client.put(
        "/api/v1/settings/alerts",
        headers=headers,
        json=dict(enabled=True, lead_time_days=3, notification_email="bounced@example.org"),
    )
    assert settings.status_code == 200, settings.text
    assert lifecycle.suppress(db, "bounced@example.org", "complaint") == 1
    db.commit()
    shown = api_client.get("/api/v1/settings/alerts", headers=headers).json()
    assert shown["suppressed_reason"] == "complaint"
    same = api_client.put(
        "/api/v1/settings/alerts",
        headers=headers,
        json=dict(enabled=True, lead_time_days=5, notification_email="bounced@example.org"),
    )
    assert same.json()["suppressed_reason"] == "complaint"
    changed = api_client.put(
        "/api/v1/settings/alerts",
        headers=headers,
        json=dict(enabled=True, lead_time_days=5, notification_email="new@example.org"),
    )
    assert changed.json()["suppressed_reason"] is None
    assert user_row(db, uid).alerts_suppressed_at is None


def test_problem_reports_reject_financial_content_and_are_rate_limited(api_client, db, monkeypatch):
    monkeypatch.setenv("SUPPORT_REPORTS_PER_DAY", "2")
    get_settings.cache_clear()
    headers, user = account(api_client)
    url = "/api/v1/support/reports"
    assert api_client.post(url, json=dict(category="bug", message="short")).status_code in (
        401,
        422,
    )
    for text in (
        "my card 4111 1111 1111 1111 failed",
        "I paid Rs. 499 twice",
        "ref 12345678 odd",
    ):
        denied = api_client.post(url, headers=headers, json=dict(category="bug", message=text))
        assert denied.status_code == 422, text
        assert denied.json()["error"]["code"] == "sensitive_content"
    ok = dict(category="data_issue", message="The renewal date on one plan looks wrong")
    first = api_client.post(url, headers=headers, json=ok)
    assert first.status_code == 201 and first.json()["received"] is True
    assert api_client.post(url, headers=headers, json=ok).status_code == 201
    limited = api_client.post(url, headers=headers, json=ok)
    assert limited.status_code == 429
    assert repo.count_owned(db, uuid.UUID(user["id"]), m.SupportReport) == 2


def test_legal_acceptance_is_recorded_and_required_only_when_enabled(api_client, db, monkeypatch):
    config = api_client.get("/api/v1/auth/config").json()
    assert config["legal_acceptance_required"] is False
    monkeypatch.setenv("LEGAL_VERSION", "draft-1")
    monkeypatch.setenv("LEGAL_ACCEPTANCE_REQUIRED", "true")
    get_settings.cache_clear()
    config = api_client.get("/api/v1/auth/config").json()
    assert config["legal_version"] == "draft-1" and config["legal_acceptance_required"] is True
    body = dict(email=f"legal-{uuid.uuid4().hex}@example.org", password="Correct-Horse-9-Battery")
    missing = api_client.post("/api/v1/auth/register", json=body)
    assert missing.status_code == 400 and missing.json()["error"]["code"] == "terms_required"
    wrong = api_client.post("/api/v1/auth/register", json=dict(body, accepted_terms_version="x"))
    assert wrong.status_code == 400
    ok = api_client.post("/api/v1/auth/register", json=dict(body, accepted_terms_version="draft-1"))
    assert ok.status_code == 201, ok.text
    row = user_row(db, uuid.UUID(ok.json()["id"]))
    assert row.terms_version == "draft-1" and row.terms_accepted_at is not None
