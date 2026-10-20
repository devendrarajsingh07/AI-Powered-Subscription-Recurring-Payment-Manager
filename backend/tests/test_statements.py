"""Real local extraction, PostgreSQL review/ingestion and bounded-parser security."""

import io
import json
import time
import uuid
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from pypdf import PdfWriter
from test_api import account, subs, wait

from app import models as m
from app import repositories as repo
from app.config import get_settings
from app.services.extraction_runner import run_extraction
from app.services.statement_extraction import ExtractionError, reconcile, reconstruct, sniff
from app.statement_jobs import now

DATA = Path(__file__).resolve().parents[1] / "data/extraction"
PASSWORD = "FixtureOnly42!"


def preview(client, headers, name="text_single.pdf", *, password="", data=None):
    response = client.post(
        "/api/v1/uploads/preview",
        headers=headers,
        files={"file": (name, data if data is not None else (DATA / name).read_bytes())},
        data={"password": password},
    )
    assert response.status_code == 202, response.text
    return response.json()


def ready(client, headers, preview_id):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        response = client.get("/api/v1/uploads/previews/" + preview_id, headers=headers)
        assert response.status_code == 200, response.text
        job = response.json()
        if job["status"] in ("ready", "failed", "cancelled"):
            return job
        time.sleep(0.03)
    pytest.fail("Real preview did not finish within its test deadline")


def confirm(client, headers, job, edits=None):
    edits = (
        edits
        if edits is not None
        else [dict(index=row["index"], verified=True) for row in job["result"]["rows"]]
    )
    return client.post(
        "/api/v1/uploads",
        headers=headers,
        data={"preview_id": job["id"], "edits": json.dumps(edits)},
    )


def test_text_pdf_real_review_ingestion_exact_ground_truth_and_reconfirm(api_client, db):
    headers, user = account(api_client)
    pending = preview(api_client, headers)
    assert pending["status"] == "pending" and pending["result"] is None
    job = ready(api_client, headers, pending["id"])
    assert job["status"] == "ready", job
    truth = json.loads((DATA / "manifest.json").read_text())["variants"][0]["rows"]
    extracted = job["result"]["rows"]
    assert len(extracted) == len(truth) == 399
    for expected, row in zip(truth, extracted):
        assert (row["date"], row["description"], Decimal(row["amount"]), row["type"]) == (
            expected["date"],
            expected["description"],
            Decimal(expected["amount"]),
            expected["type"],
        )
        assert row["flags"] and isinstance(row["amount"], str)
    result = confirm(api_client, headers, job)
    assert result.status_code == 202, result.text
    upload, _ = wait(api_client, headers, result.json()["id"])
    assert upload["status"] == "done" and upload["inserted_count"] == 399
    assert upload["source_type"] == "pdf_text" and upload["excluded_count"] == 0
    expected = json.loads((DATA.parent / "ground_truth.json").read_text())["patterns"]
    assert sorted((row["merchant"], row["cadence"]) for row in subs(api_client, headers)) == sorted(
        (row["merchant"], row["cadence"]) for row in expected
    )
    repeated = confirm(api_client, headers, job)
    assert repeated.status_code == 202 and repeated.json()["id"] == upload["id"]
    stored = repo.get_owned(db, uuid.UUID(user["id"]), m.StatementPreview, uuid.UUID(job["id"]))
    assert stored.payload == {}
    assert repo.count_owned(db, uuid.UUID(user["id"]), m.Transaction) == 399


@pytest.mark.parametrize("name", ["scanned.pdf", "scan_200_q90.jpg", "clean.png"])
def test_real_ocr_requires_review_and_reuses_upload_pipeline(api_client, name):
    headers, _ = account(api_client)
    job = ready(api_client, headers, preview(api_client, headers, name)["id"])
    assert job["status"] == "ready", job
    assert len(job["result"]["rows"]) == 15
    assert all(row["flags"] and row["field_confidence"] for row in job["result"]["rows"])
    response = confirm(api_client, headers, job)
    assert response.status_code == 202, response.text
    upload, _ = wait(api_client, headers, response.json()["id"])
    assert upload["status"] == "done" and upload["inserted_count"] == 15
    assert len(subs(api_client, headers)) == 5


@pytest.mark.parametrize(
    "password,code", [("", "password_required"), ("incorrect", "wrong_password")]
)
def test_encrypted_pdf_clean_password_failures(api_client, db, password, code, caplog):
    headers, user = account(api_client)
    job = ready(
        api_client, headers, preview(api_client, headers, "encrypted.pdf", password=password)["id"]
    )
    assert job["status"] == "failed" and job["error_code"] == code
    assert "incorrect" not in json.dumps(job) and "incorrect" not in caplog.text
    assert repo.count_owned(db, uuid.UUID(user["id"]), m.Transaction) == 0


def test_password_temp_files_and_credentials_absent_after_real_subprocess(
    tmp_path, monkeypatch, caplog
):
    import app.services.extraction_runner as runner

    monkeypatch.setattr(runner.tempfile, "tempdir", str(tmp_path))
    original = runner.subprocess.Popen
    observed = []

    def record(*args, **kwargs):
        observed.append((args, kwargs["env"], kwargs["cwd"]))
        return original(*args, **kwargs)

    monkeypatch.setattr(runner.subprocess, "Popen", record)
    result = run_extraction(
        (DATA / "encrypted.pdf").read_bytes(), "encrypted.pdf", PASSWORD, config=get_settings()
    )
    assert len(result["rows"]) == 399
    assert not list(tmp_path.iterdir())
    assert PASSWORD not in json.dumps(observed) and PASSWORD not in caplog.text
    assert all("DATABASE_URL" not in env and "LLM_API_KEY" not in env for _, env, _ in observed)


def test_preview_idor_quota_ttl_and_account_deletion(api_client, db, monkeypatch):
    a, user_a = account(api_client)
    b, user_b = account(api_client)
    job = ready(api_client, a, preview(api_client, a, "list_text.pdf")["id"])
    path = "/api/v1/uploads/previews/" + job["id"]
    assert api_client.get(path, headers=b).status_code == 404
    assert api_client.delete(path, headers=b).status_code == 404
    assert confirm(api_client, b, job).status_code == 404
    uid = uuid.UUID(user_a["id"])
    stored = repo.get_owned(db, uid, m.StatementPreview, uuid.UUID(job["id"]))
    stored.expires_at = now() - timedelta(seconds=1)
    db.commit()
    assert api_client.get(path, headers=a).status_code == 404
    assert repo.count_owned(db, uid, m.StatementPreview) == 0
    monkeypatch.setattr(get_settings(), "statement_daily_limit", 1)
    blocked = api_client.post(
        "/api/v1/uploads/preview",
        headers=a,
        files={"file": ("list_text.pdf", (DATA / "list_text.pdf").read_bytes())},
    )
    assert blocked.status_code == 429  # Expiry cannot reset quota.
    other = preview(api_client, b, "list_text.pdf")
    assert api_client.delete("/api/v1/me/data", headers=a).status_code == 200
    assert repo.count_owned(db, uid, m.StatementUsage) == 0
    assert repo.count_owned(db, uuid.UUID(user_b["id"]), m.StatementPreview) == 1
    api_client.delete("/api/v1/uploads/previews/" + other["id"], headers=b)


def test_flagged_unverified_excluded_and_edits_strictly_revalidated(api_client):
    headers, _ = account(api_client)
    job = ready(api_client, headers, preview(api_client, headers, "list_text.pdf")["id"])
    for edit in (
        dict(index=0, verified=True, amount=1.23),
        dict(index=0, verified=True, amount="1.234"),
        dict(index=0, verified=True, user_id="other"),
        dict(index=4999, verified=True),
    ):
        assert confirm(api_client, headers, job, [edit]).status_code == 422
    response = confirm(api_client, headers, job, [])
    assert response.status_code == 202
    upload, _ = wait(api_client, headers, response.json()["id"])
    assert upload["inserted_count"] == 0 and upload["excluded_count"] == 15


def test_cancel_purges_review_text_and_unreadable_image_guidance(api_client, db):
    headers, user = account(api_client)
    job = ready(api_client, headers, preview(api_client, headers, "list_text.pdf")["id"])
    cancelled = api_client.delete("/api/v1/uploads/previews/" + job["id"], headers=headers)
    assert cancelled.json()["status"] == "cancelled" and cancelled.json()["result"] is None
    assert (
        repo.get_owned(db, uuid.UUID(user["id"]), m.StatementPreview, uuid.UUID(job["id"])).payload
        == {}
    )
    unreadable = ready(api_client, headers, preview(api_client, headers, "unreadable.jpg")["id"])
    assert unreadable["status"] == "failed" and "CSV" in unreadable["error_message"]


@pytest.mark.parametrize(
    "name,data",
    [
        ("wrong.jpg", b"%PDF-1.4\n%%EOF"),
        ("wrong.pdf", b"not a PDF"),
        ("poly.pdf", b"%PDF-1.4\n%%EOF\nPK\x03\x04zip"),
        ("poly.jpg", b"\xff\xd8\xff\xd9<html>"),
        ("poly.png", b"\x89PNG\r\n\x1a\nBAD"),
    ],
)
def test_magic_mismatch_and_trailing_polyglots_are_rejected(name, data):
    with pytest.raises(ExtractionError):
        sniff(data, name)


def test_page_limit_malformed_pdf_and_active_content():
    writer = PdfWriter()
    for _ in range(31):
        writer.add_blank_page(width=600, height=800)
    buffer = io.BytesIO()
    writer.write(buffer)
    with pytest.raises(ExtractionError) as error:
        run_extraction(buffer.getvalue(), "too-many.pdf", "", config=get_settings())
    assert error.value.code == "too_many_pages"
    with pytest.raises(ExtractionError):
        run_extraction(
            b"%PDF-1.4\ninvalid recursive structure\n%%EOF", "broken.pdf", "", config=get_settings()
        )
    result = run_extraction(
        (DATA / "active_content.pdf").read_bytes(), "active.pdf", "", config=get_settings()
    )
    assert len(result["rows"]) == 399
    assert "app.alert" not in json.dumps(result) and "attachment" not in json.dumps(result)


def test_controller_timeout_and_memory_limit_cleanup(tmp_path, monkeypatch):
    import app.services.extraction_runner as runner

    monkeypatch.setattr(runner.tempfile, "tempdir", str(tmp_path))
    original = runner.subprocess.Popen

    def hanging(command, **kwargs):
        # Real subprocess stall fault injection; no parser response or fake success.
        return original([command[0], "-c", "import time; time.sleep(30)"], **kwargs)

    monkeypatch.setattr(runner.subprocess, "Popen", hanging)
    cfg = get_settings().model_copy(update={"statement_timeout_seconds": 1})
    with pytest.raises(ExtractionError) as error:
        run_extraction((DATA / "list_text.pdf").read_bytes(), "safe.pdf", "", config=cfg)
    assert error.value.code == "extraction_timeout" and not list(tmp_path.iterdir())
    monkeypatch.setattr(runner.subprocess, "Popen", original)
    cfg = get_settings().model_copy(update={"statement_memory_mb": 64})
    with pytest.raises(ExtractionError):
        run_extraction((DATA / "text_single.pdf").read_bytes(), "safe.pdf", "", config=cfg)
    assert not list(tmp_path.iterdir())


def test_decimal_reconciliation_flags_break_neighbors_and_indian_dr_suffix():
    def word(text, x, y, confidence="100"):
        return dict(text=text, x=x, y=y, height=10, confidence=confidence)

    words = [
        word("Date", 0, 0),
        word("Description", 100, 0),
        word("Amount", 300, 0),
        word("18/10/2026", 0, 20),
        word("SYNTHETIC", 100, 20),
        word("1,23,456.78", 300, 20),
        word("Dr", 390, 20, "45"),
    ]
    rows, _ = reconstruct(words, 1, ocr=True)
    assert rows[0]["amount"] == "123456.78" and rows[0]["type"] == "debit"
    assert "Low OCR field confidence" in rows[0]["flags"]
    ledger = [
        dict(amount="10.00", type="debit", balance="90.00", flags=[]),
        dict(amount="25.00", type="debit", balance="70.00", flags=[]),
        dict(amount="10.00", type="credit", balance="80.00", flags=[]),
    ]
    result = reconcile(ledger, {"opening": "100.00", "closing": "80.00"})
    assert result["status"] == "mismatch" and all(row["flags"] for row in ledger)
    assert reconcile(rows, {})["status"] == "unavailable" and rows[0]["flags"]


def test_pixel_bomb_rejected_before_decode_and_metadata_stripped(tmp_path):
    import struct
    import zlib

    from PIL import Image

    from app.services.statement_extraction import normalize_image

    # Valid PNG IHDR with impossible dimensions; no pixel buffer is allocated by this fixture.
    def chunk(kind, data):
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    data = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 100000, 100000, 8, 0, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\0"))
        + chunk(b"IEND", b"")
    )
    with pytest.raises(ExtractionError) as error:
        run_extraction(data, "bomb.png", "", config=get_settings())
    assert error.value.code == "image_too_large"
    image = Image.new("RGB", (400, 300), "white")
    exif = Image.Exif()
    exif[0x010F] = "SYNTHETIC ONLY"
    image.info["exif"] = exif.tobytes()
    normalized = normalize_image(image)
    path = tmp_path / "normalized.png"
    normalized.save(path)
    with Image.open(path) as saved:
        assert "exif" not in saved.info and not saved.getexif()


def test_recursive_pdf_and_oversize_are_bounded():
    body = b"%PDF-1.4\n"
    offsets = [0]
    for number, value in (
        (1, b"<</Type /Catalog /Pages 2 0 R>>"),
        (2, b"<</Type /Pages /Count 1 /Kids [2 0 R]>>"),
    ):
        offsets.append(len(body))
        body += str(number).encode() + b" 0 obj\n" + value + b"\nendobj\n"
    xref = len(body)
    body += b"xref\n0 3\n0000000000 65535 f \n" + b"".join(
        f"{offset:010} 00000 n \n".encode() for offset in offsets[1:]
    )
    body += b"trailer\n<</Size 3 /Root 1 0 R>>\nstartxref\n" + str(xref).encode() + b"\n%%EOF\n"
    with pytest.raises(ExtractionError):
        run_extraction(
            body,
            "recursive.pdf",
            "",
            config=get_settings().model_copy(update={"statement_timeout_seconds": 2}),
        )
    with pytest.raises(ExtractionError) as error:
        run_extraction(b"x" * (10 * 1024 * 1024 + 1), "large.pdf", "", config=get_settings())
    assert error.value.code == "file_too_large"


def test_startup_cleans_only_abandoned_private_temp_directories(tmp_path):
    from app.services.extraction_runner import purge_abandoned_temps

    private = tmp_path / "subtrack-extract-abandoned"
    private.mkdir()
    (private / "statement.pdf").write_bytes(b"synthetic original bytes")
    other = tmp_path / "leave-alone"
    other.mkdir()
    purge_abandoned_temps(tmp_path)
    assert not private.exists() and other.exists()


def test_concurrent_preview_limit_and_rate_limit(api_client, monkeypatch):
    from threading import Event

    import app.statement_jobs as jobs

    hold = Event()
    original = jobs.run_extraction

    def slow(*args, **kwargs):
        hold.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(jobs, "run_extraction", slow)
    headers, _ = account(api_client)
    first = preview(api_client, headers, "list_text.pdf")
    second = preview(api_client, headers, "list_text.pdf")
    try:
        response = api_client.post(
            "/api/v1/uploads/preview",
            headers=headers,
            files={"file": ("list_text.pdf", (DATA / "list_text.pdf").read_bytes())},
        )
        assert response.status_code == 429
    finally:
        hold.set()
    assert ready(api_client, headers, first["id"])["status"] == "ready"
    assert ready(api_client, headers, second["id"])["status"] == "ready"
    monkeypatch.setattr(get_settings(), "auth_login_limit", 3)
    response = api_client.post(
        "/api/v1/uploads/preview",
        headers=headers,
        files={"file": ("encrypted.pdf", (DATA / "encrypted.pdf").read_bytes())},
    )
    assert response.status_code == 429 and "Retry-After" in response.headers


def test_shell_filename_cannot_execute_and_no_raw_data_in_logs(caplog, tmp_path):
    name = "synthetic;touch UNEXPECTED.pdf"
    result = run_extraction((DATA / "list_text.pdf").read_bytes(), name, "", config=get_settings())
    assert len(result["rows"]) == 15
    assert not Path("UNEXPECTED.pdf").exists()
    assert "123456.78" not in caplog.text and "UPI/" not in caplog.text
