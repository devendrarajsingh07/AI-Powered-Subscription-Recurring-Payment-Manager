import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import get_settings
from app.jobs import run_jobs


def scheduled_job(engine):
    try:
        return run_jobs(engine)
    except Exception:
        # SQL/SMTP exceptions can contain private parameters; never forward traceback text.
        logging.getLogger("subtrack.alerts").error("Scheduled alert job could not complete")
        return None


def start_scheduler(engine):
    cfg = get_settings()
    scheduler = BackgroundScheduler(timezone=cfg.app_timezone)
    scheduler.add_job(
        scheduled_job,
        CronTrigger(
            hour=cfg.alert_job_hour, minute=cfg.alert_job_minute, timezone=cfg.app_timezone
        ),
        args=[engine],
        id="daily-alerts",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    return scheduler
