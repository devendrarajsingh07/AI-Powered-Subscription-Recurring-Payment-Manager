"""Separate worker entry point; no HTTP trigger, no in-process API executor."""

import argparse
import logging
import signal
import time
from datetime import datetime
from pathlib import Path
from threading import Event
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_engine
from app.durable_worker import Worker
from app.migrations import database_at_head

ALIVE = Path("/tmp/subtrack-worker-alive")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--health", action="store_true")
    args = parser.parse_args()
    cfg = get_settings()
    if args.health:
        limit = max(cfg.statement_timeout_seconds, cfg.job_lease_seconds) * 2 + 10
        try:
            with Session(get_engine()) as db:
                healthy = (
                    ALIVE.exists()
                    and time.time() - ALIVE.stat().st_mtime < limit
                    and database_at_head(db)
                )
        except Exception:
            healthy = False
        raise SystemExit(0 if healthy else 1)
    if cfg.job_mode != "postgres":
        raise SystemExit("The separate worker requires JOB_MODE=postgres")
    # Production is still independently fail-closed until remaining work/owner gates are met.
    if cfg.environment == "production":
        raise SystemExit("Private beta launch remains blocked by Phase8 operational gates")
    stop = Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    worker = Worker(get_engine(), stop=stop)
    # This process is the single scheduler owner. The alert job holds a PostgreSQL advisory lock,
    # so even if several workers run, only one executes at a time and delivery is idempotent.
    timers = Timers(cfg)
    while not stop.is_set():
        ALIVE.touch()
        try:
            timers.tick(worker)
            worked = worker.run_once()
        except Exception:
            logging.getLogger("subtrack.worker").warning("Worker coordination unavailable")
            worked = False
        if args.once:
            break
        if not worked:
            stop.wait(0.5)


class Timers:
    """Monotonic schedules for maintenance, retention, alert retries and the daily alert job."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.next_run = dict.fromkeys(("maintenance", "retry", "retention", "demo"), 0.0)
        self.daily_done = None

    def due(self, name, every):
        now = time.monotonic()
        if now < self.next_run[name]:
            return False
        self.next_run[name] = now + every
        return True

    def tick(self, worker):
        log = logging.getLogger("subtrack.worker")
        if self.due("maintenance", 5):
            worker.maintenance()
        if self.due("retention", 3600):
            from app.services.retention import purge

            log.info("Retention completed counts=%s", purge(worker.engine))
        if self.cfg.public_demo_only and self.due("demo", 900):
            from app.services.demo_retention import purge_demo_accounts

            purge_demo_accounts(worker.engine)
        if self.cfg.scheduler_enabled:
            from app.jobs import run_jobs

            if self.due("retry", self.cfg.alert_retry_poll_seconds):
                run_jobs(worker.engine, retry_only=True)
            local = datetime.now(ZoneInfo(self.cfg.app_timezone))
            due_today = (local.hour, local.minute) >= (
                self.cfg.alert_job_hour,
                self.cfg.alert_job_minute,
            )
            if due_today and self.daily_done != local.date():
                run_jobs(worker.engine)
                self.daily_done = local.date()


if __name__ == "__main__":
    main()
