"""JWT-scoped synthetic rehearsal. Live Gmail is explicitly unavailable in every environment."""

import uuid
from typing import Literal

from fastapi import Request

from app import auth
from app import models as m
from app import repositories as repo
from app import schemas as s
from app.api.routes import CurrentUser, Db, Limit, Offset, fail, router
from app.services import mailbox_lab as lab
from app.services import plan_interests as interests


@router.get("/mailbox/config", response_model=s.MailboxConfig, tags=["mailbox"])
def config(user: CurrentUser, db: Db):
    row = lab.connection(db, user.id)
    return dict(
        enabled=lab.available(),
        mode="synthetic" if lab.available() else "disabled",
        live_available=False,
        connected=bool(row and row.consented_at and row.consent_version == lab.CONSENT),
        disclosure=lab.DISCLOSURE,
        consent_version=lab.CONSENT,
        interest_disclosure=interests.DISCLOSURE,
        interest_version=interests.VERSION,
    )


@router.post("/mailbox/synthetic/connect", response_model=s.MailboxConfig, tags=["mailbox"])
def connect(body: s.MailboxConsent, user: CurrentUser, db: Db, request: Request):
    lab.require_enabled()
    auth.limiter.check(request, "mailbox-connect:" + str(user.id))
    lab.connect(db, user.id, body.version)
    return config(user, db)


@router.post(
    "/mailbox/gmail/authorize",
    response_model=s.MessageResult,
    tags=["mailbox"],
    responses={503: {"model": s.ErrorEnvelope}},
)
def gmail_authorize(user: CurrentUser):
    """Launch-blocked. Never emits an OAuth URL or requests provider credentials."""
    fail(
        503,
        "gmail_launch_blocked",
        "Live Gmail requires owner and Google approvals; no inbox was accessed",
    )


@router.delete("/mailbox/connection", response_model=s.DeleteResult, tags=["mailbox"])
def disconnect(user: CurrentUser, db: Db):
    # Remains available after the flag is disabled so consent/data can always be withdrawn.
    return dict(deleted=lab.disconnect(db, user.id))


@router.post("/mailbox/sync", response_model=s.MailboxSyncOut, status_code=202, tags=["mailbox"])
def sync(user: CurrentUser, db: Db, request: Request):
    lab.require_enabled()
    auth.limiter.check(request, "mailbox-sync:" + str(user.id))
    return lab.enqueue(db, user.id)


@router.get("/mailbox/sync/{sync_id}", response_model=s.MailboxSyncOut, tags=["mailbox"])
def sync_status(sync_id: uuid.UUID, user: CurrentUser, db: Db):
    row = repo.get_owned(db, user.id, m.MailboxSync, sync_id)
    if row is None:
        fail(404, "not_found", "Sync not found")
    return row


def evidence_out(db, user_id, row):
    value = s.ReceiptEvidenceOut.model_validate(row)
    value.candidates = [
        s.BankCandidate.model_validate(tx) for tx in lab.candidates(db, user_id, row)
    ]
    return value


@router.get("/mailbox/evidence", response_model=s.Page[s.ReceiptEvidenceOut], tags=["mailbox"])
def evidence(
    user: CurrentUser,
    db: Db,
    status: Literal["pending", "matched", "ignored"] = "pending",
    limit: Limit = 20,
    offset: Offset = 0,
):
    lab.require_enabled()
    condition = m.ReceiptEvidence.status == status
    rows = repo.list_owned(
        db,
        user.id,
        m.ReceiptEvidence,
        condition,
        offset=offset,
        limit=limit,
        order_by=m.ReceiptEvidence.created_at,
    )
    return dict(
        items=[evidence_out(db, user.id, row) for row in rows],
        total=repo.count_owned(db, user.id, m.ReceiptEvidence, condition),
        limit=limit,
        offset=offset,
    )


@router.patch(
    "/mailbox/evidence/{evidence_id}", response_model=s.ReceiptEvidenceOut, tags=["mailbox"]
)
def review(evidence_id: uuid.UUID, body: s.EvidenceDecision, user: CurrentUser, db: Db):
    return evidence_out(db, user.id, lab.evidence_action(db, user.id, evidence_id, body))


@router.get("/interests", response_model=s.InterestOut, tags=["interests"])
def get_interests(user: CurrentUser, db: Db):
    lab.require_enabled()
    return dict(
        categories=[r.category for r in interests.preferences(db, user.id)],
        consent_version=interests.VERSION,
        disclosure=interests.DISCLOSURE,
    )


@router.put("/interests", response_model=s.InterestOut, tags=["interests"])
def put_interests(body: s.InterestPut, user: CurrentUser, db: Db):
    lab.require_enabled()
    if body.version != interests.VERSION:
        fail(422, "consent_version", "Review the current interest disclosure")
    interests.replace(db, user.id, body.categories)
    return get_interests(user, db)


@router.delete("/interests", response_model=s.MessageResult, tags=["interests"])
def delete_interests(user: CurrentUser, db: Db):
    interests.replace(db, user.id, [])
    return dict(message="Voluntary interest declarations withdrawn")


@router.get("/ops/interest-cohorts", include_in_schema=False)
def interest_cohorts(request: Request, db: Db):
    from app.api.ops import authorize

    authorize(request)
    lab.require_enabled()
    return dict(cohorts=interests.cohorts(db), disclosure_threshold=10, provider_sharing=False)
