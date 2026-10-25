import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event

import pytest
from phase5_helpers import DAY, owner, plan

from app import models as m
from app import repositories as repo
from app.config import get_settings
from app.jobs import business_date, run_jobs
from app.services.alerts import generate
from app.services.notifier import ConsoleNotifier

NOW = datetime(2026, 10, 18, 3, 30, tzinfo=timezone.utc)


def events(db, user_id, kind=None):
    db.expire_all()
    conditions = [m.Alert.kind == kind] if kind else []
    return repo.list_owned(db, user_id, m.Alert, *conditions, limit=None)


def setup_plan(db, **values):
    user = owner(db)
    sub = plan(db, user.id, **values)
    db.commit()
    return user.id, sub.id


def test_real_outbox_idempotent_and_restart(pg_engine, db, tmp_path):
    uid, _ = setup_plan(db)
    assert run_jobs(pg_engine, as_of=DAY, now=NOW, notifier=ConsoleNotifier(tmp_path))["sent"] == 1
    first = events(db, uid)[0]
    assert first.sent_at == NOW and first.attempt_count == 1
    snapshot = first.payload.copy()
    assert run_jobs(pg_engine, as_of=DAY, now=NOW, notifier=ConsoleNotifier(tmp_path))["sent"] == 0
    assert len(events(db, uid)) == 1
    assert events(db, uid)[0].payload == snapshot
    assert len(list(tmp_path.rglob("*.eml"))) == 1


def test_overlapping_jobs_one_delivery(pg_engine, db, tmp_path):
    uid, _ = setup_plan(db)
    entered, release = Event(), Event()

    class BlockingConsole(ConsoleNotifier):
        def send(self, mail):
            entered.set()
            assert release.wait(10)
            super().send(mail)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(
            run_jobs, pg_engine, as_of=DAY, now=NOW, notifier=BlockingConsole(tmp_path)
        )
        assert entered.wait(10)
        second = pool.submit(
            run_jobs, pg_engine, as_of=DAY, now=NOW, notifier=ConsoleNotifier(tmp_path)
        )
        assert second.result(timeout=10)["locked"] == 1
        release.set()
        assert first.result(timeout=10)["sent"] == 1
    assert len(events(db, uid)) == 1
    assert len(list(tmp_path.rglob("*.eml"))) == 1


def test_unsent_lead_time_recomputed_but_sent_cycle_never_resent(pg_engine, db, tmp_path):
    uid, _ = setup_plan(db, next_expected=DAY + timedelta(days=7))
    generate(db, uid, as_of=DAY, now=NOW)
    db.commit()
    alert_id = events(db, uid)[0].id
    user = repo.get_user(db, uid)
    user.alert_lead_days = 1
    generate(db, uid, as_of=DAY, now=NOW)
    db.commit()
    assert events(db, uid)[0].send_on == DAY + timedelta(days=6)
    assert events(db, uid)[0].id == alert_id
    assert (
        run_jobs(pg_engine, as_of=DAY + timedelta(days=4), notifier=ConsoleNotifier(tmp_path))[
            "sent"
        ]
        == 0
    )
    assert (
        run_jobs(pg_engine, as_of=DAY + timedelta(days=6), notifier=ConsoleNotifier(tmp_path))[
            "sent"
        ]
        == 1
    )
    db.expire_all()
    repo.get_user(db, uid).alert_lead_days = 2
    db.commit()
    assert (
        run_jobs(pg_engine, as_of=DAY + timedelta(days=7), notifier=ConsoleNotifier(tmp_path))[
            "sent"
        ]
        == 0
    )
    assert len(list(tmp_path.rglob("*.eml"))) == 1


@pytest.mark.parametrize(
    "email,enabled,reason",
    [(None, True, "No notification email"), ("notify@example.org", False, "disabled")],
)
def test_missing_email_and_disabled_are_skipped(pg_engine, db, tmp_path, email, enabled, reason):
    user = owner(db, notification_email=email, enabled=enabled)
    plan(db, user.id)
    db.commit()
    for _ in range(2):
        run_jobs(pg_engine, as_of=DAY, now=NOW, notifier=ConsoleNotifier(tmp_path))
    row = events(db, user.id)[0]
    assert row.status == "skipped" and row.sent_at is None and row.attempt_count == 0
    assert reason in row.safe_failure_reason
    assert not list(tmp_path.rglob("*.eml"))


@pytest.mark.parametrize(
    "values",
    [
        dict(status="cancelled"),
        dict(status="dismissed"),
        dict(kind="fixed_bill"),
        dict(possibly_cancelled=True),
        # An overdue prediction alone now rolls forward. Two actually missed cycles
        # make it ineligible, even if a stale persisted uncertainty flag is false.
        dict(last_charge=DAY - timedelta(days=100), next_expected=DAY - timedelta(days=1)),
    ],
)
def test_ineligible_renewals_never_alert(pg_engine, db, tmp_path, values):
    uid, _ = setup_plan(db, **values)
    run_jobs(pg_engine, as_of=DAY, now=NOW, notifier=ConsoleNotifier(tmp_path))
    assert events(db, uid) == []
    assert not list(tmp_path.rglob("*.eml"))


def test_budget_once_each_month_and_ist_boundary(pg_engine, db, tmp_path):
    uid, _ = setup_plan(db, next_expected=DAY + timedelta(days=50))
    from decimal import Decimal

    repo.create_owned(db, uid, m.Budget, monthly_limit=Decimal("50"))
    db.commit()
    before_midnight = datetime(2026, 9, 30, 18, 29, tzinfo=timezone.utc)
    midnight = before_midnight + timedelta(minutes=1)
    assert business_date(before_midnight, "Asia/Kolkata").isoformat() == "2026-09-30"
    assert business_date(midnight, "Asia/Kolkata").isoformat() == "2026-10-01"
    for now in (before_midnight, before_midnight, midnight, midnight):
        run_jobs(pg_engine, now=now, notifier=ConsoleNotifier(tmp_path))
    rows = events(db, uid, "budget")
    assert len(rows) == 2 and all(row.status == "sent" for row in rows)
    assert {row.send_on.isoformat() for row in rows} == {"2026-09-01", "2026-10-01"}
    assert all(
        row.payload["overage"] == "50.00" and row.payload["total"] == "100.00" for row in rows
    )
    assert len(list(tmp_path.rglob("*.eml"))) == 2


def test_overage_cleared_before_send_is_skipped(pg_engine, db, tmp_path):
    from decimal import Decimal

    uid, _ = setup_plan(db, next_expected=DAY + timedelta(days=7))
    budget = repo.create_owned(db, uid, m.Budget, monthly_limit=Decimal("50"))
    generate(db, uid, as_of=DAY, now=NOW)
    db.commit()
    budget.monthly_limit = Decimal("1000")
    db.commit()
    run_jobs(pg_engine, as_of=DAY, now=NOW, notifier=ConsoleNotifier(tmp_path))
    assert events(db, uid, "budget")[0].status == "skipped"
    assert not list(tmp_path.rglob("*.eml"))


def test_bounded_failures_backoff_safe_logs(pg_engine, db, monkeypatch, caplog):
    uid, _ = setup_plan(db)
    monkeypatch.setattr(get_settings(), "alert_retry_seconds", 10)

    class Failing:
        def send(self, mail):
            raise RuntimeError("private SMTP secret and notify@example.org INR 100.00")

    caplog.set_level(logging.INFO, logger="subtrack.alerts")
    for seconds in (0, 1, 10, 11, 30, 31, 1000):
        run_jobs(pg_engine, as_of=DAY, now=NOW + timedelta(seconds=seconds), notifier=Failing())
    row = events(db, uid)[0]
    assert row.status == "failed" and row.sent_at is None and row.attempt_count == 3
    assert "retry limit" in row.safe_failure_reason
    assert all(
        private not in caplog.text for private in ("SMTP secret", "notify@example.org", "100.00")
    )


def test_success_after_one_retry(pg_engine, db, tmp_path, monkeypatch):
    uid, _ = setup_plan(db)
    monkeypatch.setattr(get_settings(), "alert_retry_seconds", 1)

    class Once(ConsoleNotifier):
        calls = 0

        def send(self, mail):
            self.calls += 1
            if self.calls == 1:
                raise OSError("synthetic transport failure")
            super().send(mail)

    sender = Once(tmp_path)
    run_jobs(pg_engine, as_of=DAY, now=NOW, notifier=sender)
    assert events(db, uid)[0].sent_at is None
    run_jobs(pg_engine, as_of=DAY, now=NOW + timedelta(seconds=1), notifier=sender)
    run_jobs(pg_engine, as_of=DAY, now=NOW + timedelta(seconds=2), notifier=sender)
    assert events(db, uid)[0].attempt_count == 2
    assert events(db, uid)[0].status == "sent"
    assert len(list(tmp_path.rglob("*.eml"))) == 1


def test_crash_after_publication_reuses_same_outbox_artifact(pg_engine, db, tmp_path, monkeypatch):
    uid, _ = setup_plan(db)
    monkeypatch.setattr(get_settings(), "alert_retry_seconds", 1)

    class ProcessCrash(BaseException):
        pass

    class Crashing(ConsoleNotifier):
        def send(self, mail):
            super().send(mail)
            raise ProcessCrash()

    with pytest.raises(ProcessCrash):
        run_jobs(pg_engine, as_of=DAY, now=NOW, notifier=Crashing(tmp_path))
    row = events(db, uid)[0]
    assert row.sent_at is None and row.attempt_count == 1
    original = next(tmp_path.rglob("*.eml")).read_bytes()
    repo.get_user(db, uid).alerts_enabled = False
    db.commit()
    run_jobs(
        pg_engine,
        as_of=DAY + timedelta(days=8),
        now=NOW + timedelta(days=8),
        notifier=ConsoleNotifier(tmp_path),
    )
    # Rolling an overdue cycle can also create a *different*, disabled future alert.
    # Verify recovery of the actual published event, not arbitrary UUID list ordering.
    restored = {event.id: event for event in events(db, uid)}[row.id]
    assert restored.status == "sent"
    assert restored.sent_at == NOW
    assert all(event.status == "skipped" for event in events(db, uid) if event.id != row.id)
    assert len(list(tmp_path.rglob("*.eml"))) == 1
    assert next(tmp_path.rglob("*.eml")).read_bytes() == original


def test_scheduler_uses_configured_ist_time(pg_engine):
    from app.scheduler import start_scheduler

    scheduler = start_scheduler(pg_engine)
    try:
        job = scheduler.get_job("daily-alerts")
        next_fire = job.trigger.get_next_fire_time(
            None, datetime(2026, 10, 18, 0, tzinfo=timezone.utc)
        )
        assert next_fire.hour == get_settings().alert_job_hour
        assert str(next_fire.tzinfo) == get_settings().app_timezone
    finally:
        scheduler.shutdown(wait=True)


def test_disable_suppresses_existing_unsent_event_and_enable_can_resume(pg_engine, db, tmp_path):
    uid, _ = setup_plan(db, next_expected=DAY + timedelta(days=7))
    generate(db, uid, as_of=DAY, now=NOW)
    db.commit()
    alert_id = events(db, uid)[0].id
    repo.get_user(db, uid).alerts_enabled = False
    db.commit()
    run_jobs(pg_engine, as_of=DAY + timedelta(days=4), notifier=ConsoleNotifier(tmp_path))
    assert events(db, uid)[0].id == alert_id
    assert events(db, uid)[0].status == "skipped"
    assert not list(tmp_path.rglob("*.eml"))
    repo.get_user(db, uid).alerts_enabled = True
    db.commit()
    run_jobs(pg_engine, as_of=DAY + timedelta(days=4), notifier=ConsoleNotifier(tmp_path))
    assert events(db, uid)[0].status == "sent"
    assert len(list(tmp_path.rglob("*.eml"))) == 1


def test_invalid_recipient_is_terminal_and_private(pg_engine, db, tmp_path, caplog):
    uid, _ = setup_plan(db)
    repo.get_user(db, uid).notification_email = "invalid-private-address"
    db.commit()
    with caplog.at_level(logging.INFO):
        run_jobs(pg_engine, as_of=DAY, notifier=ConsoleNotifier(tmp_path))
    row = events(db, uid)[0]
    assert row.status == "failed" and row.attempt_count == 1 and row.sent_at is None
    assert "invalid" in row.safe_failure_reason
    assert "invalid-private-address" not in caplog.text
    assert not list(tmp_path.rglob("*.eml"))


def test_scheduler_hides_transport_exception_details(monkeypatch, caplog):
    from app import scheduler

    def failure(*args, **kwargs):
        raise RuntimeError("private@example.org amount=12345.67")

    monkeypatch.setattr(scheduler, "run_jobs", failure)
    with caplog.at_level(logging.ERROR):
        scheduler.scheduled_job(None)
    assert "Scheduled alert job could not complete" in caplog.text
    assert "private@example.org" not in caplog.text
    assert "12345.67" not in caplog.text
