"""Stateless API dispatcher and separate PostgreSQL job consumer. No accepted background gap."""

import logging
from threading import Event, Thread

from cryptography.fernet import InvalidToken
from sqlalchemy import exists, func, select, update
from sqlalchemy.orm import Session

from app import models as m
from app import repositories as repo
from app.config import get_settings
from app.services import durable_queue as queue
from app.services import extractor_rpc
from app.services.ingestion import CsvValidationError, parse_csv
from app.services.statement_extraction import ExtractionError

logger = logging.getLogger("subtrack.durable")


class Dispatcher:
    """API-side admission only: all capacity and durable input live in PostgreSQL."""

    durable = True

    def __init__(self, engine):
        self.engine, self.previews = engine, self

    def reserve(self):
        # Compatibility with inline handlers. Real admission is enqueue(), before DB commit.
        return True

    def release(self):
        """Rollback undoes admission; there is no process-local reservation."""

    def recover(self):
        """Keep legacy interrupted-work recovery; never fail an accepted durable job."""
        with Session(self.engine) as db:
            users = list(db.scalars(select(m.User.id)))
        for user_id in users:
            with Session(self.engine) as db, db.begin():
                if repo.get_user(db, user_id, lock=True) is None:
                    continue
                for model, field in (
                    (m.Upload, m.DurableJob.upload_id),
                    (m.StatementPreview, m.DurableJob.preview_id),
                ):
                    orphan = ~exists(
                        select(m.DurableJob.id).where(
                            m.DurableJob.user_id == user_id,
                            field == model.id,
                        )
                    )
                    values = dict(
                        status="failed",
                        stage="interrupted",
                        error_message="Processing was interrupted; choose the file again.",
                    )
                    if model is m.StatementPreview:
                        values.update(payload={}, error_code="interrupted")
                    db.execute(
                        update(model)
                        .where(
                            model.user_id == user_id,
                            model.status.in_(("pending", "processing")),
                            orphan,
                        )
                        .values(**values)
                    )

    def close(self):
        """This dispatcher owns no pool, timer or thread."""

    def submit(self, *args, **kwargs):
        raise RuntimeError("Durable jobs must be enqueued atomically before acknowledgement")

    def enqueue(self, db, user_id, upload_id, data, mapping, *, as_of):
        return queue.enqueue(
            db, user_id, kind="csv", subject_id=upload_id, data=data, mapping=mapping, as_of=as_of
        )

    def preflight(self, user_id, preview_id, data, filename, password, *, cancelled=lambda: False):
        with Session(self.engine) as db:
            row = db.scalar(
                select(m.DurableJob).where(
                    m.DurableJob.user_id == user_id,
                    m.DurableJob.preview_id == preview_id,
                    m.DurableJob.status == "staging",
                )
            )
            if row is None:
                return
            job_id, token = row.id, row.claim_token

        def invalid():
            if cancelled():
                return True
            with Session(self.engine) as db:
                return (
                    db.scalar(
                        select(m.DurableJob.id).where(
                            m.DurableJob.user_id == user_id,
                            m.DurableJob.id == job_id,
                            m.DurableJob.status == "staging",
                            m.DurableJob.claim_token == token,
                            m.DurableJob.lease_until > queue.utcnow(),
                            m.DurableJob.expires_at > queue.utcnow(),
                        )
                    )
                    is None
                )

        try:
            cleaned = extractor_rpc.call(
                data, filename, password=password, preflight=True, cancelled=invalid
            )
            with Session(self.engine) as db, db.begin():
                queue.activate_staging(db, user_id, job_id, token, cleaned)
        except ExtractionError as exc:
            with Session(self.engine) as db, db.begin():
                queue.reject_staging(db, user_id, job_id, token, code=exc.code, message=str(exc))


class Worker:
    def __init__(self, engine, *, stop=None):
        self.engine, self.stop = engine, stop or Event()

    def maintenance(self):
        queue.expire(self.engine)
        # Global maintenance enumerates IDs only, then every delete is scoped to its owner.
        with Session(self.engine) as db:
            users = list(db.scalars(select(m.User.id)))
        for user_id in users:
            with Session(self.engine) as db, db.begin():
                if (
                    db.scalar(
                        select(m.User.id)
                        .where(m.User.id == user_id)
                        .with_for_update(skip_locked=True)
                    )
                    is None
                ):
                    continue
                repo.purge_statement_previews(db, user_id, queue.utcnow())

    def run_once(self):
        claim = queue.claim_next(self.engine)
        if claim is None:
            return False
        self.execute(claim)
        return True

    def _progress(self, claim, model, subject_id, **values):
        with Session(self.engine) as db, db.begin():
            db.execute(
                update(model)
                .where(
                    model.user_id == claim.user_id,
                    model.id == subject_id,
                    model.status.in_(("pending", "processing")),
                    exists(
                        select(m.DurableJob.id).where(
                            m.DurableJob.id == claim.job_id,
                            m.DurableJob.user_id == claim.user_id,
                            m.DurableJob.claim_token == claim.token,
                            m.DurableJob.status == "running",
                            m.DurableJob.lease_until > func.now(),
                            m.DurableJob.expires_at > func.now(),
                        )
                    ),
                )
                .values(**values)
            )

    def execute(self, claim):
        if claim.exhausted:
            queue.failed(
                self.engine,
                claim.user_id,
                claim.job_id,
                claim.token,
                permanent=True,
                code="input_unavailable",
            )
            return
        finished, lost = Event(), Event()

        def keep_lease():
            while not finished.wait(max(1, get_settings().job_lease_seconds // 3)):
                try:
                    if not queue.heartbeat(self.engine, claim.user_id, claim.job_id, claim.token):
                        lost.set()
                        return
                except Exception:
                    lost.set()
                    return

        heartbeat = Thread(target=keep_lease, daemon=True)
        heartbeat.start()

        def cancelled():
            return self.stop.is_set() or lost.is_set()

        try:
            with Session(self.engine) as db:
                row = repo.get_owned(db, claim.user_id, m.DurableJob, claim.job_id)
                if row is None or row.claim_token != claim.token:
                    return
                data, mapping = queue.unseal(row.encrypted_input)
                kind, upload_id, preview_id, as_of = (
                    row.kind,
                    row.upload_id,
                    row.preview_id,
                    row.as_of,
                )
                if preview_id:
                    preview = repo.get_owned(db, claim.user_id, m.StatementPreview, preview_id)
                    if preview is None:
                        return
                    filename = preview.filename
            if cancelled():
                return
            if kind == "csv":

                def progress(**values):
                    self._progress(claim, m.Upload, upload_id, **values)

                progress(status="processing", stage="parsing")
                parsed = parse_csv(data, mapping)
                progress(
                    total_rows=parsed.row_count,
                    row_count=parsed.row_count,
                    malformed_count=parsed.skipped_count,
                    warnings=[dict(line=e.line, reason=e.reason) for e in parsed.errors[:100]],
                    stage="waiting_for_user_lock",
                )
            else:
                self._progress(
                    claim, m.StatementPreview, preview_id, status="processing", stage="extracting"
                )
                result = extractor_rpc.call(
                    data,
                    filename,
                    cancelled=cancelled,
                    progress=lambda done, total: self._progress(
                        claim,
                        m.StatementPreview,
                        preview_id,
                        processed_pages=done,
                        total_pages=total,
                        stage="extracting_pages",
                    ),
                )
            if cancelled():
                return
            # Owner -> job order matches cancellation and deletion. Holding the job lock fences
            # every financial/preview write; acknowledgement and input deletion commit with them.
            with Session(self.engine) as db, db.begin():
                if repo.get_user(db, claim.user_id, lock=True) is None:
                    return
                job = queue.locked_claim(db, claim.user_id, claim.job_id, claim.token)
                if job is None:
                    return
                if kind == "csv":
                    from app.uploads import persist_parsed

                    persist_parsed(
                        db, claim.user_id, upload_id, parsed, as_of=as_of, progress=progress
                    )
                else:
                    preview = repo.get_owned(db, claim.user_id, m.StatementPreview, preview_id)
                    if preview is None or preview.status != "processing":
                        return
                    preview.payload, preview.source_type = result, result["source_type"]
                    preview.status, preview.stage = "ready", "review"
                    repo.statement_usage(
                        db, claim.user_id, preview.created_at.date()
                    ).flagged_rows += result["flagged_count"]
                if queue.utcnow() >= job.expires_at:
                    raise TimeoutError
                queue.acknowledge(job)
            logger.info("Job completed job_id=%s user_id=%s", claim.job_id, claim.user_id)
        except InvalidToken:
            queue.failed(
                self.engine,
                claim.user_id,
                claim.job_id,
                claim.token,
                permanent=True,
                code="input_unavailable",
            )
        except ExtractionError as exc:
            queue.failed(
                self.engine,
                claim.user_id,
                claim.job_id,
                claim.token,
                permanent=exc.code != "extractor_unavailable",
                code="extraction_failed",
                preview_error=exc.code,
            )
        except (CsvValidationError, TimeoutError):
            queue.failed(self.engine, claim.user_id, claim.job_id, claim.token, permanent=True)
        except Exception:
            # SQL/provider/parser exceptions may contain private values; never stringify them.
            logger.warning("Job attempt failed job_id=%s", claim.job_id)
            try:
                queue.failed(self.engine, claim.user_id, claim.job_id, claim.token)
            except Exception:
                logger.warning("Job lease left for recovery job_id=%s", claim.job_id)
        finally:
            finished.set()
            heartbeat.join(timeout=2)
