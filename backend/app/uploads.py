"""Bounded in-process work with persisted progress and atomic financial writes."""

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import repositories as repo
from app.config import get_settings
from app.db import get_engine
from app.models import Upload, User
from app.services.ingestion import parse_csv
from app.services.insights import regenerate

logger = logging.getLogger("subtrack.uploads")


class UploadWorker:
    def __init__(self, engine, *, workers=None, queue_limit=None):
        self.engine = engine
        config = get_settings()
        self.pool = ThreadPoolExecutor(
            max_workers=workers or config.upload_workers, thread_name_prefix="subtrack-upload"
        )
        self.capacity = BoundedSemaphore(queue_limit or config.upload_queue_limit)
        from app.statement_jobs import PreviewWorker

        self.previews = PreviewWorker(engine)

    def reserve(self):
        return self.capacity.acquire(blocking=False)

    def release(self):
        self.capacity.release()

    def submit(self, user_id, upload_id, data, mapping, *, as_of):
        try:
            return self.pool.submit(self._run, user_id, upload_id, data, mapping, as_of)
        except Exception:
            self.release()
            self._failed(user_id, upload_id)
            raise

    def close(self):
        self.previews.close()
        self.pool.shutdown(wait=True, cancel_futures=False)

    def recover(self):
        self.previews.recover()
        self.previews.start_purge()
        # System bootstrap enumerates account IDs only, then uses scoped repository operations.
        with Session(self.engine) as db:
            user_ids = list(db.scalars(select(User.id)))
        for user_id in user_ids:
            with Session(self.engine) as db, db.begin():
                if repo.get_user(db, user_id, lock=True):
                    repo.recover_uploads(db, user_id)

    def _progress(self, user_id, upload_id, **values):
        with Session(self.engine) as db, db.begin():
            repo.update_upload(db, user_id, upload_id, **values)

    def _failed(self, user_id, upload_id):
        self._progress(
            user_id,
            upload_id,
            inflight_only=True,
            status="failed",
            stage="failed",
            processed_rows=0,
            inserted_count=0,
            duplicate_count=0,
            detected_count=0,
            error_message=(
                "Upload processing failed. No financial changes were saved; retry the file."
            ),
        )

    def _run(self, user_id: uuid.UUID, upload_id: uuid.UUID, data: bytes, mapping, as_of):
        try:
            self._progress(user_id, upload_id, status="processing", stage="parsing")
            parsed = parse_csv(data, mapping)
            warnings = [dict(line=error.line, reason=error.reason) for error in parsed.errors[:100]]
            self._progress(
                user_id,
                upload_id,
                total_rows=parsed.row_count,
                row_count=parsed.row_count,
                malformed_count=parsed.skipped_count,
                warnings=warnings,
                stage="waiting_for_user_lock",
            )
            with Session(self.engine) as db, db.begin():
                result = persist_parsed(
                    db,
                    user_id,
                    upload_id,
                    parsed,
                    as_of=as_of,
                    progress=lambda **values: self._progress(user_id, upload_id, **values),
                )
                if result is None:
                    return
                inserted, detected = result
            logger.info(
                "Upload completed upload_id=%s inserted_count=%d detected_count=%d",
                upload_id,
                inserted,
                detected,
            )
        except Exception:
            # Never log exception/SQL parameters, raw descriptions, amounts or file bytes.
            logger.error("Upload failed upload_id=%s", upload_id)
            try:
                self._failed(user_id, upload_id)
            except Exception:
                logger.error("Upload failure status could not be saved upload_id=%s", upload_id)
        finally:
            self.release()


def persist_parsed(db, user_id, upload_id, parsed, *, as_of, progress):
    """Shared financial transaction body. Caller owns commit; no process-local dispatch here."""
    if repo.get_user(db, user_id, lock=True) is None:
        return None
    if repo.get_owned(db, user_id, Upload, upload_id) is None:
        return None
    inserted = 0
    for offset in range(0, len(parsed.transactions), 500):
        chunk = parsed.transactions[offset : offset + 500]
        inserted += repo.insert_transactions(db, user_id, upload_id, chunk)
        progress(
            stage="ingesting", processed_rows=min(offset + len(chunk), len(parsed.transactions))
        )
    progress(stage="detecting")
    detected = repo.redetect(db, user_id, as_of=as_of)
    regenerate(db, user_id, as_of=as_of)
    from app.services.demo import finalize

    finalize(db, user_id, upload_id, as_of=as_of)
    repo.update_upload(
        db,
        user_id,
        upload_id,
        status="done",
        stage="done",
        processed_rows=parsed.row_count,
        total_rows=parsed.row_count,
        inserted_count=inserted,
        duplicate_count=len(parsed.transactions) - inserted,
        detected_count=detected,
    )
    return inserted, detected


def get_worker():
    """Dependency is replaced with an isolated worker in PostgreSQL integration tests."""
    return worker


worker: UploadWorker | None = None


def start_worker():
    global worker
    if get_settings().job_mode == "postgres":
        from app.durable_worker import Dispatcher

        worker = Dispatcher(get_engine())
    else:
        worker = UploadWorker(get_engine())
    worker.recover()
    return worker
