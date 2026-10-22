import inspect
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from threading import Event

import jwt
import pytest
from sqlalchemy import func, select

from app import models as m
from app import repositories as repo
from app.auth import limiter
from app.config import get_settings

DATA = Path(__file__).resolve().parents[1] / "data"
PASSWORD = "ExampleSecure42!"
MAPPING = {"date": "date", "description": "description", "amount": "amount", "type": "type"}


def account(client, email=None):
    email = email or f"test-{uuid.uuid4().hex}@example.org"
    response = client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})
    assert response.status_code == 201, response.text
    user = response.json()
    token = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert token.status_code == 200, token.text
    return {"Authorization": "Bearer " + token.json()["access_token"]}, user


def submit(client, headers, data=None, mapping=None):
    response = client.post(
        "/api/v1/uploads",
        headers=headers,
        files={
            "file": (
                "synthetic.csv",
                data if data is not None else (DATA / "sample_transactions.csv").read_bytes(),
                "text/csv",
            )
        },
        data={"mapping": json.dumps(mapping or MAPPING)},
    )
    assert response.status_code == 202, response.text
    assert response.json()["status"] == "pending"
    return response.json()


def wait(client, headers, upload_id):
    deadline = time.monotonic() + 20
    statuses = set()
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/uploads/{upload_id}", headers=headers)
        assert response.status_code == 200, response.text
        result = response.json()
        statuses.add(result["status"])
        if result["status"] in ("done", "failed"):
            return result, statuses
        time.sleep(0.01)
    pytest.fail("Upload did not finish within the test deadline")


def load(client, headers, data=None, mapping=None):
    upload = submit(client, headers, data, mapping)
    result, _ = wait(client, headers, upload["id"])
    assert result["status"] == "done", result
    return result


def subs(client, headers):
    response = client.get("/api/v1/subscriptions?limit=100", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["items"]


def expected_totals(patterns, kind=None):
    # Independent arithmetic from labels, never uses service code or detector output.
    factors = {
        "weekly": Decimal(52),
        "monthly": Decimal(12),
        "quarterly": Decimal(4),
        "yearly": Decimal(1),
    }
    yearly = sum(
        (
            Decimal(p["new_amount"] if p.get("price_increase") else p["avg_amount"])
            * factors[p["cadence"]]
            for p in patterns
            if kind is None or p["kind"] == kind
        ),
        Decimal(0),
    )
    return (
        (yearly / 12).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        yearly.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
    )


def test_happy_path_and_independent_summary(api_client, db):
    headers, user = account(api_client)
    csv = (DATA / "sample_transactions.csv").read_bytes()
    preview = api_client.post(
        "/api/v1/uploads/preview", headers=headers, files={"file": ("sample.csv", csv, "text/csv")}
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["delimiter"] == ","
    assert "YYYY-MM-DD" in preview.json()["date_formats"]
    assert preview.json()["warnings"] == []
    assert db.scalar(select(func.count()).select_from(m.Transaction)) == 0
    upload = load(api_client, headers, csv, preview.json()["suggested_mapping"])
    assert upload["inserted_count"] == 399
    assert upload["processed_rows"] == upload["total_rows"] == 399
    found = subs(api_client, headers)
    truth = json.loads((DATA / "ground_truth.json").read_text())["patterns"]
    assert len(found) == len(truth) == 16
    expected = {(p["merchant"], p["cadence"], p["avg_amount"], p["kind"]) for p in truth}
    actual = {(p["merchant"], p["cadence"], p["avg_amount"], p["kind"]) for p in found}
    assert actual == expected
    for row in found:
        assert isinstance(row["avg_amount"], str)
        assert row["next_expected"] >= "2026-10-18"
    summary = api_client.get("/api/v1/summary", headers=headers)
    assert summary.status_code == 200, summary.text
    body = summary.json()
    monthly, yearly = expected_totals(truth)
    assert Decimal(body["monthly_equivalent"]) == monthly
    assert Decimal(body["yearly_total"]) == yearly
    for kind, key in (("subscription", "subscriptions"), ("fixed_bill", "fixed_bills")):
        month, year = expected_totals(truth, kind)
        assert Decimal(body[key]["monthly_equivalent"]) == month
        assert Decimal(body[key]["yearly_total"]) == year
    assert body["subscriptions"]["count"] == 12
    assert body["fixed_bills"]["count"] == 4
    assert api_client.get("/api/v1/summary?period=year", headers=headers).json()[
        "period_total"
    ] == str(yearly)
    assert all(isinstance(tx.amount, Decimal) for tx in db.scalars(select(m.Transaction)))
    stored = db.get(m.User, uuid.UUID(user["id"]))
    assert stored.password_hash.startswith("$2b$") and stored.password_hash != PASSWORD


def test_repeat_upload_and_decisions_survive(api_client, db):
    headers, _ = account(api_client)
    load(api_client, headers)
    before = subs(api_client, headers)
    decisions = [
        (before[0], {"user_confirmed": True, "category": "news", "last_used_at": "2026-10-01"}),
        (before[1], {"status": "dismissed"}),
        (before[2], {"status": "cancelled"}),
    ]
    for record, change in decisions:
        response = api_client.patch(
            f"/api/v1/subscriptions/{record['id']}", headers=headers, json=change
        )
        assert response.status_code == 200, response.text
    first_count = db.scalar(select(func.count()).select_from(m.Transaction))
    result = load(api_client, headers)
    assert result["inserted_count"] == 0
    assert result["duplicate_count"] == 399
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(m.Transaction)) == first_count
    after = {p["id"]: p for p in subs(api_client, headers)}
    assert set(after) == {p["id"] for p in before}
    for original, change in decisions:
        for key, value in change.items():
            assert after[original["id"]][key] == value
    assert after[before[2]["id"]]["cancelled_at"] is not None


def test_concurrent_duplicate_uploads(api_client, db):
    headers, _ = account(api_client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        submitted = list(pool.map(lambda _: submit(api_client, headers), range(2)))
    results = [wait(api_client, headers, item["id"])[0] for item in submitted]
    assert all(item["status"] == "done" for item in results), results
    assert sorted(item["inserted_count"] for item in results) == [0, 399]
    assert db.scalar(select(func.count()).select_from(m.Transaction)) == 399
    assert len(subs(api_client, headers)) == 16


def test_user_isolation_and_delete_account_cascades(api_client, db):
    a, user_a = account(api_client)
    b, user_b = account(api_client)
    upload_b = load(api_client, b)
    sub_b = subs(api_client, b)[0]
    assert api_client.get(f"/api/v1/uploads/{upload_b['id']}", headers=a).status_code == 404
    assert api_client.get(f"/api/v1/subscriptions/{sub_b['id']}", headers=a).status_code == 404
    assert (
        api_client.patch(
            f"/api/v1/subscriptions/{sub_b['id']}", headers=a, json={"status": "cancelled"}
        ).status_code
        == 404
    )
    assert api_client.delete(f"/api/v1/uploads/{upload_b['id']}", headers=a).status_code in (
        404,
        405,
    )
    assert api_client.get("/api/v1/uploads", headers=a).json()["total"] == 0
    assert api_client.get("/api/v1/subscriptions", headers=a).json()["total"] == 0
    assert api_client.get("/api/v1/summary", headers=a).json()["monthly_equivalent"] == "0.00"
    assert (
        api_client.put("/api/v1/budget", headers=b, json={"monthly_limit": "4000.00"}).status_code
        == 200
    )
    assert api_client.get("/api/v1/budget", headers=a).json()["monthly_limit"] is None
    assert (
        api_client.put("/api/v1/budget", headers=a, json={"monthly_limit": "100.00"}).status_code
        == 200
    )
    assert api_client.get("/api/v1/budget", headers=b).json()["monthly_limit"] == "4000.00"
    assert (
        api_client.put(
            "/api/v1/settings/alerts",
            headers=b,
            json={
                "lead_time_days": 7,
                "notification_email": "b-notify@example.org",
                "enabled": False,
            },
        ).status_code
        == 200
    )
    assert api_client.get("/api/v1/settings/alerts", headers=a).json()["lead_time_days"] == 3
    load(api_client, a)
    # Seed only schema-only Phase 5/6 tables to verify cascading privacy deletion.
    uid = uuid.UUID(user_a["id"])
    with db.begin_nested():
        repo.create_owned(db, uid, m.ChatMessage, role="user", content="Synthetic privacy fixture")
        repo.create_owned(
            db, uid, m.Alert, kind="budget", send_on=date(2026, 10, 1), channel="email", payload={}
        )
        repo.create_owned(
            db,
            uid,
            m.Recommendation,
            type="high_cost",
            message="Synthetic fixture",
            est_monthly_saving=Decimal("0.00"),
        )
    db.commit()
    response = api_client.delete("/api/v1/me/data", headers=a)
    assert response.status_code == 200, response.text
    assert response.json()["deleted"]["transactions"] == 399
    for table in m.Base.metadata.sorted_tables:
        if "user_id" in table.c:
            assert (
                db.scalar(select(func.count()).select_from(table).where(table.c.user_id == uid))
                == 0
            )
    assert db.get(m.User, uid) is None
    assert api_client.get("/api/v1/auth/me", headers=a).status_code == 401
    assert api_client.get("/api/v1/auth/me", headers=b).json()["id"] == user_b["id"]
    assert len(subs(api_client, b)) == 16


@pytest.mark.parametrize(
    "filename,expected_count,skipped",
    [("handwritten_bank.csv", 3, 3), ("handwritten_products.csv", 5, 0)],
)
def test_handwritten_exports_full_pipeline(api_client, filename, expected_count, skipped):
    headers, _ = account(api_client)
    data = (DATA / filename).read_bytes()
    preview = api_client.post(
        "/api/v1/uploads/preview", headers=headers, files={"file": (filename, data)}
    )
    assert preview.status_code == 200, preview.text
    result = load(api_client, headers, data, preview.json()["suggested_mapping"])
    assert result["malformed_count"] == skipped
    assert len(subs(api_client, headers)) == expected_count


@pytest.mark.parametrize(
    "data,status",
    [
        (b"", 422),
        (b"\xff", 422),
        (b"x" * (5 * 1024 * 1024 + 1), 413),
        (b"date,description,amount,type\n" + b"2026-01-01,A,1,debit\n" * 50001, 422),
        (b"date,description\n2026-01-01,Netflix\n", 422),
    ],
)
def test_malformed_uploads_are_safe(api_client, data, status):
    headers, _ = account(api_client)
    response = api_client.post(
        "/api/v1/uploads",
        headers=headers,
        files={"file": ("bad.csv", data)},
        data={"mapping": json.dumps(MAPPING)},
    )
    assert response.status_code == status, response.text
    assert set(response.json()) == {"error"}
    assert "bad.csv" not in response.json()["error"]["message"]
    assert api_client.get("/api/v1/uploads", headers=headers).json()["total"] == 0


def test_broken_quoting_and_formula_prefix(api_client, db):
    headers, _ = account(api_client)
    data = (
        b"date,description,amount,type\n2026-01-01,=UNKNOWN SERVICE,100,debit\n"
        b"2026-01-31,=UNKNOWN SERVICE,100,debit\n2026-03-02,=UNKNOWN SERVICE,100,debit\n"
        b'2026-04-01,"unclosed,100,debit\n'
    )
    preview = api_client.post(
        "/api/v1/uploads/preview", headers=headers, files={"file": ("formulas.csv", data)}
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["malformed_csv"]
    assert preview.json()["rows"][0][1] == "UNKNOWN SERVICE"
    result = load(api_client, headers, data)
    assert result["malformed_count"] == 1
    assert "unreadable" in result["remainder_notice"]
    record = subs(api_client, headers)[0]
    confirmed = api_client.patch(
        f"/api/v1/subscriptions/{record['id']}", headers=headers, json={"user_confirmed": True}
    )
    assert not confirmed.json()["requires_confirmation"]
    unconfirmed_record = api_client.patch(
        f"/api/v1/subscriptions/{record['id']}", headers=headers, json={"user_confirmed": False}
    )
    assert unconfirmed_record.json()["requires_confirmation"]
    detail = api_client.get(f"/api/v1/subscriptions/{record['id']}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["charges"][0]["description"] == "UNKNOWN SERVICE"
    assert db.scalar(select(m.Transaction.raw_description).limit(1)).startswith("=")
    unconfirmed = api_client.get("/api/v1/categories/unconfirmed", headers=headers).json()["items"]
    assert len(unconfirmed) == 1
    other_headers, _ = account(api_client)
    assert (
        api_client.patch(
            f"/api/v1/categories/{unconfirmed[0]['id']}",
            headers=other_headers,
            json={"category": "software"},
        ).status_code
        == 404
    )
    assert (
        api_client.patch(
            f"/api/v1/categories/{unconfirmed[0]['id']}",
            headers=headers,
            json={"category": "software"},
        ).status_code
        == 200
    )
    load(api_client, headers, data)
    assert subs(api_client, headers)[0]["category"] == "software"
    assert api_client.get("/api/v1/categories/unconfirmed", headers=headers).json()["total"] == 0


def test_auth_normalization_errors_tokens_and_rate_limit(api_client, monkeypatch):
    headers, user = account(api_client, "  Mixed.Case@EXAMPLE.ORG  ")
    assert user["email"] == "mixed.case@example.org"
    duplicate = api_client.post(
        "/api/v1/auth/register", json={"email": "mixed.case@example.org", "password": PASSWORD}
    )
    assert duplicate.status_code == 409
    wrong = api_client.post(
        "/api/v1/auth/login", json={"email": user["email"], "password": "wrong"}
    )
    missing = api_client.post(
        "/api/v1/auth/login", json={"email": "missing@example.org", "password": "wrong"}
    )
    assert wrong.status_code == missing.status_code == 401
    assert wrong.json() == missing.json()
    config = get_settings()
    expired = jwt.encode(
        {
            "sub": user["id"],
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "iss": config.jwt_issuer,
            "aud": config.jwt_audience,
        },
        config.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )
    assert (
        api_client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer " + expired}
        ).status_code
        == 401
    )
    assert (
        api_client.get("/api/v1/auth/me", headers={"Authorization": "Bearer forged"}).status_code
        == 401
    )
    assert api_client.get("/api/v1/auth/me").status_code == 401
    monkeypatch.setenv("AUTH_LOGIN_LIMIT", "2")
    monkeypatch.setenv("AUTH_REGISTER_LIMIT", "2")
    get_settings.cache_clear()
    limiter.clear()
    for path in ("login", "register"):
        for index in range(2):
            body = {"email": f"rate{index}@example.org", "password": PASSWORD}
            assert api_client.post("/api/v1/auth/" + path, json=body).status_code != 429
        limited = api_client.post(
            "/api/v1/auth/" + path, json={"email": "rate-next@example.org", "password": PASSWORD}
        )
        assert limited.status_code == 429
        assert limited.json()["error"]["code"] == "rate_limited"


@pytest.mark.parametrize(
    "change",
    [
        {"avg_amount": "1.00"},
        {"user_id": str(uuid.uuid4())},
        {"last_used_at": "2099-01-01"},
        {"status": "other"},
        {},
    ],
)
def test_strict_patch(api_client, change):
    headers, _ = account(api_client)
    load(api_client, headers)
    record = subs(api_client, headers)[0]
    response = api_client.patch(
        f"/api/v1/subscriptions/{record['id']}", headers=headers, json=change
    )
    assert response.status_code == 422


@pytest.mark.parametrize("value", [1.25, 100, "-1.00", "1.001", "1e3", "NaN"])
def test_budget_requires_nonnegative_decimal_strings(api_client, value):
    headers, _ = account(api_client)
    assert (
        api_client.put("/api/v1/budget", headers=headers, json={"monthly_limit": value}).status_code
        == 422
    )


def test_rounding_and_trend_from_independent_labels(api_client):
    headers, _ = account(api_client)
    load(api_client, headers)
    truth = json.loads((DATA / "ground_truth.json").read_text())
    expected, _ = expected_totals(truth["patterns"])
    assert api_client.get("/api/v1/summary", headers=headers).json()["monthly_equivalent"] == str(
        expected
    )
    result = api_client.get("/api/v1/summary/trend?months=12", headers=headers)
    assert result.status_code == 200, result.text
    assert len(result.json()["months"]) == 12
    assert result.json()["months"][-1]["month"] == "2026-10"
    assert all(isinstance(point["total"], str) for point in result.json()["months"])
    renewals = api_client.get("/api/v1/renewals/upcoming?days=30&limit=100", headers=headers)
    assert renewals.status_code == 200, renewals.text
    assert any(item["possibly_cancelled"] for item in renewals.json()["items"])
    assert all(item["status"] == "active" for item in renewals.json()["items"])


def test_progress_and_atomic_failure(api_client, isolated_app, monkeypatch, db):
    headers, _ = account(api_client)
    entered, resume = Event(), Event()
    original = repo.redetect

    def paused_failure(session, user_id, *, as_of):
        entered.set()
        assert resume.wait(timeout=10)
        raise RuntimeError("Synthetic failure, never log this")

    monkeypatch.setattr(repo, "redetect", paused_failure)
    pending = submit(api_client, headers)
    assert pending["status"] == "pending"
    assert entered.wait(timeout=10)
    processing = api_client.get(f"/api/v1/uploads/{pending['id']}", headers=headers).json()
    assert processing["status"] == "processing"
    assert processing["stage"] == "detecting"
    assert processing["processed_rows"] == 399
    # Uncommitted financial writes are not visible to another connection.
    assert db.scalar(select(func.count()).select_from(m.Transaction)) == 0
    resume.set()
    result, _ = wait(api_client, headers, pending["id"])
    assert result["status"] == "failed"
    assert result["inserted_count"] == 0
    db.rollback()
    assert db.scalar(select(func.count()).select_from(m.Transaction)) == 0
    assert db.scalar(select(func.count()).select_from(m.Subscription)) == 0
    monkeypatch.setattr(repo, "redetect", original)
    assert load(api_client, headers)["inserted_count"] == 399


def test_repository_functions_require_user_scope():
    functions = [
        fn
        for name, fn in vars(repo).items()
        if inspect.isfunction(fn) and fn.__module__ == repo.__name__ and not name.startswith("_")
    ]
    assert functions
    assert all("user_id" in inspect.signature(fn).parameters for fn in functions)


def test_price_change_preserves_stable_identity_and_decisions(api_client):
    headers, _ = account(api_client)
    first = (
        b"date,description,amount,type\n2026-01-01,SPOTIFY REF1,100,debit\n"
        b"2026-01-31,SPOTIFY REF2,100,debit\n2026-03-02,SPOTIFY REF3,100,debit\n"
    )
    load(api_client, headers, first)
    before = subs(api_client, headers)[0]
    assert (
        api_client.patch(
            f"/api/v1/subscriptions/{before['id']}",
            headers=headers,
            json={"user_confirmed": True, "category": "news"},
        ).status_code
        == 200
    )
    expanded = first + b"2026-04-01,SPOTIFY REF4,120,debit\n"
    result = load(api_client, headers, expanded)
    (after,) = subs(api_client, headers)
    assert result["inserted_count"] == 1
    assert after["id"] == before["id"]
    assert after["avg_amount"] == "105.00"
    assert after["user_confirmed"] and after["category"] == "news"
    assert after["price_increase"]["previous_amount"] == "100.00"
    assert after["price_increase"]["new_amount"] == "120.00"


def test_large_aggregate_is_not_limited_to_per_record_numeric(api_client):
    headers, _ = account(api_client)
    rows = ["date,description,amount,type"]
    for merchant in ("ACME SERVICE", "OTHER SERVICE"):
        for day in ("2026-01-01", "2026-01-31", "2026-03-02"):
            rows.append(f"{day},{merchant},9999999999.99,debit")
    load(api_client, headers, ("\n".join(rows) + "\n").encode())
    response = api_client.get("/api/v1/summary", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["monthly_equivalent"] == "19999999999.98"
    trend_response = api_client.get("/api/v1/summary/trend", headers=headers)
    assert trend_response.status_code == 200, trend_response.text


@pytest.mark.parametrize("password", ["short", "abcdefghijklmn", "A1!" * 30, "Ab1" + "é" * 40])
def test_password_strength_and_utf8_byte_bound(api_client, password):
    response = api_client.post(
        "/api/v1/auth/register", json={"email": "weak@example.org", "password": password}
    )
    assert response.status_code == 422
    assert password not in response.text
    if len(password.encode()) > 72:
        login = api_client.post(
            "/api/v1/auth/login", json={"email": "weak@example.org", "password": password}
        )
        assert login.status_code == 422


def test_invalid_auth_bodies_are_rate_limited_too(api_client, monkeypatch):
    monkeypatch.setenv("AUTH_LOGIN_LIMIT", "2")
    get_settings.cache_clear()
    for _ in range(2):
        assert api_client.post("/api/v1/auth/login", json={}).status_code == 422
    assert api_client.post("/api/v1/auth/login", json={}).status_code == 429


def test_queue_bound_releases_reservation(api_client, isolated_app):
    headers, _ = account(api_client)
    reservations = 0
    while isolated_app.reserve():
        reservations += 1
    response = api_client.post(
        "/api/v1/uploads",
        headers=headers,
        files={"file": ("sample.csv", (DATA / "sample_transactions.csv").read_bytes())},
        data={"mapping": json.dumps(MAPPING)},
    )
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "upload_queue_full"
    for _ in range(reservations):
        isolated_app.release()
    assert load(api_client, headers)["status"] == "done"


def test_interrupted_uploads_recovered_as_failed(api_client, db, isolated_app):
    headers, user = account(api_client)
    uid = uuid.UUID(user["id"])
    record = repo.create_owned(db, uid, m.Upload, filename="synthetic.csv", status="processing")
    db.commit()
    isolated_app.recover()
    result = api_client.get(f"/api/v1/uploads/{record.id}", headers=headers)
    assert result.json()["status"] == "failed"
    assert "interrupted" in result.json()["error_message"]


def test_logs_never_include_private_csv_values(api_client, caplog, monkeypatch):
    headers, _ = account(api_client)
    marker = "PRIVATE_UNTRUSTED_DESCRIPTION"
    data = f"date,description,amount,type\n2026-01-01,{marker},123.45,debit\n".encode()

    def error(db, user_id, **kwargs):
        raise RuntimeError(marker + " 123.45")

    monkeypatch.setattr(repo, "redetect", error)
    result = submit(api_client, headers, data)
    done, _ = wait(api_client, headers, result["id"])
    assert done["status"] == "failed"
    assert marker not in caplog.text and "123.45" not in caplog.text


def test_filters_pagination_and_settings_validation(api_client):
    headers, _ = account(api_client)
    load(api_client, headers)
    first = api_client.get("/api/v1/subscriptions?kind=fixed_bill&limit=2", headers=headers).json()
    second = api_client.get(
        "/api/v1/subscriptions?kind=fixed_bill&limit=2&offset=2", headers=headers
    ).json()
    assert first["total"] == second["total"] == 4
    assert not ({p["id"] for p in first["items"]} & {p["id"] for p in second["items"]})
    music = api_client.get(
        "/api/v1/subscriptions?category=music&cadence=monthly&status=active", headers=headers
    )
    assert music.json()["total"] == 2
    assert (
        api_client.get("/api/v1/subscriptions?sort=raw_description", headers=headers).status_code
        == 422
    )
    assert (
        api_client.put(
            "/api/v1/budget", headers=headers, json={"monthly_limit": "0.00"}
        ).status_code
        == 200
    )
    for days in (0, 31, True):
        assert (
            api_client.put(
                "/api/v1/settings/alerts", headers=headers, json={"lead_time_days": days}
            ).status_code
            == 422
        )


def test_preview_accepts_unknown_columns_for_mapping_step(api_client):
    headers, _ = account(api_client)
    data = b"When,What,Value,Direction\n2026-01-01,Netflix,199,debit\n"
    response = api_client.post(
        "/api/v1/uploads/preview", headers=headers, files={"file": ("custom.csv", data)}
    )
    assert response.status_code == 200, response.text
    assert response.json()["suggested_mapping"] == {}
    assert response.json()["warnings"]


def test_no_llm_or_create_all_and_all_business_routes_are_protected():
    import ast

    from app.main import app

    for path in (Path(__file__).resolve().parents[1] / "app").rglob("*.py"):
        tree = ast.parse(path.read_text())
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "create_all"
            for node in ast.walk(tree)
        )
    for path, methods in app.openapi()["paths"].items():
        if path.startswith("/api/v1/health") or path in (
            "/api/v1/auth/register",
            "/api/v1/auth/login",
            "/api/v1/auth/config",
            "/api/v1/auth/demo",
            "/api/v1/auth/email/request",
            "/api/v1/auth/email/confirm",
            "/api/v1/auth/password/request",
            "/api/v1/auth/password/reset",
            "/api/v1/alerts/unsubscribe",  # Signed one-click link; no session by design.
        ):
            continue
        for operation in methods.values():
            assert operation["security"], path


def test_new_upload_can_queue_while_prior_detection_holds_user_lock(api_client, monkeypatch):
    headers, _ = account(api_client)
    entered, resume = Event(), Event()
    original = repo.redetect
    calls = 0

    def paused_once(db, user_id, *, as_of):
        nonlocal calls
        calls += 1
        if calls == 1:
            entered.set()
            assert resume.wait(timeout=10)
        return original(db, user_id, as_of=as_of)

    monkeypatch.setattr(repo, "redetect", paused_once)
    first = submit(api_client, headers)
    assert entered.wait(timeout=10)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(submit, api_client, headers)
            second = future.result(timeout=3)
    finally:
        resume.set()
    assert wait(api_client, headers, first["id"])[0]["status"] == "done"
    assert wait(api_client, headers, second["id"])[0]["inserted_count"] == 0


def test_confirming_unknown_merchant_as_fixed_bill_survives_detection(api_client):
    headers, _ = account(api_client)
    data = (
        b"date,description,amount,type\n2026-01-01,HOUSING SERVICE,1000,debit\n"
        b"2026-01-31,HOUSING SERVICE,1000,debit\n2026-03-02,HOUSING SERVICE,1000,debit\n"
    )
    load(api_client, headers, data)
    cache = api_client.get("/api/v1/categories/unconfirmed", headers=headers).json()["items"][0]
    assert (
        api_client.patch(
            f"/api/v1/categories/{cache['id']}", headers=headers, json={"category": "rent"}
        ).status_code
        == 200
    )
    load(api_client, headers, data)
    (found,) = subs(api_client, headers)
    assert found["kind"] == "fixed_bill" and found["category"] == "rent"
    summary = api_client.get("/api/v1/summary", headers=headers).json()
    assert summary["subscriptions"]["count"] == 0
    assert summary["fixed_bills"]["count"] == 1


def test_post_commit_logging_failure_does_not_relabel_saved_upload_as_failed(
    api_client, monkeypatch, isolated_app
):
    from app.uploads import logger

    headers, _ = account(api_client)

    def logging_error(*args, **kwargs):
        raise RuntimeError("Synthetic logging handler failure")

    monkeypatch.setattr(logger, "info", logging_error)
    pending = submit(api_client, headers)
    isolated_app.close()
    result, _ = wait(api_client, headers, pending["id"])
    assert result["status"] == "done"
    assert result["inserted_count"] == 399
