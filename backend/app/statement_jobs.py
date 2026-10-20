"""Single-instance preview jobs; original bytes/password live in memory and private temp only."""

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import BoundedSemaphore, Event, Thread

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models as m
from app import repositories as repo
from app.config import get_settings
from app.services.extraction_runner import run_extraction
from app.services.statement_extraction import ExtractionError

logger = logging.getLogger("subtrack.statements")


def now():
    return datetime.now(timezone.utc)


class PreviewWorker:
    def __init__(self, engine):
        self.engine = engine
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="subtrack-preview")
        self.capacity = BoundedSemaphore(4)
        self.stop = Event()
        self.purger = None

    def reserve(self):
        return self.capacity.acquire(blocking=False)

    def release(self):
        self.capacity.release()

    def start_purge(self):
        def loop():
            while not self.stop.wait(30):
                try:
                    self.purge()
                except Exception:
                    logger.warning("Preview cleanup deferred")

        self.purger = Thread(target=loop, daemon=True, name="subtrack-preview-purge")
        self.purger.start()

    def purge(self):
        with Session(self.engine) as db:
            users = list(db.scalars(select(m.User.id)))
        for user_id in users:
            with Session(self.engine) as db, db.begin():
                repo.purge_statement_previews(db, user_id, now())

    def recover(self):
        from app.services.extraction_runner import purge_abandoned_temps

        purge_abandoned_temps()
        with Session(self.engine) as db:
            users = list(db.scalars(select(m.User.id)))
        for user_id in users:
            with Session(self.engine) as db, db.begin():
                repo.purge_statement_previews(db, user_id, now())
                for row in repo.list_owned(
                    db,
                    user_id,
                    m.StatementPreview,
                    m.StatementPreview.status.in_(["pending", "processing"]),
                    limit=None,
                ):
                    row.status, row.stage, row.payload = "failed", "interrupted", {}
                    row.error_code = "interrupted"
                    row.error_message = "Preview was interrupted. Choose the local file again."

    def submit(self, user_id, preview_id, data, filename, password):
        try:
            self.pool.submit(self._run, user_id, preview_id, data, filename, password)
        except Exception:
            self.release()
            raise

    def _run(self, user_id, preview_id, data, filename, password):
        try:
            self._update(user_id, preview_id, status="processing", stage="extracting")

            def cancelled():
                with Session(self.engine) as db:
                    row = repo.get_owned(db, user_id, m.StatementPreview, preview_id)
                    return (
                        row is None
                        or row.status not in ("pending", "processing")
                        or row.expires_at <= now()
                    )

            def progress(done, total):
                self._update(
                    user_id,
                    preview_id,
                    processed_pages=done,
                    total_pages=total,
                    stage="extracting_pages",
                )

            result = run_extraction(
                data,
                filename,
                password,
                config=get_settings(),
                progress=progress,
                cancelled=cancelled,
            )
            with Session(self.engine) as db, db.begin():
                row = repo.get_owned(db, user_id, m.StatementPreview, preview_id)
                if row is None or row.status != "processing" or row.expires_at <= now():
                    return
                row.payload, row.source_type, row.status, row.stage = (
                    result,
                    result["source_type"],
                    "ready",
                    "review",
                )
                usage = repo.statement_usage(db, user_id, row.created_at.date())
                usage.flagged_rows += result["flagged_count"]
            logger.info("Preview ready preview_id=%s row_count=%d", preview_id, len(result["rows"]))
        except Exception as exc:
            code = exc.code if isinstance(exc, ExtractionError) else "extraction_failed"
            message = (
                str(exc)
                if isinstance(exc, ExtractionError)
                else "Statement could not be read safely. Re-export it or use CSV."
            )
            self._update(
                user_id,
                preview_id,
                status="failed",
                stage="failed",
                payload={},
                error_code=code,
                error_message=message,
            )
            logger.info("Preview failed preview_id=%s", preview_id)
        finally:
            self.release()

    def _update(self, user_id, preview_id, **values):
        with Session(self.engine) as db, db.begin():
            row = repo.get_owned(db, user_id, m.StatementPreview, preview_id)
            if row and row.status in ("pending", "processing"):
                for key, value in values.items():
                    setattr(row, key, value)
                if values.get("status") == "failed":
                    repo.statement_usage(db, user_id, row.created_at.date()).failures += 1

    def close(self):
        self.stop.set()
        if self.purger:
            self.purger.join(timeout=1)
        self.pool.shutdown(wait=True, cancel_futures=False)
