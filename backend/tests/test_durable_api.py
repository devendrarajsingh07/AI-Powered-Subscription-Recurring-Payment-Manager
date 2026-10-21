"""Authenticated API -> PostgreSQL queue -> real consumer; never mock a happy-path handler."""

import json
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select
from test_api import DATA, MAPPING, account, expected_totals, subs
from test_durable_worker import FIXTURES, private_rpc  # noqa: F401 - pytest fixture

from app import models as m
from app import repositories as repo
from app.config import get_settings
from app.durable_worker import Dispatcher, Worker
from app.main import app
from app.services import durable_queue as q
from app.uploads import get_worker


@pytest.fixture
def durable_api(api_client, pg_engine, monkeypatch):
    monkeypatch.setenv("JOB_MODE", "postgres")
    get_settings.cache_clear()
    app.dependency_overrides[get_worker] = lambda: Dispatcher(pg_engine)
    return api_client


def submit(client, headers):
    response = client.post(
        "/api/v1/uploads",
        headers=headers,
        files={"file": ("synthetic.csv", (DATA / "sample_transactions.csv").read_bytes())},
        data={"mapping": json.dumps(MAPPING)},
    )
    assert response.status_code == 202
    return response.json()


def test_durable_upload_preview_queue_detect_summary_and_idempotent_reupload(
    durable_api,
    pg_engine,
    db,
):
    client = durable_api
    headers, user = account(client)
    preview = client.post(
        "/api/v1/uploads/preview",
        headers=headers,
        files={"file": ("synthetic.csv", (DATA / "sample_transactions.csv").read_bytes())},
    )
    assert preview.status_code == 200 and preview.json()["suggested_mapping"] == MAPPING
    first = submit(client, headers)
    # Consumer is deliberately stopped: acknowledged input remains durable and pending.
    assert first["status"] == "pending"
    job = client.get("/api/v1/jobs", headers=headers).json()["items"][0]
    assert job["status"] == "queued" and job["upload_id"] == first["id"]
    assert "encrypted_input" not in job and "claim_token" not in job
    assert Worker(pg_engine).run_once()
    truth = json.loads((DATA / "ground_truth.json").read_text())["patterns"]
    actual = subs(client, headers)
    assert sorted((s["merchant"], s["cadence"]) for s in actual) == sorted(
        (p["merchant"], p["cadence"]) for p in truth
    )
    expected_month, expected_year = expected_totals(truth)
    summary = client.get("/api/v1/summary", headers=headers).json()
    assert (summary["monthly_equivalent"], summary["yearly_total"]) == (
        str(expected_month),
        str(expected_year),
    )
    target = actual[0]
    assert (
        client.patch(
            "/api/v1/subscriptions/" + target["id"],
            headers=headers,
            json={"user_confirmed": True, "category": "software"},
        ).status_code
        == 200
    )
    second = submit(client, headers)
    assert Worker(pg_engine).run_once()
    assert (
        client.get("/api/v1/uploads/" + second["id"], headers=headers).json()["inserted_count"] == 0
    )
    assert {s["id"] for s in subs(client, headers)} == {s["id"] for s in actual}
    persisted = client.get("/api/v1/subscriptions/" + target["id"], headers=headers).json()
    assert persisted["user_confirmed"] and persisted["category"] == "software"
    assert repo.count_owned(db, uuid.UUID(user["id"]), m.Transaction) == 399
    assert all(
        row.encrypted_input is None
        for row in repo.list_owned(db, uuid.UUID(user["id"]), m.DurableJob)
    )


def test_jobs_isolation_strict_action_cancel_and_delete(durable_api, pg_engine, db):
    a, ua = account(durable_api)
    b, ub = account(durable_api)
    submit(durable_api, a)
    job = durable_api.get("/api/v1/jobs", headers=a).json()["items"][0]
    path = "/api/v1/jobs/" + job["id"]
    assert durable_api.get(path, headers=b).status_code == 404
    assert durable_api.patch(path, headers=b, json={"action": "cancel"}).status_code == 404
    assert (
        durable_api.patch(
            path, headers=a, json={"action": "cancel", "user_id": ub["id"]}
        ).status_code
        == 422
    )
    assert durable_api.patch(path, headers=a, json={"action": "retry"}).status_code == 422
    assert (
        durable_api.patch(path, headers=a, json={"action": "cancel"}).json()["status"]
        == "cancelled"
    )
    db.expire_all()
    assert db.get(m.DurableJob, uuid.UUID(job["id"])).encrypted_input is None
    assert not Worker(pg_engine).run_once()
    submit(durable_api, a)
    result = durable_api.delete("/api/v1/me/data", headers=a)
    assert result.status_code == 200 and result.json()["deleted"]["durable_jobs"] == 2
    assert repo.count_owned(db, uuid.UUID(ua["id"]), m.DurableJob) == 0
    assert durable_api.get("/api/v1/auth/me", headers=b).status_code == 200
    assert durable_api.get("/api/v1/jobs", headers=b).json()["total"] == 0


def test_expired_job_visible_terminal_and_original_removed(durable_api, pg_engine, db):
    headers, user = account(durable_api)
    submit(durable_api, headers)
    row = db.scalar(select(m.DurableJob).where(m.DurableJob.user_id == uuid.UUID(user["id"])))
    row.expires_at = q.utcnow() - timedelta(seconds=1)
    db.commit()
    Worker(pg_engine).maintenance()
    visible = durable_api.get("/api/v1/jobs?status=dead_letter", headers=headers).json()
    assert visible["total"] == 1 and visible["items"][0]["failure_code"] == "expired"
    db.expire_all()
    assert db.get(m.DurableJob, row.id).encrypted_input is None


def test_api_recovery_preserves_accepted_jobs_and_marks_only_legacy_orphans(
    durable_api,
    pg_engine,
    db,
):
    headers, user = account(durable_api)
    upload = submit(durable_api, headers)
    legacy = repo.create_owned(db, uuid.UUID(user["id"]), m.Upload, filename="legacy.csv")
    legacy_id = legacy.id
    db.commit()
    Dispatcher(pg_engine).recover()
    db.expire_all()
    assert db.get(m.Upload, legacy_id).status == "failed"
    assert db.get(m.Upload, uuid.UUID(upload["id"])).status == "pending"
    assert Worker(pg_engine).run_once()
    assert (
        durable_api.get("/api/v1/uploads/" + upload["id"], headers=headers).json()["status"]
        == "done"
    )


def test_encrypted_pdf_api_preflight_real_rpc_review_and_ingestion(
    durable_api,
    pg_engine,
    db,
    private_rpc,  # noqa: F811
):
    headers, user = account(durable_api)
    for password, expected in (("wrong", "wrong_password"), ("FixtureOnly42!", None)):
        response = durable_api.post(
            "/api/v1/uploads/preview",
            headers=headers,
            files={"file": ("synthetic.pdf", (FIXTURES / "encrypted.pdf").read_bytes())},
            data={"password": password},
        )
        assert response.status_code == 202
        preview = response.json()
        if expected:
            assert preview["status"] == "failed" and preview["error_code"] == expected
        else:
            assert Worker(pg_engine).run_once()
            preview = durable_api.get(
                "/api/v1/uploads/previews/" + preview["id"], headers=headers
            ).json()
            assert preview["status"] == "ready"
            edits = [{"index": row["index"], "verified": True} for row in preview["result"]["rows"]]
            result = durable_api.post(
                "/api/v1/uploads",
                headers=headers,
                data={"preview_id": preview["id"], "edits": json.dumps(edits)},
            )
            assert result.status_code == 202
            assert Worker(pg_engine).run_once()
            assert (
                durable_api.get("/api/v1/uploads/" + result.json()["id"], headers=headers).json()[
                    "inserted_count"
                ]
                == 399
            )
    assert repo.count_owned(db, uuid.UUID(user["id"]), m.Transaction) == 399
