"""Development receipt previews reuse owned storage, review and durable CSV ingestion."""

from datetime import timedelta

from fastapi import HTTPException

from app import models as m
from app import repositories as repo
from app.config import get_settings
from app.statement_jobs import now


def fail(status, code, message):
    raise HTTPException(status, dict(code=code, message=message))


def require_enabled():
    cfg = get_settings()
    if cfg.public_demo_only:
        fail(403, "demo_data_only", "Receipt uploads are disabled in the public demo")
    if not cfg.receipt_import_enabled or cfg.environment == "production":
        fail(404, "receipt_import_disabled", "Receipt-import development foundation is disabled")
    if cfg.llm_provider != "fake":
        fail(
            409, "receipt_offline_only", "Receipt-import foundation requires the offline assistant"
        )


def ensure_source(db, user_id, source_type):
    """Caller holds the ingestion lock; never count one payment from bank and email twice."""
    if source_type == "email_receipt":
        require_enabled()
        mixed = repo.count_owned(db, user_id, m.Upload, m.Upload.source_type != "email_receipt")
    else:
        mixed = repo.count_owned(db, user_id, m.Upload, m.Upload.source_type == "email_receipt")
    if mixed:
        fail(
            409,
            "receipt_source_conflict",
            "Receipt and statement histories cannot be mixed before bank reconciliation exists. "
            "Use a separate empty local account for synthetic receipt imports.",
        )


def create(db, user_id, result):
    repo.lock_ingestion(db, user_id)
    if repo.get_user(db, user_id, lock=True) is None:
        fail(401, "unauthorized", "Invalid or expired credentials")
    ensure_source(db, user_id, "email_receipt")
    cfg = get_settings()
    instant = now()
    repo.purge_statement_previews(db, user_id, instant)
    if (
        repo.count_owned(
            db,
            user_id,
            m.StatementPreview,
            m.StatementPreview.status.in_(["ready", "pending", "processing"]),
        )
        >= cfg.statement_concurrent_limit
    ):
        fail(429, "preview_busy", "Confirm or cancel an existing preview before another receipt")
    usage = repo.statement_usage(db, user_id, instant.date())
    if usage.attempts >= cfg.statement_daily_limit:
        fail(429, "preview_quota", "Daily preview quota reached; try again tomorrow")
    usage.attempts += 1
    usage.flagged_rows += len(result["rows"])
    row = repo.create_owned(
        db,
        user_id,
        m.StatementPreview,
        filename="receipt.eml",
        source_type="email_receipt",
        status="ready",
        stage="review_required",
        processed_pages=1,
        total_pages=1,
        expires_at=instant + timedelta(minutes=cfg.statement_preview_ttl_minutes),
        payload=result,
    )
    db.commit()
    return row
