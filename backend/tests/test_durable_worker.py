"""Real parser subprocesses, Unix RPC, PostgreSQL jobs and financial transaction boundaries."""

import io
import json
import os
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pytest
from pypdf import PdfReader
from sqlalchemy import select
from test_durable_queue import owner

from app import models as m
from app import repositories as repo
from app.config import get_settings
from app.durable_worker import Dispatcher, Worker
from app.services import durable_queue as q
from app.services import extractor_rpc
from app.services.statement_extraction import ExtractionError

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data/extraction"
DAY = date(2026, 10, 18)


@pytest.fixture
def private_rpc(monkeypatch, tmp_path):
    socket = tmp_path / "parser.sock"
    private = tmp_path / "private"
    private.mkdir()
    env = {
        "PATH": os.environ["PATH"],
        "PYTHONPATH": str(ROOT),
        "LANG": "C.UTF-8",
        "EXTRACTOR_SOCKET": str(socket),
        "TMPDIR": str(private),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    process = subprocess.Popen(
        [sys.executable, "-m", "app.extractor_service"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    monkeypatch.setenv("EXTRACTOR_SOCKET", str(socket))
    get_settings.cache_clear()
    try:
        deadline = time.monotonic() + 10
        while not socket.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert socket.exists() and process.poll() is None
        yield private
    finally:
        process.terminate()
        try:
            process.wait(timeout=6)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


def preview_job(db, user_id, data, *, staging=False):
    preview = repo.create_owned(
        db,
        user_id,
        m.StatementPreview,
        filename="synthetic.pdf",
        expires_at=q.utcnow() + timedelta(minutes=30),
    )
    job = q.enqueue(
        db,
        user_id,
        kind="extraction",
        subject_id=preview.id,
        data=None if staging else data,
        mapping=None,
        as_of=DAY,
        staging=staging,
    )
    db.commit()
    return preview.id, job.id


def test_unix_rpc_real_text_extraction_and_temp_cleanup(private_rpc):
    result = extractor_rpc.call((FIXTURES / "text_single.pdf").read_bytes(), "synthetic.pdf")
    truth = json.loads((FIXTURES / "manifest.json").read_text())["variants"][0]["rows"]
    assert len(result["rows"]) == len(truth)
    assert all(isinstance(row["amount"], str) for row in result["rows"])
    assert result["flagged_count"] == len(result["rows"])
    assert not list(private_rpc.glob("subtrack-extract-*"))


def test_password_preflight_never_stored_and_clean_pdf_is_durable(db, pg_engine, private_rpc):
    user_id = owner(db)
    data = (FIXTURES / "encrypted.pdf").read_bytes()
    preview_id, job_id = preview_job(db, user_id, data, staging=True)
    assert db.get(m.DurableJob, job_id).encrypted_input is None
    assert q.claim_next(pg_engine) is None
    Dispatcher(pg_engine).preflight(user_id, preview_id, data, "synthetic.pdf", "FixtureOnly42!")
    db.expire_all()
    row = db.get(m.DurableJob, job_id)
    cleaned, mapping = q.unseal(row.encrypted_input)
    assert mapping is None and not PdfReader(io.BytesIO(cleaned)).is_encrypted
    assert b"FixtureOnly42!" not in row.encrypted_input and b"FixtureOnly42!" not in cleaned
    Worker(pg_engine).run_once()
    db.expire_all()
    assert db.get(m.StatementPreview, preview_id).status == "ready"
    assert db.get(m.DurableJob, job_id).encrypted_input is None
    assert not list(private_rpc.glob("subtrack-extract-*"))


def test_wrong_preflight_password_terminal_and_no_original_bytes(db, pg_engine, private_rpc):
    user_id = owner(db)
    data = (FIXTURES / "encrypted.pdf").read_bytes()
    preview_id, job_id = preview_job(db, user_id, data, staging=True)
    Dispatcher(pg_engine).preflight(
        user_id, preview_id, data, "synthetic.pdf", "wrong-fixture-code"
    )
    db.expire_all()
    assert db.get(m.DurableJob, job_id).status == "dead_letter"
    assert db.get(m.DurableJob, job_id).encrypted_input is None
    assert db.get(m.StatementPreview, preview_id).error_code == "wrong_password"
    assert not list(private_rpc.glob("subtrack-extract-*"))


def test_rpc_cancel_kills_private_parser_and_removes_tmp(private_rpc):
    with pytest.raises(ExtractionError) as failure:
        extractor_rpc.call(
            (FIXTURES / "scanned.pdf").read_bytes(), "synthetic.pdf", cancelled=lambda: True
        )
    assert failure.value.code == "cancelled"
    deadline = time.monotonic() + 8
    while list(private_rpc.glob("subtrack-extract-*")) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not list(private_rpc.glob("subtrack-extract-*"))


def test_worker_real_csv_idempotency_and_atomic_ack(db, pg_engine):
    user_id = owner(db)
    data = (ROOT / "data/sample_transactions.csv").read_bytes()
    truth = json.loads((ROOT / "data/ground_truth.json").read_text())
    db.commit()
    ids = []
    for _ in range(2):
        upload = repo.create_owned(db, user_id, m.Upload, filename="synthetic.csv")
        q.enqueue(db, user_id, kind="csv", subject_id=upload.id, data=data, mapping=None, as_of=DAY)
        ids.append(upload.id)
        db.commit()
        assert Worker(pg_engine).run_once()
    db.expire_all()
    assert repo.count_owned(db, user_id, m.Transaction) == len(data.decode().splitlines()) - 1
    assert repo.count_owned(db, user_id, m.Subscription) == len(truth["patterns"])
    assert db.get(m.Upload, ids[1]).inserted_count == 0
    assert all(
        row.status == "done" and row.encrypted_input is None
        for row in repo.list_owned(db, user_id, m.DurableJob)
    )


def test_failure_after_financial_writes_rolls_back_everything_and_wipes_input(
    db,
    pg_engine,
    monkeypatch,
    caplog,
):
    from app import uploads

    monkeypatch.setenv("JOB_MAX_ATTEMPTS", "1")
    get_settings.cache_clear()
    user_id = owner(db)
    upload = repo.create_owned(db, user_id, m.Upload, filename="synthetic.csv")
    q.enqueue(
        db,
        user_id,
        kind="csv",
        subject_id=upload.id,
        data=(ROOT / "data/sample_transactions.csv").read_bytes(),
        mapping=None,
        as_of=DAY,
    )
    db.commit()
    original = uploads.persist_parsed

    def fail_after_writes(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("SYNTHETIC_PRIVATE_FAILURE 314159.26")

    monkeypatch.setattr(uploads, "persist_parsed", fail_after_writes)
    Worker(pg_engine).run_once()
    db.expire_all()
    assert repo.count_owned(db, user_id, m.Transaction) == 0
    assert repo.count_owned(db, user_id, m.Subscription) == 0
    assert repo.count_owned(db, user_id, m.Recommendation) == 0
    assert db.get(m.Upload, upload.id).status == "failed"
    row = db.scalar(select(m.DurableJob).where(m.DurableJob.user_id == user_id))
    assert row.status == "dead_letter" and row.encrypted_input is None
    assert "314159.26" not in caplog.text and "SYNTHETIC_PRIVATE_FAILURE" not in caplog.text


def test_staging_expiry_cannot_be_activated_by_late_api(db, pg_engine):
    user_id = owner(db)
    _, job_id = preview_job(db, user_id, b"", staging=True)
    row = db.get(m.DurableJob, job_id)
    token = row.claim_token
    now = row.lease_until + timedelta(seconds=1)
    assert q.expire(pg_engine, now=now) == 1
    db.expire_all()
    assert not q.activate_staging(db, user_id, job_id, token, b"%PDF-synthetic")
    assert db.get(m.DurableJob, job_id).encrypted_input is None
