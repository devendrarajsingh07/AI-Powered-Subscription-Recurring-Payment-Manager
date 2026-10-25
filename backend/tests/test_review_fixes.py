"""Independent regressions for the October 25 review; real PostgreSQL and local HTTP only."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from conftest import alembic_config
from phase5_helpers import owner, plan
from sqlalchemy import text
from sqlalchemy.orm import Session
from test_api import account, load
from test_llm import client as gemini
from test_llm import server, tokens

from alembic import command
from app import models as m
from app import repositories as repo
from app.main import app
from app.services.alerts import generate
from app.services.llm import get_client
from app.services.pricing import billing_projection
from app.services.renewals import upcoming


def price_csv(n):
    amounts = [400, 400, 440, 440, 440]
    return (
        "date,description,amount,type\n"
        + "".join(
            f"2026-{i + 1:02d}-01,Netflix,{amount}.00,debit\n"
            for i, amount in enumerate(amounts[:n])
        )
    ).encode()


def test_new_billing_price_survives_a_resolved_increase_notice(api_client):
    headers, _ = account(api_client)
    for n in (3, 4, 5):
        load(api_client, headers, price_csv(n))
        summary = api_client.get("/api/v1/summary", headers=headers).json()
        assert summary["monthly_equivalent"] == "440.00"
        assert summary["yearly_total"] == "5280.00"
    sub = api_client.get("/api/v1/subscriptions", headers=headers).json()["items"][0]
    assert sub["avg_amount"] == "424.00"  # Historical mean remains accurate and visible.
    assert sub["billing_amount"] == "440.00" and sub["price_increase"] is None
    load(api_client, headers, price_csv(5))  # Dedupe and re-detection do not lose the projection.
    assert (
        api_client.get("/api/v1/summary", headers=headers).json()["monthly_equivalent"] == "440.00"
    )


def test_billing_projection_keeps_average_policy_for_usage_and_fx():
    assert billing_projection([Decimal(v) for v in ("100", "102", "99", "101")], 3) is None
    assert billing_projection([Decimal(v) for v in ("100", "100", "110", "99")], 3) is None
    assert billing_projection([Decimal("100"), Decimal("110")], 2) == Decimal("110")
    assert billing_projection([Decimal("100"), Decimal("110")], 3) is None
    assert billing_projection(
        [Decimal(v) for v in ("400", "400", "440", "440", "420")], 3
    ) == Decimal("420")
    assert billing_projection(
        [Decimal(v) for v in ("400", "400", "440", "441", "442", "439")], 3
    ) == Decimal("439")  # An established increase survives ordinary FX variation too.
    with pytest.raises(TypeError):
        billing_projection([1.0], 3)


def test_billing_migration_repairs_existing_history_and_preserves_decisions(api_client, pg_engine):
    headers, _ = account(api_client)
    load(api_client, headers, price_csv(5))
    sub = api_client.get("/api/v1/subscriptions", headers=headers).json()["items"][0]
    api_client.patch(
        "/api/v1/subscriptions/" + sub["id"],
        headers=headers,
        json={"user_confirmed": True, "category": "software"},
    )
    with pg_engine.begin() as db:
        command.downgrade(alembic_config(db), "0015_email_lifecycle")
        assert db.scalar(text("SELECT price_new_amount FROM subscriptions")) is None
        command.upgrade(alembic_config(db), "head")
    repaired = api_client.get("/api/v1/subscriptions/" + sub["id"], headers=headers).json()
    assert repaired["billing_amount"] == "440.00"
    assert repaired["user_confirmed"] and repaired["category"] == "software"


def test_renewal_alert_matches_calendar_projection_and_is_idempotent(db):
    user = owner(db)
    plan(db, user.id, last_charge=date(2026, 1, 31), next_expected=date(2026, 2, 28))
    db.commit()
    day = date(2026, 3, 28)
    visible = upcoming(db, user.id, days=7, as_of=day)
    assert len(visible) == 1 and visible[0].next_expected == date(2026, 3, 31)
    now = datetime(2026, 3, 28, tzinfo=timezone.utc)
    assert generate(db, user.id, as_of=day, now=now) == 1
    assert generate(db, user.id, as_of=day, now=now) == 0
    alert = repo.list_owned(db, user.id, m.Alert)[0]
    assert alert.send_on == day and alert.payload["renewal_date"] == "2026-03-31"


def test_two_missed_cycles_suppress_projected_alerts(db):
    user = owner(db)
    plan(db, user.id, last_charge=date(2026, 1, 31), next_expected=date(2026, 2, 28))
    assert (
        generate(
            db, user.id, as_of=date(2026, 4, 28), now=datetime(2026, 4, 28, tzinfo=timezone.utc)
        )
        == 0
    )


@pytest.mark.parametrize("mode", ["chat", "category"])
@pytest.mark.parametrize("remove_account", [False, True])
def test_provider_retry_rechecks_consent_and_account(
    api_client, pg_engine, db, mode, remove_account
):
    headers, user = account(api_client)
    user_id = uuid.UUID(user["id"])
    api_client.put("/api/v1/chat/config", headers=headers, json={"live_opt_in": True})
    category_id = None
    if mode == "category":
        plan(
            db, user_id, merchant="unmapped service", category="unknown", requires_confirmation=True
        )
        category_id = repo.category_cache(
            db, user_id, "unmapped service", "unknown", source="rule", confirmed=False
        ).id
        db.commit()

    def revoke():
        with Session(pg_engine) as session, session.begin():
            if remove_account:
                repo.delete_data(session, user_id)
            else:
                session.get(m.User, user_id).live_opt_in = False
        return []

    with server([(503, revoke), (200, tokens("I do not have that information."))]) as (
        url,
        requests,
    ):
        live = gemini(url)
        app.dependency_overrides[get_client] = lambda: live
        if mode == "chat":
            response = api_client.post(
                "/api/v1/chat", headers=headers, json={"message": "monthly total"}
            )
            assert response.status_code == 200
            assert "consent" in response.text.lower()
        else:
            response = api_client.post(f"/api/v1/categories/{category_id}/suggest", headers=headers)
            assert response.status_code == (401 if remove_account else 200)
        assert len(requests) == 1  # Retry was refused before network I/O.
