"""WP5: single-owner retry loop, documented retention, content-free internal metrics."""

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from phase5_helpers import DAY, owner, plan

from app import models as m
from app import repositories as repo
from app.config import get_settings
from app.jobs import run_jobs
from app.services import retention

NOW = datetime(2026, 10, 18, 3, 30, tzinfo=timezone.utc)
TOKEN = "t" * 24 + "ops-metrics-synthetic-token-1234"


class Flaky:
    """Provider stand-in: fails transiently, then succeeds."""

    def __init__(self, failures):
        self.failures, self.sent = failures, 0

    def send(self, mail):
        if self.failures:
            self.failures -= 1
            raise RuntimeError("synthetic transient outage")
        self.sent += 1


def alerts(db, user_id):
    db.expire_all()
    return repo.list_owned(db, user_id, m.Alert, limit=None)


def test_retry_loop_retries_only_due_retrying_alerts_and_never_generates(pg_engine, db):
    user = owner(db)
    plan(db, user.id)
    db.commit()
    assert run_jobs(pg_engine, as_of=DAY, now=NOW, notifier=Flaky(1))["failed"] == 0
    row = alerts(db, user.id)[0]
    assert row.status == "retrying" and row.attempt_count == 1 and row.next_attempt_at > NOW
    provider = Flaky(0)
    # Not yet due: the short-interval loop does nothing and touches no other account.
    early = run_jobs(pg_engine, as_of=DAY, now=NOW, notifier=provider, retry_only=True)
    assert early == dict(created=0, sent=0, failed=0, locked=0) and provider.sent == 0
    later = NOW + timedelta(hours=1)
    done = run_jobs(pg_engine, as_of=DAY, now=later, notifier=provider, retry_only=True)
    assert done["sent"] == 1 and done["created"] == 0 and provider.sent == 1
    assert alerts(db, user.id)[0].status == "sent"
    # Idempotent: a repeat cannot deliver a second copy.
    again = run_jobs(pg_engine, as_of=DAY, now=later, notifier=provider, retry_only=True)
    assert again["sent"] == 0 and provider.sent == 1


def test_retry_loop_does_not_create_or_send_pending_alerts(pg_engine, db):
    user = owner(db)
    plan(db, user.id)
    db.commit()
    provider = Flaky(0)
    result = run_jobs(pg_engine, as_of=DAY, now=NOW, notifier=provider, retry_only=True)
    assert result["created"] == 0 and provider.sent == 0
    assert alerts(db, user.id) == []


def seed_old_and_new(db, user_id):
    old = datetime.now(timezone.utc) - timedelta(days=400)
    new = datetime.now(timezone.utc)
    for when, label in ((old, "old"), (new, "new")):
        upload = repo.create_owned(db, user_id, m.Upload, filename=f"{label}.csv")
        db.flush()
        db.add(
            m.DurableJob(
                user_id=user_id,
                kind="csv",
                upload_id=upload.id,
                status="done",
                as_of=DAY,
                max_attempts=3,
                expires_at=when,
                created_at=when,
                updated_at=when,
            )
        )
        repo.create_owned(
            db,
            user_id,
            m.ChatMessage,
            role="user",
            content=f"SYNTHETICPRIVATE {label}",
            created_at=when,
        )
        sub = plan(db, user_id)
        db.flush()
        repo.create_owned(
            db,
            user_id,
            m.Alert,
            subscription_id=sub.id,
            kind="renewal",
            event_key=f"renewal:{uuid.uuid4()}",
            send_on=when.date(),
            payload={},
            status="sent",
        )
        db.add(m.SecurityEvent(user_id=user_id, kind="login", created_at=when))
    db.add(m.SecurityEvent(user_id=None, kind="login_failed", created_at=old))
    db.add(m.SecurityEvent(user_id=None, kind="login_failed", created_at=new))


def test_retention_deletes_only_expired_finished_records(pg_engine, db):
    user = owner(db)
    seed_old_and_new(db, user.id)
    db.commit()
    counts = retention.purge(pg_engine)
    assert counts["jobs"] == 1 and counts["chat"] == 1 and counts["alerts"] == 1
    assert counts["audit"] == 2  # One owned and one unknown-login event.
    db.expire_all()
    assert repo.count_owned(db, user.id, m.DurableJob) == 1
    assert [r.content for r in repo.list_owned(db, user.id, m.ChatMessage, limit=None)] == [
        "SYNTHETICPRIVATE new"
    ]
    assert len(alerts(db, user.id)) == 1
    assert all(isinstance(v, int) for v in counts.values())  # Counts only.
    assert retention.purge(pg_engine) == dict.fromkeys(counts, 0)  # Idempotent.


def test_retention_never_removes_active_jobs_or_recent_failures(pg_engine, db):
    user = owner(db)
    old = datetime.now(timezone.utc) - timedelta(days=400)
    for status in ("queued", "running", "dead_letter"):
        upload = repo.create_owned(db, user.id, m.Upload, filename=f"{status}.csv")
        db.flush()
        db.add(
            m.DurableJob(
                user_id=user.id,
                kind="csv",
                upload_id=upload.id,
                status=status,
                as_of=DAY,
                max_attempts=3,
                expires_at=old + timedelta(days=500),
                updated_at=old if status != "dead_letter" else datetime.now(timezone.utc),
            )
        )
    db.commit()
    assert retention.purge(pg_engine)["jobs"] == 0
    assert repo.count_owned(db, user.id, m.DurableJob) == 3


def test_metrics_disabled_without_token_and_hidden_on_wrong_token(api_client, monkeypatch):
    assert api_client.get("/api/v1/ops/metrics").status_code == 404
    monkeypatch.setenv("OPS_METRICS_TOKEN", TOKEN)
    get_settings.cache_clear()
    assert api_client.get("/api/v1/ops/metrics").status_code == 404
    assert (
        api_client.get("/api/v1/ops/metrics", headers={"X-Ops-Token": "x" * 40}).status_code == 404
    )
    assert "/ops/metrics" not in json.dumps(api_client.get("/api/v1/openapi.json").json())


def test_metrics_are_content_free(api_client, pg_engine, db, monkeypatch, caplog):
    monkeypatch.setenv("OPS_METRICS_TOKEN", TOKEN)
    get_settings.cache_clear()
    user = owner(db)
    plan(db, user.id, merchant="SYNTHETICPRIVATE MERCHANT", amount="98765.43")
    seed_old_and_new(db, user.id)
    db.commit()
    caplog.set_level(logging.DEBUG)
    response = api_client.get("/api/v1/ops/metrics", headers={"X-Ops-Token": TOKEN})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "generated_at",
        "queue",
        "alerts",
        "security_events_24h",
        "chat",
        "statements",
        "llm",
        "email",
        "accounts_total",
    }
    text = response.text + caplog.text
    for secret in ("SYNTHETICPRIVATE", "98765", "synthetic-", "@example.org", str(user.id), TOKEN):
        assert secret not in text
    assert body["queue"]["by_kind_status"] == {"csv:done": 2}
    assert body["accounts_total"] == 1
    assert body["chat"]["assistant_messages"] == 0
