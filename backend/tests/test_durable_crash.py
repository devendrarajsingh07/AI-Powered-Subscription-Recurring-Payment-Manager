"""Crash, per-user admission and delete-while-running tests against real PostgreSQL.

A genuine OS process claims a job and is SIGKILLed while holding its lease; a second worker must
reclaim it after expiry and publish exactly once. Synthetic data only.
"""

import os
import signal
import subprocess
import sys
import textwrap
import time
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import update
from test_durable_queue import add_job, owner

from app import models as m
from app import repositories as repo
from app.config import get_settings
from app.durable_worker import Worker
from app.services import durable_queue as q

ROOT = Path(__file__).resolve().parents[1]
DAY = date(2026, 10, 18)

HOLDER = textwrap.dedent(
    """
    import os, time
    from sqlalchemy import create_engine
    from app.services import durable_queue as q
    claim = q.claim_next(create_engine(os.environ["HOLDER_DB"]))
    print("CLAIMED" if claim else "NONE", flush=True)
    time.sleep(600)
    """
)


def csv_job(db, user_id):
    data = (ROOT / "data/sample_transactions.csv").read_bytes()
    upload = repo.create_owned(db, user_id, m.Upload, filename="synthetic.csv")
    row = q.enqueue(
        db, user_id, kind="csv", subject_id=upload.id, data=data, mapping=None, as_of=DAY
    )
    db.flush()
    return row.id, upload.id, len(data.decode().splitlines()) - 1


def test_sigkilled_worker_lease_expires_and_second_worker_publishes_exactly_once(
    db, pg_engine, monkeypatch
):
    monkeypatch.setenv("JOB_LEASE_SECONDS", "3")
    get_settings.cache_clear()
    user_id = owner(db)
    job_id, upload_id, expected = csv_job(db, user_id)
    db.commit()
    env = dict(
        os.environ,
        HOLDER_DB=pg_engine.url.render_as_string(hide_password=False),
        JOB_LEASE_SECONDS="3",
        PYTHONPATH=str(ROOT),
        PYTHONDONTWRITEBYTECODE="1",
    )
    holder = subprocess.Popen(
        [sys.executable, "-c", HOLDER],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        assert holder.stdout.readline().strip() == "CLAIMED"
        db.expire_all()
        row = db.get(m.DurableJob, job_id)
        assert row.status == "running" and row.attempt_count == 1
        # While the dead worker's lease is still valid nobody else may take the job.
        assert q.claim_next(pg_engine) is None
        holder.send_signal(signal.SIGKILL)
        holder.wait(timeout=5)
    finally:
        if holder.poll() is None:
            holder.kill()
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if Worker(pg_engine).run_once():
            break
        time.sleep(0.5)
    db.expire_all()
    row = db.get(m.DurableJob, job_id)
    assert row.status == "done" and row.attempt_count == 2 and row.encrypted_input is None
    assert db.get(m.Upload, upload_id).status == "done"
    assert repo.count_owned(db, user_id, m.Transaction) == expected
    # No duplicate publication: nothing is left to claim and a re-run changes nothing.
    assert not Worker(pg_engine).run_once()
    assert repo.count_owned(db, user_id, m.Transaction) == expected


def test_worker_dead_on_final_attempt_ends_in_visible_dead_letter_without_financial_rows(
    db, pg_engine, monkeypatch
):
    monkeypatch.setenv("JOB_MAX_ATTEMPTS", "1")
    get_settings.cache_clear()
    user_id = owner(db)
    job_id, upload_id, _ = csv_job(db, user_id)
    db.commit()
    assert q.claim_next(pg_engine) is not None  # Simulated dead worker: never finishes.
    with pg_engine.begin() as connection:
        connection.execute(
            update(m.DurableJob)
            .where(m.DurableJob.id == job_id)
            .values(lease_until=q.utcnow() - timedelta(seconds=5))
        )
    assert Worker(pg_engine).run_once()  # Exhausted claim is terminalised, never processed.
    db.expire_all()
    row = db.get(m.DurableJob, job_id)
    assert row.status == "dead_letter" and row.encrypted_input is None
    assert row.failure_code == "input_unavailable"
    upload = db.get(m.Upload, upload_id)
    assert upload.status == "failed" and upload.stage == "dead_letter"
    assert repo.count_owned(db, user_id, m.Transaction) == 0


def test_account_deleted_while_job_running_publishes_nothing_and_leaves_no_rows(db, pg_engine):
    user_id = owner(db)
    job_id, upload_id, _ = csv_job(db, user_id)
    db.commit()
    claim = q.claim_next(pg_engine)
    assert claim is not None and claim.job_id == job_id
    assert repo.get_user(db, user_id, lock=True) is not None
    repo.delete_data(db, user_id)
    db.commit()
    Worker(pg_engine).execute(claim)  # Late worker: must be a safe no-op.
    db.expire_all()
    assert db.get(m.User, user_id) is None
    assert db.get(m.DurableJob, job_id) is None and db.get(m.Upload, upload_id) is None
    assert repo.count_owned(db, user_id, m.Transaction) == 0
    assert repo.count_owned(db, user_id, m.Subscription) == 0


def test_one_account_cannot_fill_the_shared_queue(db, monkeypatch):
    monkeypatch.setenv("UPLOAD_QUEUE_LIMIT", "8")
    monkeypatch.setenv("JOB_USER_LIMIT", "2")
    get_settings.cache_clear()
    greedy, other = owner(db), owner(db)
    db.commit()
    add_job(db, greedy)
    add_job(db, greedy)
    db.commit()
    with pytest.raises(HTTPException) as error:
        add_job(db, greedy)
    assert error.value.status_code == 429
    assert error.value.detail["code"] == "upload_user_limit"
    db.rollback()
    add_job(db, other)  # A different account is unaffected.
    db.commit()
    assert repo.count_owned(db, greedy, m.DurableJob) == 2
    assert repo.count_owned(db, other, m.DurableJob) == 1
