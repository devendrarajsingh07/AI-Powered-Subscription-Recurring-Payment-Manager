"""Real PostgreSQL queue lifecycle. Container crash/isolation tests follow the worker wiring."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import pytest
from cryptography.fernet import InvalidToken
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models as m
from app import repositories as repo
from app.config import get_settings
from app.services import durable_queue as q

DATA = b"date,description,amount,type\n2026-01-01,SYNTHETICPRIVATE,100.00,debit\n"
DAY = date(2026, 10, 18)


def owner(db):
    user = m.User(email=f"queue-{uuid.uuid4().hex}@example.org", password_hash="unused-synthetic")
    db.add(user)
    db.flush()
    return user.id


def add_job(db, user_id, *, expiry=None):
    upload = repo.create_owned(db, user_id, m.Upload, filename="synthetic.csv")
    row = q.enqueue(
        db,
        user_id,
        kind="csv",
        subject_id=upload.id,
        data=DATA,
        mapping={"date": "date"},
        as_of=DAY,
        expires_at=expiry,
    )
    db.flush()
    return row.id, upload.id


def test_encrypted_bounded_input_and_wrong_key(monkeypatch):
    value = q.seal(DATA, {"description": "description"})
    assert DATA not in value and b"SYNTHETICPRIVATE" not in value
    assert q.unseal(value) == (DATA, {"description": "description"})
    with pytest.raises(ValueError):
        q.seal(b"x" * (q.MAX_INPUT + 1))
    with pytest.raises(ValueError):
        q.seal(DATA, {"date": "x" * 513})
    with pytest.raises(InvalidToken):
        q.unseal(value[:-5] + b"wrong")
    monkeypatch.setenv("JWT_SECRET", uuid.uuid4().hex + uuid.uuid4().hex)
    get_settings.cache_clear()
    with pytest.raises(InvalidToken):
        q.unseal(value)


def test_enqueue_is_atomic_with_subject_and_owner_scoped(db):
    user_id = owner(db)
    db.commit()
    add_job(db, user_id)
    db.rollback()
    assert repo.count_owned(db, user_id, m.Upload) == 0
    assert repo.count_owned(db, user_id, m.DurableJob) == 0
    other_id = owner(db)
    upload = repo.create_owned(db, other_id, m.Upload, filename="synthetic.csv")
    with pytest.raises(HTTPException) as error:
        q.enqueue(db, user_id, kind="csv", subject_id=upload.id, data=DATA, mapping=None, as_of=DAY)
    assert error.value.status_code == 404


def test_capacity_shared_between_independent_connections(db, pg_engine, monkeypatch):
    monkeypatch.setenv("UPLOAD_QUEUE_LIMIT", "2")
    get_settings.cache_clear()
    users = [owner(db) for _ in range(4)]
    db.commit()

    def submit(user_id):
        try:
            with Session(pg_engine) as session, session.begin():
                add_job(session, user_id)
            return 202
        except HTTPException as error:
            return error.status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sorted(pool.map(submit, users)) == [202, 202, 429, 429]
    assert db.scalar(select(func.count()).select_from(m.DurableJob)) == 2
    assert db.scalar(select(func.count()).select_from(m.Upload)) == 2


def test_skip_locked_claims_other_job(db, pg_engine):
    user_id = owner(db)
    first, _ = add_job(db, user_id)
    second, _ = add_job(db, user_id)
    db.commit()
    with Session(pg_engine) as lock:
        lock.scalar(select(m.DurableJob).where(m.DurableJob.id == first).with_for_update())
        claim = q.claim_next(pg_engine)
        assert claim.job_id == second
    assert q.claim_next(pg_engine).job_id == first
    assert q.claim_next(pg_engine) is None


def test_expired_lease_reclaimed_and_stale_token_cannot_publish_or_release(db, pg_engine):
    user_id = owner(db)
    job_id, _ = add_job(db, user_id)
    db.commit()
    now = q.utcnow()
    first = q.claim_next(pg_engine, now=now)
    later = now + timedelta(seconds=get_settings().job_lease_seconds + 1)
    second = q.claim_next(pg_engine, now=later)
    assert first.job_id == second.job_id == job_id and first.token != second.token
    assert not q.heartbeat(pg_engine, user_id, job_id, first.token, now=later)
    assert not q.failed(pg_engine, user_id, job_id, first.token, permanent=True, now=later)
    repo.get_user(db, user_id, lock=True)
    assert q.locked_claim(db, user_id, job_id, first.token, now=later) is None
    row = q.locked_claim(db, user_id, job_id, second.token, now=later)
    assert row is not None and row.attempt_count == 2 and row.as_of == DAY
    q.acknowledge(row)
    db.commit()
    db.expire_all()
    assert db.get(m.DurableJob, job_id).encrypted_input is None


def test_retry_backoff_terminal_failure_wipes_input_and_is_visible(db, pg_engine, monkeypatch):
    monkeypatch.setenv("JOB_MAX_ATTEMPTS", "2")
    get_settings.cache_clear()
    user_id = owner(db)
    job_id, upload_id = add_job(db, user_id)
    db.commit()
    now = q.utcnow()
    first = q.claim_next(pg_engine, now=now)
    assert q.failed(pg_engine, user_id, job_id, first.token, code="not a safe code", now=now)
    assert q.claim_next(pg_engine, now=now) is None
    later = now + timedelta(seconds=get_settings().job_retry_seconds + 1)
    second = q.claim_next(pg_engine, now=later)
    assert second.job_id == job_id and not second.exhausted
    assert q.failed(pg_engine, user_id, job_id, second.token, now=later)
    db.expire_all()
    row = db.get(m.DurableJob, job_id)
    assert row.status == "dead_letter" and row.encrypted_input is None
    assert row.attempt_count == 2 and row.failure_code == "processing_failed"
    upload = db.get(m.Upload, upload_id)
    assert upload.status == "failed" and upload.stage == "dead_letter"
    assert q.claim_next(pg_engine, now=later) is None


def test_cancel_queued_or_running_clears_bytes_and_owner_delete_cascades(db, pg_engine):
    user_id = owner(db)
    queued_id, _ = add_job(db, user_id)
    running_id, _ = add_job(db, user_id)
    db.commit()
    claim = q.claim_next(pg_engine)
    assert q.cancel(db, user_id, queued_id)
    assert q.cancel(db, user_id, running_id)
    db.commit()
    assert not q.heartbeat(pg_engine, user_id, claim.job_id, claim.token)
    db.expire_all()
    assert all(row.encrypted_input is None for row in repo.list_owned(db, user_id, m.DurableJob))
    another, _ = add_job(db, user_id)
    db.commit()
    counts = repo.delete_data(db, user_id)
    assert counts["durable_jobs"] == 3
    db.commit()
    assert db.get(m.DurableJob, another) is None


def test_expired_input_is_claimed_for_terminal_cleanup_never_for_processing(db, pg_engine):
    user_id = owner(db)
    now = q.utcnow()
    job_id, _ = add_job(db, user_id, expiry=now - timedelta(seconds=1))
    db.commit()
    claim = q.claim_next(pg_engine, now=now)
    assert claim.exhausted
    assert q.failed(
        pg_engine, user_id, job_id, claim.token, permanent=True, code="expired", now=now
    )
    db.expire_all()
    assert db.get(m.DurableJob, job_id).encrypted_input is None


def test_database_rejects_cross_owner_job_link(db):
    first, second = owner(db), owner(db)
    job_id, _ = add_job(db, first)
    db.commit()
    db.get(m.DurableJob, job_id).user_id = second
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
