import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from phase5_helpers import DAY, owner, plan
from sqlalchemy.orm import Session
from test_api import DATA, account, expected_totals, load, subs

from app import models as m
from app import repositories as repo
from app.services.insights import regenerate


def expected_savings():
    truth = json.loads((DATA / "ground_truth.json").read_text())
    factors = dict(weekly=Decimal(52), monthly=Decimal(12), quarterly=Decimal(4), yearly=Decimal(1))
    results = {}
    for category in ("music", "streaming", "cloud"):
        amounts = [
            Decimal(p["avg_amount"]) * factors[p["cadence"]] / 12
            for p in truth["patterns"]
            if p["kind"] == "subscription" and p["category"] == category
        ]
        results[category] = (sum(amounts) - max(amounts)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    return results


def recs(client, headers):
    response = client.get("/api/v1/recommendations?limit=100", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["items"]


def test_uploaded_ground_truth_savings_and_accept_intent(api_client):
    headers, _ = account(api_client)
    load(api_client, headers)
    before = {row["id"]: row["status"] for row in subs(api_client, headers)}
    rows = recs(api_client, headers)
    duplicates = {row["members"][0]["category"]: row for row in rows if row["type"] == "duplicate"}
    expected = expected_savings()
    assert {category: row["est_monthly_saving"] for category, row in duplicates.items()} == {
        category: format(amount, ".2f") for category, amount in expected.items()
    }
    assert not [row for row in rows if row["type"] == "possibly_unused"]
    fixed = {row["id"] for row in subs(api_client, headers) if row["kind"] == "fixed_bill"}
    assert not fixed.intersection(
        member["subscription_id"] for row in rows for member in row["members"]
    )
    assert all(row["est_monthly_saving"] is None for row in rows if row["type"] != "duplicate")
    total = api_client.get("/api/v1/summary/savings", headers=headers).json()["potential_savings"]
    assert total == format(sum(expected.values()), ".2f")
    response = api_client.patch(
        f"/api/v1/recommendations/{duplicates['music']['id']}",
        headers=headers,
        json={"action": "accept"},
    )
    assert response.status_code == 200
    assert response.json()["accepted_at"]
    assert response.json()["status"] == "accepted"
    assert {row["id"]: row["status"] for row in subs(api_client, headers)} == before
    assert api_client.get("/api/v1/summary/savings", headers=headers).json()[
        "potential_savings"
    ] == format(sum(expected.values()) - expected["music"], ".2f")
    load(api_client, headers)
    assert (
        next(r for r in recs(api_client, headers) if r["id"] == duplicates["music"]["id"])["status"]
        == "accepted"
    )


def test_unchanged_regeneration_reupload_and_concurrency(api_client, pg_engine):
    headers, user = account(api_client)
    load(api_client, headers)
    initial = recs(api_client, headers)
    user_id = uuid.UUID(user["id"])

    def regenerate_once(_):
        with Session(pg_engine) as session, session.begin():
            regenerate(session, user_id, as_of=DAY)

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(regenerate_once, range(2)))
    assert recs(api_client, headers) == initial
    load(api_client, headers)
    assert recs(api_client, headers) == initial
    from app.clock import today
    from app.main import app

    app.dependency_overrides[today] = lambda: DAY + timedelta(days=1)
    load(api_client, headers)
    assert recs(api_client, headers) == initial


def test_dismissal_survives_resolution_and_material_changes_reopen(api_client, db):
    headers, user = account(api_client)
    load(api_client, headers)
    row = next(
        r
        for r in recs(api_client, headers)
        if r["type"] == "duplicate" and r["members"][0]["category"] == "music"
    )
    assert (
        api_client.patch(
            f"/api/v1/recommendations/{row['id']}", headers=headers, json={"action": "dismiss"}
        ).status_code
        == 200
    )
    sub_id = row["members"][0]["subscription_id"]
    api_client.patch(
        f"/api/v1/subscriptions/{sub_id}", headers=headers, json={"status": "cancelled"}
    )
    assert (
        next(r for r in recs(api_client, headers) if r["id"] == row["id"])["status"] == "resolved"
    )
    api_client.patch(f"/api/v1/subscriptions/{sub_id}", headers=headers, json={"status": "active"})
    assert (
        next(r for r in recs(api_client, headers) if r["id"] == row["id"])["status"] == "dismissed"
    )
    sub = repo.get_owned(db, uuid.UUID(user["id"]), m.Subscription, uuid.UUID(sub_id))
    sub.avg_amount += Decimal("1.00")
    regenerate(db, uuid.UUID(user["id"]), as_of=DAY)
    db.commit()
    changed = next(r for r in recs(api_client, headers) if r["id"] == row["id"])
    assert changed["status"] == "open"
    assert len([r for r in recs(api_client, headers) if r["id"] == row["id"]]) == 1


def test_last_used_user_signal_and_category_override_regenerate(api_client):
    headers, _ = account(api_client)
    load(api_client, headers)
    sub = next(s for s in subs(api_client, headers) if s["merchant"] == "spotify")
    api_client.patch(
        f"/api/v1/subscriptions/{sub['id']}",
        headers=headers,
        json={"last_used_at": (DAY - timedelta(days=61)).isoformat()},
    )
    assert any(
        r["type"] == "possibly_unused" and r["subscription_id"] == sub["id"]
        for r in recs(api_client, headers)
    )
    api_client.patch(
        f"/api/v1/subscriptions/{sub['id']}", headers=headers, json={"category": "rent"}
    )
    assert not [
        r
        for r in recs(api_client, headers)
        if r["status"] == "open"
        and any(member["subscription_id"] == sub["id"] for member in r["members"])
    ]


def test_large_duplicate_estimate_does_not_overflow_record_money(db):
    user = owner(db)
    for i in range(3):
        plan(db, user.id, amount="9999999999.99", category="cloud", merchant=f"synthetic {i}")
    regenerate(db, user.id, as_of=DAY)
    db.commit()
    rows = repo.list_owned(db, user.id, m.Recommendation, m.Recommendation.type == "duplicate")
    assert rows[0].est_monthly_saving == Decimal("19999999999.98")


def test_new_routes_scoped_strict_and_documented(api_client):
    a, _ = account(api_client)
    b, _ = account(api_client)
    load(api_client, b)
    row = recs(api_client, b)[0]
    assert recs(api_client, a) == []
    assert (
        api_client.patch(
            f"/api/v1/recommendations/{row['id']}", headers=a, json={"action": "dismiss"}
        ).status_code
        == 404
    )
    for body in (
        {"action": "cancel"},
        {"action": "accept", "user_id": "other"},
        {"status": "accepted"},
    ):
        assert (
            api_client.patch(
                f"/api/v1/recommendations/{row['id']}", headers=b, json=body
            ).status_code
            == 422
        )
    assert (
        api_client.put(
            "/api/v1/settings/alerts", headers=b, json={"notification_email": "notify@example.org"}
        ).status_code
        == 200
    )
    alert = api_client.get("/api/v1/alerts", headers=b).json()["items"][0]
    assert api_client.get(f"/api/v1/alerts/{alert['id']}", headers=a).status_code == 404
    assert api_client.get("/api/v1/alerts", headers=a).json()["total"] == 0
    spec = api_client.get("/api/v1/openapi.json").json()
    for route in (
        "/recommendations",
        "/recommendations/{recommendation_id}",
        "/alerts",
        "/alerts/{alert_id}",
        "/summary/savings",
    ):
        assert "/api/v1" + route in spec["paths"]


def test_budget_snapshot_matches_independent_ground_truth(api_client, db):
    headers, user = account(api_client)
    load(api_client, headers)
    response = api_client.put("/api/v1/budget", headers=headers, json={"monthly_limit": "1000.00"})
    assert response.status_code == 200
    patterns = json.loads((DATA / "ground_truth.json").read_text())["patterns"]
    expected_month, _ = expected_totals(patterns)
    alert = repo.list_owned(db, uuid.UUID(user["id"]), m.Alert, m.Alert.kind == "budget")[0]
    assert alert.payload["total"] == format(expected_month, ".2f")
    assert alert.payload["overage"] == format(expected_month - Decimal("1000.00"), ".2f")
    assert [row["merchant"] for row in alert.payload["contributors"]] == [
        "rent",
        "loan emi",
        "electricity",
    ]
