"""Isolated synthetic mailbox rehearsal: real parser, PostgreSQL progress, no network.

Evidence is deliberately separate from transaction history and cannot change spend figures.
"""

import hashlib
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import case, delete, func, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app import models as m
from app import repositories as repo
from app.account_security import audit
from app.config import get_settings
from app.services.email_receipts import ReceiptError, parse_receipt
from app.services.normalizer import normalize_merchant

CONSENT = "synthetic-mailbox-v1"
DISCLOSURE = (
    "Synthetic mailbox rehearsal only: committed fixtures, no Google account or inbox access. "
    "Only extracted receipt fields are stored; bodies, headers and addresses are discarded. "
    "Evidence never changes spending totals. Confirm a bank match explicitly. "
    "No mailbox data is sent to AI or used for provider negotiations. "
    "Sync may repeat hourly while the local worker runs. "
    "Disconnect purges mailbox evidence and cancels sync."
)
DATA = Path(__file__).resolve().parents[2] / "data/receipts"


def now():
    return datetime.now(timezone.utc)


def available():
    cfg = get_settings()
    return (
        cfg.mailbox_lab_enabled
        and cfg.environment != "production"
        and not cfg.public_demo_only
        and cfg.llm_provider == "fake"
    )


def require_enabled():
    if not available():
        raise HTTPException(
            404,
            {
                "code": "mailbox_disabled",
                "message": "Synthetic mailbox lab is disabled; live Gmail is unavailable",
            },
        )


def connection(db, user_id, *, lock=False):
    query = select(m.MailboxConnection).where(m.MailboxConnection.user_id == user_id)
    return db.scalar(query.with_for_update() if lock else query)


def connect(db, user_id, version):
    require_enabled()
    if version != CONSENT:
        raise HTTPException(
            422, {"code": "consent_version", "message": "Review the current disclosure"}
        )
    repo.lock_ingestion(db, user_id)
    if repo.get_user(db, user_id, lock=True) is None:
        raise HTTPException(401, {"code": "unauthorized", "message": "Session expired"})
    row = connection(db, user_id, lock=True)
    if row is None:
        row = repo.create_owned(
            db,
            user_id,
            m.MailboxConnection,
            mode="synthetic",
            consent_version=version,
            consented_at=now(),
        )
    elif row.mode != "synthetic":
        raise HTTPException(
            409, {"code": "disconnect_first", "message": "Disconnect the previous connection first"}
        )
    elif row.consented_at is None or row.consent_version != version:
        row.generation += 1
        row.consented_at, row.disconnected_at, row.consent_version = now(), None, version
        db.execute(
            update(m.MailboxSync)
            .where(
                m.MailboxSync.user_id == user_id, m.MailboxSync.status.in_(("queued", "running"))
            )
            .values(
                status="cancelled",
                claim_token=None,
                lease_until=None,
                failure_code="consent_changed",
            )
        )
    audit(db, user_id, "mailbox_consent")
    db.commit()
    return row


def disconnect(db, user_id):
    repo.lock_ingestion(db, user_id)
    row = connection(db, user_id, lock=True)
    counts = {"receipt_evidence": 0, "mailbox_syncs": 0, "oauth_states": 0}
    if row:
        row.generation += 1
        row.consented_at, row.token_cipher, row.disconnected_at = None, None, now()
        counts["receipt_evidence"] = db.execute(
            delete(m.ReceiptEvidence).where(m.ReceiptEvidence.user_id == user_id)
        ).rowcount
        counts["mailbox_syncs"] = db.execute(
            delete(m.MailboxSync).where(m.MailboxSync.user_id == user_id)
        ).rowcount
    counts["oauth_states"] = db.execute(
        delete(m.MailboxOAuthState).where(m.MailboxOAuthState.user_id == user_id)
    ).rowcount
    audit(db, user_id, "mailbox_disconnected")
    db.commit()
    return counts


def fixture_names():
    # Frozen allowlist, never a filename supplied by a client, email or provider.
    return sorted(json.loads((DATA / "ground_truth.json").read_text(encoding="utf-8"))["cases"])


def enqueue(db, user_id):
    require_enabled()
    db.execute(text("SELECT pg_advisory_xact_lock(170017)"))
    row = connection(db, user_id, lock=True)
    if (
        row is None
        or row.consented_at is None
        or row.mode != "synthetic"
        or row.consent_version != CONSENT
    ):
        raise HTTPException(
            409, {"code": "mailbox_consent", "message": "Consent to the synthetic lab first"}
        )
    active = db.scalar(
        select(m.MailboxSync).where(
            m.MailboxSync.user_id == user_id, m.MailboxSync.status.in_(("queued", "running"))
        )
    )
    if active:
        return active
    busy = db.scalar(
        select(func.count())
        .select_from(m.MailboxSync)
        .where(m.MailboxSync.status.in_(("queued", "running")))
    )
    if busy >= 32:
        raise HTTPException(
            429, {"code": "mailbox_capacity", "message": "Sync capacity is full; retry later"}
        )
    job = repo.create_owned(
        db,
        user_id,
        m.MailboxSync,
        connection_id=row.id,
        generation=row.generation,
        total=len(fixture_names()),
        expires_at=now() + timedelta(minutes=30),
    )
    db.commit()
    return job


def candidates(db, user_id, evidence):
    if (
        not evidence.merchant
        or normalize_merchant(evidence.merchant) == "unknown"
        or not evidence.charged_on
        or evidence.amount is None
    ):
        return []
    return repo.list_owned(
        db,
        user_id,
        m.Transaction,
        m.Transaction.type == "debit",
        m.Transaction.currency == "INR",
        m.Transaction.upload_id.in_(
            select(m.Upload.id).where(
                m.Upload.user_id == user_id, m.Upload.source_type != "email_receipt"
            )
        ),
        m.Transaction.amount == evidence.amount,
        m.Transaction.merchant_normalized == normalize_merchant(evidence.merchant),
        m.Transaction.date.between(
            evidence.charged_on - timedelta(days=3), evidence.charged_on + timedelta(days=3)
        ),
        limit=20,
        order_by=m.Transaction.date,
    )


def evidence_action(db, user_id, evidence_id, body):
    require_enabled()
    row = db.scalar(
        select(m.ReceiptEvidence)
        .where(m.ReceiptEvidence.user_id == user_id, m.ReceiptEvidence.id == evidence_id)
        .with_for_update()
    )
    if row is None:
        raise HTTPException(404, {"code": "not_found", "message": "Receipt evidence not found"})
    if body.action == "review":
        row.merchant = normalize_merchant(body.merchant)
        row.charged_on, row.amount = body.charged_on, body.amount
        row.status, row.transaction_id, row.reviewed_at = "pending", None, now()
    elif body.action == "ignore":
        row.status, row.transaction_id, row.reviewed_at = "ignored", None, now()
    else:
        matches = {item.id for item in candidates(db, user_id, row)}
        if body.transaction_id not in matches:
            raise HTTPException(
                404, {"code": "not_found", "message": "Matching bank debit not found"}
            )
        row.status, row.transaction_id, row.reviewed_at = "matched", body.transaction_id, now()
    audit(db, user_id, "receipt_reviewed")
    db.commit()
    return row


def claim(engine, *, instant=None):
    """Worker-only global claim; input is fixture indexes, never email bytes or credentials."""
    instant = instant or now()
    with Session(engine) as db, db.begin():
        # Terminal TTL/attempt failure is visible and never retried forever.
        db.execute(
            update(m.MailboxSync)
            .where(
                m.MailboxSync.status.in_(("queued", "running")),
                or_(
                    m.MailboxSync.expires_at <= instant,
                    (m.MailboxSync.attempts >= 3)
                    & (
                        m.MailboxSync.lease_until.is_(None) | (m.MailboxSync.lease_until <= instant)
                    ),
                ),
            )
            .values(
                status="failed", claim_token=None, lease_until=None, failure_code="sync_expired"
            )
        )
        row = db.scalar(
            select(m.MailboxSync)
            .where(
                m.MailboxSync.expires_at > instant,
                m.MailboxSync.attempts < 3,
                or_(
                    (m.MailboxSync.status == "queued") & (m.MailboxSync.available_at <= instant),
                    (m.MailboxSync.status == "running") & (m.MailboxSync.lease_until <= instant),
                ),
            )
            .order_by(m.MailboxSync.created_at, m.MailboxSync.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if row is None:
            return None
        row.status, row.claim_token = "running", uuid.uuid4()
        row.attempts += 1
        row.lease_until = instant + timedelta(seconds=30)
        return row.id, row.user_id, row.claim_token


def step(engine, identity, *, parser=parse_receipt):
    """Fence each independently committed item; crash resumes at the last committed cursor."""
    job_id, user_id, token = identity
    with Session(engine) as db, db.begin():
        if repo.get_user(db, user_id, lock=True) is None:
            return False
        owner = connection(db, user_id, lock=True)
        row = db.scalar(
            select(m.MailboxSync)
            .where(
                m.MailboxSync.user_id == user_id,
                m.MailboxSync.id == job_id,
                m.MailboxSync.claim_token == token,
                m.MailboxSync.status == "running",
                m.MailboxSync.lease_until > now(),
                m.MailboxSync.expires_at > now(),
            )
            .with_for_update()
        )
        if row is None:
            return False
        if (
            not available()
            or owner is None
            or owner.consented_at is None
            or owner.generation != row.generation
            or owner.mode != "synthetic"
            or owner.consent_version != CONSENT
        ):
            row.status, row.claim_token, row.failure_code = "cancelled", None, "consent_unavailable"
            return False
        if row.processed >= row.total:
            row.status, row.claim_token, row.lease_until = "done", None, None
            row.failure_code = None
            return False
        name = fixture_names()[row.processed]
        try:
            item = parser((DATA / name).read_bytes())["rows"][0]
            digest = hashlib.sha256(("synthetic:" + name).encode()).hexdigest()
            statement = (
                insert(m.ReceiptEvidence)
                .values(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    connection_id=owner.id,
                    message_digest=digest,
                    merchant=item["description"] or None,
                    charged_on=date.fromisoformat(item["date"]) if item["date"] else None,
                    amount=Decimal(item["amount"]) if item["amount"] else None,
                    flags=item["flags"],
                )
                .on_conflict_do_nothing(constraint="uq_receipt_message")
                .returning(m.ReceiptEvidence.id)
            )
            if db.scalar(statement):
                row.accepted += 1
            else:
                row.duplicates += 1
        except ReceiptError:
            row.rejected += 1  # No rejected content is stored or logged.
        row.processed += 1
        if row.processed == row.total:
            row.status, row.claim_token, row.lease_until, row.failure_code = (
                "done",
                None,
                None,
                None,
            )
            return False
        row.lease_until = now() + timedelta(seconds=30)
        return True


def run_once(engine):
    if not available():
        return False
    identity = claim(engine)
    if identity is None:
        return False
    try:
        for _ in range(17):
            if not step(engine, identity):
                break
    except Exception:
        job_id, user_id, token = identity
        with Session(engine) as db, db.begin():
            db.execute(
                update(m.MailboxSync)
                .where(
                    m.MailboxSync.user_id == user_id,
                    m.MailboxSync.id == job_id,
                    m.MailboxSync.claim_token == token,
                )
                .values(
                    status="queued",
                    claim_token=None,
                    lease_until=None,
                    available_at=now() + timedelta(seconds=5),
                    failure_code="sync_unavailable",
                )
            )
    return True


def maintenance(engine):
    instant = now()
    with Session(engine) as db, db.begin():
        # Retention enumerates ownership IDs only; every deletion below stays user-scoped.
        owners = list(db.scalars(select(m.User.id)))
        for user_id in owners:
            db.execute(
                delete(m.MailboxOAuthState).where(
                    m.MailboxOAuthState.user_id == user_id,
                    m.MailboxOAuthState.expires_at <= instant,
                )
            )
            db.execute(
                delete(m.MailboxSync).where(
                    m.MailboxSync.user_id == user_id,
                    m.MailboxSync.expires_at <= instant - timedelta(days=7),
                )
            )
            db.execute(
                update(m.ReceiptEvidence)
                .where(
                    m.ReceiptEvidence.user_id == user_id,
                    func.coalesce(m.ReceiptEvidence.reviewed_at, m.ReceiptEvidence.created_at)
                    <= instant - timedelta(days=30),
                )
                .values(
                    merchant=None,
                    charged_on=None,
                    amount=None,
                    flags=["retention_purged"],
                    status=case(
                        (m.ReceiptEvidence.status == "pending", "ignored"),
                        else_=m.ReceiptEvidence.status,
                    ),
                )
            )


def queue_due(engine):
    if not available():
        return 0
    with Session(engine) as db:
        owners = list(
            db.scalars(
                select(m.MailboxConnection.user_id)
                .where(
                    m.MailboxConnection.consented_at.is_not(None),
                    m.MailboxConnection.mode == "synthetic",
                    m.MailboxConnection.consent_version == CONSENT,
                )
                .order_by(m.MailboxConnection.user_id)
                .limit(100)
            )
        )
    created = 0
    for user_id in owners:
        with Session(engine) as db:
            latest = db.scalar(
                select(func.max(m.MailboxSync.created_at)).where(m.MailboxSync.user_id == user_id)
            )
            if latest and latest > now() - timedelta(hours=1):
                continue
            try:
                enqueue(db, user_id)
                created += 1
            except HTTPException:
                db.rollback()
    return created
