"""Synthetic EML fixtures and real PostgreSQL pipeline; no Gmail or external service calls."""

import json
import socket
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from test_api import account, load, wait

from app import models as m
from app.config import Settings, get_settings
from app.services.email_receipts import MAX_BYTES, ReceiptError, parse_receipt
from app.services.llm import LLMError
from app.services.llm_controls import guard_user
from app.statement_jobs import now

DATA = Path(__file__).resolve().parents[1] / "data" / "receipts"
TRUTH = json.loads((DATA / "ground_truth.json").read_text(encoding="utf-8"))


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv("RECEIPT_IMPORT_ENABLED", "true")
    monkeypatch.setenv("AUTH_LOGIN_LIMIT", "1000")
    get_settings.cache_clear()


def preview(client, headers, name="netflix-1.eml", data=None):
    return client.post(
        "/api/v1/receipts/preview",
        headers=headers,
        files={
            "file": (
                name,
                data if data is not None else (DATA / name).read_bytes(),
                "message/rfc822",
            )
        },
    )


def confirm(client, headers, row, edits=None):
    return client.post(
        "/api/v1/uploads",
        headers=headers,
        data={
            "preview_id": row["id"],
            "edits": json.dumps(edits if edits is not None else [{"index": 0, "verified": True}]),
        },
    )


@pytest.mark.parametrize("name", sorted(TRUTH["cases"]))
def test_independently_labelled_mime_fields(name):
    expected = TRUTH["cases"][name]
    if expected["verdict"] == "reject":
        with pytest.raises(ReceiptError) as error:
            parse_receipt((DATA / name).read_bytes())
        assert error.value.code == expected["error"]
        return
    result = parse_receipt((DATA / name).read_bytes())
    row = result["rows"][0]
    assert {k: row[k] for k in ("date", "description", "amount", "type")} == {
        k: expected[k] for k in ("date", "description", "amount", "type")
    }
    assert "email_review_required" in row["flags"] and result["flagged_count"] == 1
    serialized = json.dumps(result)
    assert "example.org" not in serialized and "never-fetch.invalid" not in serialized
    assert "IGNORE ALL RULES" not in serialized and "<script" not in serialized
    if row["amount"] is not None:
        assert isinstance(row["amount"], str)


def test_bounded_mime_and_plaintext_precedence():
    for data, code in (
        (b"", "empty_receipt"),
        (b"x" * (MAX_BYTES + 1), "receipt_too_large"),
        (b"broken", "invalid_receipt"),
        (b"Subject: x\n" + b"Content-Type: text/plain\n" * 40 + b"\nbody", "receipt_too_complex"),
    ):
        with pytest.raises(ReceiptError) as error:
            parse_receipt(data)
        assert error.value.code == code
    message = EmailMessage()
    message.set_content(
        "Merchant: Netflix\nPayment status: Paid\nPayment date: 2026-09-01\nAmount paid: INR 499.00"
    )
    message.add_alternative("<p>Amount paid: INR 99999</p>", subtype="html")
    assert parse_receipt(message.as_bytes())["rows"][0]["amount"] == "499.00"
    padded = EmailMessage()
    padded.set_content(
        "\n" * 60000 + "Merchant: Netflix\nPayment status: Paid\n"
        "Payment date: 2026-09-01\nAmount paid: INR 499.00"
    )
    assert parse_receipt(padded.as_bytes())["rows"][0]["amount"] == "499.00"
    for _ in range(7):
        parent = EmailMessage()
        parent.make_mixed()
        parent.attach(message)
        message = parent
    with pytest.raises(ReceiptError, match="nesting"):
        parse_receipt(message.as_bytes())


@pytest.mark.parametrize(
    "value,expected",
    [
        ("\u20b91,499.50", "1499.50"),
        ("INR 1,23,456.78", "123456.78"),
        ("199 INR", "199.00"),
        ("Rs. 199.00", "199.00"),
    ],
)
def test_decimal_currency_and_indian_grouping(value, expected):
    data = (
        "Content-Type: text/plain; charset=utf-8\n\nMerchant: Netflix\n"
        "Payment status: Paid\nPayment date: 2026-09-01\nAmount paid: " + value
    ).encode()
    assert parse_receipt(data)["rows"][0]["amount"] == expected


def test_html_never_fetches_remote_resources(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Receipt parser attempted a network connection")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    assert parse_receipt((DATA / "hostile-html.eml").read_bytes())["rows"][0]["amount"] == "49.99"


def test_formula_unknown_merchant_and_bad_grouping_remain_unverified():
    data = (
        b"Content-Type: text/plain; charset=utf-8\n\nMerchant: =IGNORE INSTRUCTIONS\n"
        b"Payment status: Paid\nPayment date: 2026-09-01\nAmount paid: INR 1,99.00\n"
    )
    row = parse_receipt(data)["rows"][0]
    assert row["description"] == "" and row["amount"] is None
    assert "missing_or_ambiguous_merchant" in row["flags"]


def test_real_receipt_upload_detect_summary_replay_and_delete(api_client, enabled, db):
    headers, user = account(api_client)
    originals = []
    for name, expected in TRUTH["cases"].items():
        if not expected.get("detect"):
            continue
        response = preview(api_client, headers, name)
        assert response.status_code == 200, response.text
        row = response.json()
        assert row["status"] == "ready" and row["source_type"] == "email_receipt"
        assert db.scalar(select(func.count()).select_from(m.Transaction)) == len(originals)
        upload = confirm(api_client, headers, row)
        assert upload.status_code == 202, upload.text
        result, _ = wait(api_client, headers, upload.json()["id"])
        assert result["status"] == "done" and result["inserted_count"] == 1
        assert confirm(api_client, headers, row).json()["id"] == result["id"]
        originals.append((name, expected))
    subscriptions = api_client.get("/api/v1/subscriptions", headers=headers).json()["items"]
    assert sorted((s["merchant"], s["cadence"], s["avg_amount"]) for s in subscriptions) == sorted(
        (p["merchant"], p["cadence"], p["avg_amount"]) for p in TRUTH["patterns"]
    )
    # Independent arithmetic from plan labels, never the summary/detection implementation.
    factors = {"monthly": Decimal(12), "yearly": Decimal(1)}
    annual = sum(Decimal(p["avg_amount"]) * factors[p["cadence"]] for p in TRUTH["patterns"])
    monthly = (annual / Decimal(12)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    summary = api_client.get("/api/v1/summary", headers=headers).json()
    assert summary["monthly_equivalent"] == str(monthly)
    assert summary["yearly_total"] == format(annual, ".2f")
    before = {(s["id"], s["avg_amount"]) for s in subscriptions}
    for name, _ in originals:
        row = preview(api_client, headers, name).json()
        result, _ = wait(api_client, headers, confirm(api_client, headers, row).json()["id"])
        assert result["inserted_count"] == 0 and result["duplicate_count"] == 1
    assert {
        (s["id"], s["avg_amount"])
        for s in api_client.get("/api/v1/subscriptions", headers=headers).json()["items"]
    } == before
    assert db.scalar(select(func.count()).select_from(m.Transaction)) == len(originals)
    stored = db.scalars(select(m.StatementPreview)).all()
    assert all(row.payload == {} for row in stored)  # Confirm consumes temporary extracted data.
    assert api_client.delete("/api/v1/me/data", headers=headers).status_code == 200
    assert db.scalar(select(func.count()).select_from(m.StatementPreview)) == 0
    assert api_client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_review_isolation_cancellation_expiry_and_content_privacy(api_client, enabled, db, caplog):
    headers, _ = account(api_client)
    other, _ = account(api_client)
    assert (
        api_client.post(
            "/api/v1/receipts/preview",
            headers=headers,
            files={"file": ("receipt.eml", (DATA / "netflix-1.eml").read_bytes())},
            data={"user_id": "forbidden"},
        ).status_code
        == 422
    )
    row = preview(api_client, headers).json()
    assert "fixture-only" not in json.dumps(row) and "billing.example.org" not in json.dumps(row)
    assert confirm(api_client, headers, row, []).status_code == 422
    assert (
        confirm(
            api_client, headers, row, [{"index": 0, "verified": True, "user_id": "x"}]
        ).status_code
        == 422
    )
    path = "/api/v1/uploads/previews/" + row["id"]
    assert api_client.get(path, headers=other).status_code == 404
    assert api_client.delete(path, headers=other).status_code == 404
    assert confirm(api_client, other, row).status_code == 404
    assert api_client.delete(path, headers=headers).json()["status"] == "cancelled"
    assert confirm(api_client, headers, row).status_code == 409
    row = preview(api_client, headers).json()
    record = db.get(m.StatementPreview, row["id"])
    record.expires_at = now() - timedelta(seconds=1)
    db.commit()
    assert (
        api_client.get("/api/v1/uploads/previews/" + row["id"], headers=headers).status_code == 404
    )
    assert "Amount paid" not in caplog.text and "billing.example.org" not in caplog.text


def test_both_mixing_directions_and_queued_receipt_exclusion(api_client, enabled):
    bank, _ = account(api_client)
    load(api_client, bank)
    assert preview(api_client, bank).status_code == 409
    email, _ = account(api_client)
    row = preview(api_client, email).json()
    assert confirm(api_client, email, row).status_code == 202
    # Existing financial intake checks source before dispatch, including pending uploads.
    response = api_client.post(
        "/api/v1/uploads",
        headers=email,
        files={
            "file": ("bank.csv", b"date,description,amount,type\n2026-09-01,Netflix,499,debit\n")
        },
        data={"mapping": json.dumps({k: k for k in ("date", "description", "amount", "type")})},
    )
    assert (
        response.status_code == 409
        and response.json()["error"]["code"] == "receipt_source_conflict"
    )


def test_missing_fields_need_correction_and_float_money_is_rejected(api_client, enabled):
    headers, _ = account(api_client)
    row = preview(api_client, headers, "ambiguous-amount.eml").json()
    assert confirm(api_client, headers, row).status_code == 422
    assert (
        confirm(
            api_client, headers, row, [{"index": 0, "verified": True, "amount": 499.0}]
        ).status_code
        == 422
    )
    response = confirm(
        api_client, headers, row, [{"index": 0, "verified": True, "amount": "499.00"}]
    )
    assert response.status_code == 202
    assert wait(api_client, headers, response.json()["id"])[0]["inserted_count"] == 1


def test_feature_off_public_guard_and_production_fail_closed(api_client, monkeypatch):
    monkeypatch.setenv("RECEIPT_IMPORT_ENABLED", "false")
    get_settings.cache_clear()
    assert preview(api_client, {}).status_code == 404
    monkeypatch.setenv("RECEIPT_IMPORT_ENABLED", "true")
    monkeypatch.setenv("PUBLIC_DEMO_ONLY", "true")
    monkeypatch.setenv("AUTH_SESSION_MODE", "demo")
    get_settings.cache_clear()
    assert preview(api_client, {}).status_code == 403
    with pytest.raises(ValidationError, match="Receipt-import foundation is development-only"):
        Settings(environment="production", receipt_import_enabled=True)


def test_receipt_workspace_cannot_send_derived_data_to_a_live_provider(
    api_client, enabled, db, pg_engine
):
    headers, user = account(api_client)
    row = preview(api_client, headers).json()
    response = confirm(api_client, headers, row)
    wait(api_client, headers, response.json()["id"])
    owner = db.get(m.User, user["id"])
    owner.live_opt_in = True
    db.commit()
    with pytest.raises(LLMError, match="offline-only"):
        guard_user(pg_engine, SimpleNamespace(live=True), 100, owner.id)
    assert db.scalar(select(func.count()).select_from(m.LlmUsage)) == 0


def test_durable_confirm_queue_real_worker_and_input_purge(
    api_client, enabled, monkeypatch, pg_engine, db
):
    from app.durable_worker import Dispatcher, Worker
    from app.main import app
    from app.services.durable_queue import unseal
    from app.uploads import get_worker

    monkeypatch.setenv("JOB_MODE", "postgres")
    get_settings.cache_clear()
    app.dependency_overrides[get_worker] = lambda: Dispatcher(pg_engine)
    headers, _ = account(api_client)
    for name in ("netflix-1.eml", "netflix-2.eml", "netflix-3.eml"):
        row = preview(api_client, headers, name).json()
        response = confirm(api_client, headers, row)
        assert response.status_code == 202 and response.json()["status"] == "pending"
        job = api_client.get("/api/v1/jobs", headers=headers).json()["items"][0]
        assert job["status"] == "queued"
        queued = db.scalar(
            select(m.DurableJob).where(m.DurableJob.upload_id == response.json()["id"])
        )
        csv_data, _ = unseal(queued.encrypted_input)
        assert csv_data.startswith(b"date,description,amount,type")
        assert b"example.org" not in csv_data and b"Subject:" not in csv_data
        assert Worker(pg_engine).run_once()
        result = api_client.get("/api/v1/uploads/" + response.json()["id"], headers=headers).json()
        assert result["status"] == "done" and result["inserted_count"] == 1
    assert (
        api_client.get("/api/v1/summary", headers=headers).json()["monthly_equivalent"] == "499.00"
    )
    db.expire_all()
    assert all(job.encrypted_input is None for job in db.scalars(select(m.DurableJob)))
    assert db.scalar(select(func.count()).select_from(m.Transaction)) == 3


def test_preview_rate_and_ready_capacity_are_enforced(api_client, enabled, monkeypatch):
    headers, _ = account(api_client)
    monkeypatch.setenv("AUTH_LOGIN_LIMIT", "1")
    get_settings.cache_clear()
    assert preview(api_client, headers).status_code == 200
    assert preview(api_client, headers).status_code == 429
    monkeypatch.setenv("AUTH_LOGIN_LIMIT", "1000")
    monkeypatch.setenv("STATEMENT_CONCURRENT_LIMIT", "1")
    get_settings.cache_clear()
    assert preview(api_client, headers).json()["error"]["code"] == "preview_busy"


def test_invalid_file_limits_and_public_body_is_never_read(api_client, enabled, monkeypatch):
    import asyncio

    from app.main import app

    headers, _ = account(api_client)
    assert preview(api_client, headers, data=b"").status_code == 422
    assert preview(api_client, headers, data=b"x" * (MAX_BYTES + 1)).status_code == 413
    assert (
        preview(
            api_client, headers, "wrong.txt", data=(DATA / "netflix-1.eml").read_bytes()
        ).status_code
        == 422
    )
    monkeypatch.setenv("PUBLIC_DEMO_ONLY", "true")
    monkeypatch.setenv("AUTH_SESSION_MODE", "demo")
    get_settings.cache_clear()
    sent = []

    async def receive():
        pytest.fail("Public-demo receipt body must not be consumed")

    async def send(message):
        sent.append(message)

    asyncio.run(
        app(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/v1/receipts/preview",
                "headers": [],
                "query_string": b"",
                "scheme": "https",
            },
            receive,
            send,
        )
    )
    assert sent[0]["status"] == 403


def test_daily_quota_and_disable_after_preview_cannot_bypass_review(
    api_client, enabled, monkeypatch
):
    headers, _ = account(api_client)
    row = preview(api_client, headers).json()
    monkeypatch.setenv("STATEMENT_DAILY_LIMIT", "1")
    get_settings.cache_clear()
    assert preview(api_client, headers).json()["error"]["code"] == "preview_quota"
    monkeypatch.setenv("RECEIPT_IMPORT_ENABLED", "false")
    get_settings.cache_clear()
    assert confirm(api_client, headers, row).status_code == 404
    assert api_client.get("/api/v1/uploads", headers=headers).json()["total"] == 0


def test_synthetic_fixture_headers_and_manifest_only():
    assert {p.name for p in DATA.glob("*.eml")} == set(TRUTH["cases"])
    for name in TRUTH["cases"]:
        message = BytesParser().parsebytes((DATA / name).read_bytes())
        addresses = getaddresses(
            [message[key] for key in ("From", "To", "Cc", "Bcc") if message[key]]
        )
        assert addresses
        assert all(
            address.rsplit("@", 1)[-1] == "example.org"
            or address.rsplit("@", 1)[-1].endswith(".example.org")
            for _, address in addresses
        )


def test_concurrent_bank_and_receipt_admission_never_mix(api_client, enabled):
    from concurrent.futures import ThreadPoolExecutor

    headers, _ = account(api_client)
    row = preview(api_client, headers).json()

    def bank():
        return api_client.post(
            "/api/v1/uploads",
            headers=headers,
            files={
                "file": (
                    "bank.csv",
                    b"date,description,amount,type\n2026-09-01,Netflix,499,debit\n",
                )
            },
            data={"mapping": json.dumps({k: k for k in ("date", "description", "amount", "type")})},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(bank), pool.submit(confirm, api_client, headers, row)
        responses = [a.result(), b.result()]
    assert sorted(response.status_code for response in responses) == [202, 409]
    accepted = next(response.json() for response in responses if response.status_code == 202)
    assert wait(api_client, headers, accepted["id"])[0]["inserted_count"] == 1
    uploads = api_client.get("/api/v1/uploads", headers=headers).json()
    assert uploads["total"] == 1


@pytest.mark.parametrize("flag,public,provider,expected", [
    (False, False, "fake", False),
    (True, False, "fake", True),
    (True, True, "fake", False),
    (True, False, "gemini", False),
])
def test_receipt_ui_capability_fails_closed(
    api_client, monkeypatch, flag, public, provider, expected
):
    from app.api import account as routes
    cfg = SimpleNamespace(public_demo_only=public, receipt_import_enabled=flag,
                          environment="development", llm_provider=provider,
                          auth_session_mode="demo", legal_version="draft",
                          legal_acceptance_required=False)
    monkeypatch.setattr(routes, "get_settings", lambda: cfg)
    response = api_client.get("/api/v1/auth/config")
    assert response.status_code == 200
    assert response.json()["receipt_import_enabled"] is expected
