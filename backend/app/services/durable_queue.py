"""PostgreSQL leases and bounded encrypted input. Financial commits fence the claim token.

Request paths are user-scoped. Only the worker's claim/expiry maintenance enumerates owners.
Coordination uses wall time; the immutable financial as_of is supplied at submission.
"""

import base64
import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from sqlalchemy import func, or_, select, text, update
from sqlalchemy.orm import Session, defer

from app import models as m
from app import repositories as repo
from app.config import get_settings

MAX_INPUT = 10 * 1024 * 1024
MAX_CIPHER = 14 * 1024 * 1024
CAPACITY_LOCK = 724193820


def utcnow():
    return datetime.now(timezone.utc)


def cipher():
    secret = get_settings().jwt_secret.get_secret_value().encode()
    if len(secret) < 32:
        raise RuntimeError("Job input encryption requires a strong signing secret")
    key = hmac.new(secret, b"subtrack-durable-input-v1", hashlib.sha256).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def seal(data: bytes, mapping=None):
    """Binary framing avoids a second base64 expansion. No arbitrary object deserialization."""
    if not isinstance(data, bytes) or len(data) > MAX_INPUT:
        raise ValueError("Job input exceeds its byte limit")
    if mapping is not None and (
        not isinstance(mapping, dict)
        or len(mapping) > 20
        or any(
            not isinstance(k, str) or not isinstance(v, str) or len(k) > 512 or len(v) > 512
            for k, v in mapping.items()
        )
    ):
        raise ValueError("Column mapping exceeds its bounded schema")
    header = json.dumps({"mapping": mapping}, separators=(",", ":")).encode()
    if len(header) > 16384:
        raise ValueError("Column mapping exceeds its byte limit")
    value = cipher().encrypt(len(header).to_bytes(4, "big") + header + data)
    if len(value) > MAX_CIPHER:
        raise ValueError("Encrypted job input exceeds its byte limit")
    return value


def unseal(value):
    if not isinstance(value, bytes) or len(value) > MAX_CIPHER:
        raise InvalidToken
    plain = cipher().decrypt(value)
    size = int.from_bytes(plain[:4], "big")
    if not 1 <= size <= 16384 or len(plain) > MAX_INPUT + 16388:
        raise InvalidToken
    try:
        header = json.loads(plain[4 : 4 + size])
        if set(header) != {"mapping"}:
            raise ValueError
        mapping = header["mapping"]
        if mapping is not None and (
            not isinstance(mapping, dict)
            or len(mapping) > 20
            or any(not isinstance(k, str) or not isinstance(v, str) for k, v in mapping.items())
        ):
            raise ValueError
    except (ValueError, TypeError):
        raise InvalidToken from None
    return plain[4 + size :], mapping


def enqueue(db, user_id, *, kind, subject_id, data, mapping, as_of, expires_at=None, staging=False):
    cfg = get_settings()
    if kind not in ("csv", "extraction"):
        raise ValueError("Unsupported job kind")
    if staging and (kind != "extraction" or data is not None or mapping is not None):
        raise ValueError("Preflight staging may contain metadata only")
    if repo.get_user(db, user_id, lock=True) is None:
        raise HTTPException(401, {"code": "unauthorized", "message": "Account no longer exists"})
    model = m.Upload if kind == "csv" else m.StatementPreview
    if repo.get_owned(db, user_id, model, subject_id) is None:
        raise HTTPException(404, {"code": "not_found", "message": "Record not found"})
    # All API instances share the same admission lock and count. No in-memory reservation gap.
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": CAPACITY_LOCK})
    count = db.scalar(
        select(func.count())
        .select_from(m.DurableJob)
        .where(m.DurableJob.status.in_(("staging", "queued", "running")))
    )
    if count >= cfg.upload_queue_limit:
        raise HTTPException(
            429, {"code": "upload_queue_full", "message": "Work queue is full; try again shortly"}
        )
    # One account cannot consume the whole shared queue; counted under the same admission lock.
    mine = db.scalar(
        select(func.count())
        .select_from(m.DurableJob)
        .where(
            m.DurableJob.user_id == user_id,
            m.DurableJob.status.in_(("staging", "queued", "running")),
        )
    )
    if mine >= cfg.job_user_limit:
        raise HTTPException(
            429,
            {
                "code": "upload_user_limit",
                "message": "Too many of your files are already processing; wait for one to finish",
            },
        )
    try:
        encrypted = None if staging else seal(data, mapping)
    except ValueError:
        raise HTTPException(
            422, {"code": "job_input_limit", "message": "File or column mapping exceeds its limits"}
        ) from None
    return repo.create_owned(
        db,
        user_id,
        m.DurableJob,
        kind=kind,
        upload_id=subject_id if kind == "csv" else None,
        preview_id=subject_id if kind == "extraction" else None,
        encrypted_input=encrypted,
        as_of=as_of,
        max_attempts=cfg.job_max_attempts,
        expires_at=expires_at or utcnow() + timedelta(minutes=cfg.job_ttl_minutes),
        status="staging" if staging else "queued",
        claim_token=uuid.uuid4() if staging else None,
        lease_until=utcnow() + timedelta(seconds=cfg.statement_timeout_seconds + 5)
        if staging
        else None,
    )


@dataclass(frozen=True)
class Claim:
    job_id: uuid.UUID
    user_id: uuid.UUID
    token: uuid.UUID
    exhausted: bool


def claim_next(engine, *, now=None):
    """Worker-only global dispatcher. Return identities, never input bytes or financial data."""
    now = now or utcnow()
    with Session(engine) as db, db.begin():
        row = db.scalar(
            select(m.DurableJob)
            .options(defer(m.DurableJob.encrypted_input))
            .where(
                or_(
                    (m.DurableJob.status == "queued") & (m.DurableJob.available_at <= now),
                    (m.DurableJob.status == "running") & (m.DurableJob.lease_until <= now),
                    (m.DurableJob.status == "staging") & (m.DurableJob.lease_until <= now),
                )
            )
            .order_by(m.DurableJob.available_at, m.DurableJob.created_at, m.DurableJob.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if row is None:
            return None
        exhausted = (
            row.status == "staging"
            or row.attempt_count >= row.max_attempts
            or row.expires_at <= now
        )
        if not exhausted:
            row.attempt_count += 1
        row.status, row.claim_token = "running", uuid.uuid4()
        row.lease_until = now + timedelta(seconds=get_settings().job_lease_seconds)
        row.updated_at = now
        return Claim(row.id, row.user_id, row.claim_token, exhausted)


def heartbeat(engine, user_id, job_id, token, *, now=None):
    now = now or utcnow()
    with Session(engine) as db, db.begin():
        return bool(
            db.execute(
                update(m.DurableJob)
                .where(
                    m.DurableJob.user_id == user_id,
                    m.DurableJob.id == job_id,
                    m.DurableJob.claim_token == token,
                    m.DurableJob.status == "running",
                    m.DurableJob.lease_until > now,
                    m.DurableJob.expires_at > now,
                )
                .values(
                    lease_until=now + timedelta(seconds=get_settings().job_lease_seconds),
                    updated_at=now,
                )
            ).rowcount
        )


def locked_claim(db, user_id, job_id, token, *, now=None):
    """Caller locks the owner first, matching deletion/finalization lock order."""
    now = now or utcnow()
    row = db.scalar(
        select(m.DurableJob)
        .where(m.DurableJob.user_id == user_id, m.DurableJob.id == job_id)
        .with_for_update()
    )
    if (
        row is None
        or row.status != "running"
        or row.claim_token != token
        or row.lease_until <= now
        or row.expires_at <= now
    ):
        return None
    return row


def acknowledge(row):
    """Called inside the SAME transaction as financial writes or preview publication."""
    row.status, row.encrypted_input = "done", None
    row.claim_token, row.lease_until, row.failure_code = None, None, None
    row.updated_at = utcnow()


def _subject_state(db, user_id, row, *, status, stage, message):
    if row.upload_id:
        repo.update_upload(
            db, user_id, row.upload_id, status=status, stage=stage, error_message=message
        )
    else:
        preview = repo.get_owned(db, user_id, m.StatementPreview, row.preview_id)
        if preview and preview.status in ("pending", "processing"):
            preview.status, preview.stage = status, stage
            preview.error_code, preview.error_message = row.failure_code, message
            if status in ("failed", "cancelled"):
                preview.payload = {}


def failed(
    engine,
    user_id,
    job_id,
    token,
    *,
    permanent=False,
    code="processing_failed",
    now=None,
    preview_error=None,
):
    now = now or utcnow()
    allowed = {"processing_failed", "input_unavailable", "expired", "extraction_failed"}
    code = code if code in allowed else "processing_failed"
    with Session(engine) as db, db.begin():
        if repo.get_user(db, user_id, lock=True) is None:
            return False
        row = db.scalar(
            select(m.DurableJob)
            .where(m.DurableJob.user_id == user_id, m.DurableJob.id == job_id)
            .with_for_update()
        )
        if row is None or row.claim_token != token or row.status != "running":
            return False
        if row.lease_until <= now and row.expires_at > now:
            return False  # A dead/late worker cannot change a newly eligible claim.
        terminal = permanent or row.attempt_count >= row.max_attempts or row.expires_at <= now
        row.failure_code, row.updated_at = code, now
        row.claim_token, row.lease_until = None, None
        if terminal:
            row.status, row.encrypted_input = "dead_letter", None
            _subject_state(
                db,
                user_id,
                row,
                status="failed",
                stage="dead_letter",
                message=(
                    "Processing could not finish safely. No partial financial changes were "
                    "saved; choose the file again."
                ),
            )
            if preview_error and row.preview_id:
                from app.services.extractor_rpc import SAFE_ERRORS

                preview = repo.get_owned(db, user_id, m.StatementPreview, row.preview_id)
                if preview and preview_error in SAFE_ERRORS:
                    preview.error_code = preview_error
                    preview.error_message = SAFE_ERRORS[preview_error]
        else:
            row.status = "queued"
            delay = min(300, get_settings().job_retry_seconds * 2 ** (row.attempt_count - 1))
            row.available_at = now + timedelta(seconds=delay)
            _subject_state(db, user_id, row, status="processing", stage="retrying", message=None)
        return True


def cancel(db, user_id, job_id):
    if repo.get_user(db, user_id, lock=True) is None:
        return False
    row = db.scalar(
        select(m.DurableJob)
        .where(m.DurableJob.user_id == user_id, m.DurableJob.id == job_id)
        .with_for_update()
    )
    if row is None:
        return False
    if row.status in ("staging", "queued", "running"):
        row.status, row.encrypted_input = "cancelled", None
        row.claim_token, row.lease_until = None, None
        row.updated_at = utcnow()
        _subject_state(
            db,
            user_id,
            row,
            status="failed" if row.upload_id else "cancelled",
            stage="cancelled",
            message="Processing was cancelled before publication.",
        )
    return True


def activate_staging(db, user_id, job_id, token, cleaned):
    """No accepted job depends on a password. Atomically replace metadata-only admission."""
    if repo.get_user(db, user_id, lock=True) is None:
        return False
    now = utcnow()
    row = db.scalar(
        select(m.DurableJob)
        .where(m.DurableJob.user_id == user_id, m.DurableJob.id == job_id)
        .with_for_update()
    )
    if (
        row is None
        or row.status != "staging"
        or row.claim_token != token
        or row.expires_at <= now
        or row.lease_until <= now
    ):
        return False
    row.encrypted_input = seal(cleaned)
    row.status, row.claim_token, row.lease_until = "queued", None, None
    row.available_at, row.updated_at = now, now
    preview = repo.get_owned(db, user_id, m.StatementPreview, row.preview_id)
    if preview:
        preview.stage = "queued"
    return True


def reject_staging(db, user_id, job_id, token, *, code, message):
    if repo.get_user(db, user_id, lock=True) is None:
        return False
    row = db.scalar(
        select(m.DurableJob)
        .where(m.DurableJob.user_id == user_id, m.DurableJob.id == job_id)
        .with_for_update()
    )
    if row is None or row.status != "staging" or row.claim_token != token:
        return False
    row.status, row.encrypted_input = "dead_letter", None
    row.claim_token, row.lease_until = None, None
    row.failure_code, row.updated_at = code, utcnow()
    _subject_state(db, user_id, row, status="failed", stage="failed", message=message)
    return True


def expire(engine, *, now=None):
    """Worker maintenance enumerates IDs only; busy owners are revisited without blocking."""
    now = now or utcnow()
    active = m.DurableJob.status.in_(("staging", "queued", "running"))
    due = or_(
        m.DurableJob.expires_at <= now,
        (m.DurableJob.status == "staging") & (m.DurableJob.lease_until <= now),
    )
    with Session(engine) as db:
        ids = list(db.execute(select(m.DurableJob.user_id, m.DurableJob.id).where(active, due)))
    count = 0
    for user_id, job_id in ids:
        with Session(engine) as db, db.begin():
            owner = db.scalar(
                select(m.User.id).where(m.User.id == user_id).with_for_update(skip_locked=True)
            )
            if owner is None:
                continue
            row = db.scalar(
                select(m.DurableJob)
                .where(
                    m.DurableJob.user_id == user_id,
                    m.DurableJob.id == job_id,
                    active,
                    due,
                )
                .with_for_update(skip_locked=True)
            )
            if row is None:
                continue
            row.status, row.encrypted_input = "dead_letter", None
            row.claim_token, row.lease_until = None, None
            row.failure_code, row.updated_at = "expired", now
            _subject_state(
                db,
                user_id,
                row,
                status="failed",
                stage="dead_letter",
                message="Processing expired safely. Choose the local file again.",
            )
            count += 1
    return count
