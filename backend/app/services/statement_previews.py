"""Scoped preview lifecycle and review -> existing ingestion. No original-file persistence."""

from datetime import timedelta

from fastapi import HTTPException
from pydantic import TypeAdapter, ValidationError

from app import models as m
from app import repositories as repo
from app import schemas as s
from app.config import get_settings
from app.services.normalizer import safe_display
from app.services.statement_extraction import ExtractionError, sniff, validate_row, virtual_csv
from app.statement_jobs import now


def fail(status, code, message):
    raise HTTPException(status, dict(code=code, message=message))


def output(row):
    result = dict(row.payload) if row.payload else None
    if result:
        result["rows"] = [
            dict(item, description=safe_display(item["description"])) for item in result["rows"]
        ]
    return dict(
        id=row.id,
        filename=row.filename,
        status=row.status,
        stage=row.stage,
        source_type=row.source_type,
        processed_pages=row.processed_pages,
        total_pages=row.total_pages,
        expires_at=row.expires_at,
        error_code=row.error_code,
        error_message=row.error_message,
        result=result,
        upload_id=row.upload_id,
    )


def owned(db, user_id, preview_id):
    row = repo.get_owned(db, user_id, m.StatementPreview, preview_id)
    if row is None:
        fail(404, "not_found", "Preview not found")
    if row.expires_at <= now():
        repo.purge_statement_previews(db, user_id, now())
        db.commit()
        fail(404, "preview_expired", "Preview expired; choose the local file again")
    return row


def create(db, user_id, data, filename, worker, *, as_of=None, preflight=False):
    cfg = get_settings()
    if len(data) > cfg.statement_max_mb * 1024 * 1024:
        fail(413, "file_too_large", "PDF/image exceeds the configured limit (maximum 10 MB)")
    try:
        kind = sniff(data, filename)
    except ExtractionError as exc:
        fail(422, exc.code, str(exc))
    repo.lock_ingestion(db, user_id)
    if repo.get_user(db, user_id, lock=True) is None:
        fail(401, "unauthorized", "Invalid or expired credentials")
    repo.purge_statement_previews(db, user_id, now())
    if (
        repo.count_owned(
            db,
            user_id,
            m.StatementPreview,
            m.StatementPreview.status.in_(["pending", "processing"]),
        )
        >= cfg.statement_concurrent_limit
    ):
        fail(429, "preview_busy", "Wait for or cancel an existing preview")
    usage = repo.statement_usage(db, user_id, now().date())
    if usage.attempts >= cfg.statement_daily_limit:
        fail(429, "preview_quota", "Daily statement preview quota reached; try again tomorrow")
    if not worker.previews.reserve():
        fail(429, "preview_busy", "Statement preview queue is full; try again shortly")
    try:
        usage.attempts += 1
        row = repo.create_owned(
            db,
            user_id,
            m.StatementPreview,
            filename=safe_display(filename.replace("\\", "/").split("/")[-1])[:255],
            source_type="pdf_text" if kind == "pdf" else "image_ocr",
            expires_at=now() + timedelta(minutes=cfg.statement_preview_ttl_minutes),
        )
        if getattr(worker, "durable", False):
            from app.clock import today
            from app.services.durable_queue import enqueue

            enqueue(
                db,
                user_id,
                kind="extraction",
                subject_id=row.id,
                data=None if preflight else data,
                mapping=None,
                as_of=as_of or today(),
                expires_at=row.expires_at,
                staging=preflight,
            )
            if preflight:
                row.stage = "checking_password"
        db.commit()
        return row
    except Exception:
        worker.previews.release()
        db.rollback()
        raise


def confirm(db, user_id, preview_id, edits_text, worker, *, as_of=None):
    repo.lock_ingestion(db, user_id)
    if repo.get_user(db, user_id, lock=True) is None:
        fail(401, "unauthorized", "Invalid or expired credentials")
    row = owned(db, user_id, preview_id)
    if row.status == "confirmed":
        return repo.get_owned(db, user_id, m.Upload, row.upload_id), None
    if row.status != "ready":
        fail(409, "preview_not_ready", "Wait for a ready preview before importing")
    if repo.count_owned(db, user_id, m.Upload, m.Upload.source == "demo"):
        fail(
            409,
            "remove_demo_first",
            "Remove demo data in Settings before importing a real statement",
        )
    try:
        edits = TypeAdapter(list[s.RowEdit]).validate_json(edits_text)
        if len(edits) > 5000 or len({edit.index for edit in edits}) != len(edits):
            raise ValueError
        indexed = {item["index"]: dict(item) for item in row.payload["rows"]}
        if any(edit.index not in indexed for edit in edits):
            raise ValueError
    except (ValueError, ValidationError):
        fail(
            422,
            "invalid_review",
            "Review edits need unique existing row indexes, valid dates and decimal-string amounts",
        )
    edited, selected = 0, []
    decisions = {edit.index: edit for edit in edits}
    excluded = 0
    for index, item in indexed.items():
        edit = decisions.get(index)
        if edit and edit.delete:
            excluded += 1
            continue
        if item["flags"] and not (edit and edit.verified):
            excluded += 1
            continue
        if edit:
            values = edit.model_dump(mode="json", exclude_unset=True)
            changed = {
                key: value
                for key, value in values.items()
                if key not in ("index", "verified", "delete")
            }
            if changed:
                edited += 1
                item.update(changed)
        if validate_row(item) is None:
            fail(
                422,
                "invalid_review_row",
                "Correct the date, description, amount and debit/credit type in every verified row",
            )
        selected.append(item)
    data = virtual_csv(selected)
    if not worker.reserve():
        fail(429, "upload_queue_full", "Upload queue is full; retry after current uploads finish")
    try:
        upload = repo.create_owned(
            db,
            user_id,
            m.Upload,
            filename=row.filename,
            source_type=row.source_type,
            excluded_count=excluded,
            total_rows=len(selected),
            row_count=len(selected),
        )
        row.upload_id, row.status, row.stage, row.payload = upload.id, "confirmed", "importing", {}
        repo.statement_usage(db, user_id, row.created_at.date()).edited_rows += edited
        if getattr(worker, "durable", False):
            from app.clock import today

            worker.enqueue(db, user_id, upload.id, data, None, as_of=as_of or today())
        db.commit()
    except Exception:
        worker.release()
        db.rollback()
        raise
    return upload, data
