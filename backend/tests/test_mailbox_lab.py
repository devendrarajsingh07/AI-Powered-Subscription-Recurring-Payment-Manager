"""Real PostgreSQL and committed synthetic mail only. No provider sockets or personal data."""

import inspect
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError
from sqlalchemy.orm import Session
from test_api import account, load

from app import models as m
from app import repositories as repo
from app.config import Settings, get_settings
from app.services import gmail_protocol as gmail
from app.services import mailbox_lab as lab
from app.services import plan_interests as interests


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv("MAILBOX_LAB_ENABLED", "true")
    monkeypatch.setenv("MAILBOX_TOKEN_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()


def connect(client, headers):
    response = client.post(
        "/api/v1/mailbox/synthetic/connect",
        headers=headers,
        json={"consent": True, "version": lab.CONSENT},
    )
    assert response.status_code == 200, response.text
    assert response.json()["mode"] == "synthetic" and response.json()["connected"]


def sync(client, headers, engine):
    response = client.post("/api/v1/mailbox/sync", headers=headers)
    assert response.status_code == 202, response.text
    assert lab.run_once(engine)
    result = client.get("/api/v1/mailbox/sync/" + response.json()["id"], headers=headers)
    assert result.status_code == 200
    assert result.json()["status"] == "done"
    return result.json()


def test_real_sync_is_idempotent_separate_evidence_and_zero_spend(enabled, api_client, pg_engine):
    headers, user = account(api_client)
    connect(api_client, headers)
    first = sync(api_client, headers, pg_engine)
    truth = json.loads((lab.DATA / "ground_truth.json").read_text(encoding="utf-8"))
    reviews = sum(case["verdict"] == "review" for case in truth["cases"].values())
    assert (first["processed"], first["total"], first["accepted"], first["rejected"]) == (
        len(truth["cases"]),
        len(truth["cases"]),
        reviews,
        len(truth["cases"]) - reviews,
    )
    replay = sync(api_client, headers, pg_engine)
    assert replay["accepted"] == 0 and replay["duplicates"] == reviews
    evidence = api_client.get("/api/v1/mailbox/evidence", headers=headers).json()
    assert evidence["total"] == reviews and all(r["status"] == "pending" for r in evidence["items"])
    assert all(isinstance(r["amount"], str) for r in evidence["items"] if r["amount"])
    assert api_client.get("/api/v1/summary", headers=headers).json()["monthly_equivalent"] == "0.00"
    with Session(pg_engine) as db:
        assert repo.count_owned(db, uuid.UUID(user["id"]), m.Transaction) == 0
        stored = " ".join(
            str(r.flags) + str(r.merchant)
            for r in repo.list_owned(db, uuid.UUID(user["id"]), m.ReceiptEvidence)
        )
        assert "example.org" not in stored and "<script" not in stored
        assert all(
            r.token_cipher is None
            for r in repo.list_owned(db, uuid.UUID(user["id"]), m.MailboxConnection)
        )


def test_bank_matching_requires_explicit_choice_and_never_changes_totals(
    enabled,
    api_client,
    pg_engine,
):
    headers, _ = account(api_client)
    connect(api_client, headers)
    sync(api_client, headers, pg_engine)
    csv = (
        b"date,description,amount,type\n2026-06-30,POS NETFLIX REF1,499,debit\n"
        b"2026-07-01,UPI NETFLIX REF2,499,debit\n2026-07-01,NETFLIX REF3,499,credit\n"
        b"2026-07-01,NETFLIX REF4,499.01,debit\n2026-07-01,SPOTIFY REF5,499,debit\n"
    )
    load(api_client, headers, csv)
    before = api_client.get("/api/v1/summary", headers=headers).json()
    rows = api_client.get("/api/v1/mailbox/evidence", headers=headers).json()["items"]
    row = next(r for r in rows if r["merchant"] == "netflix" and r["charged_on"] == "2026-07-01")
    assert len(row["candidates"]) == 2 and row["transaction_id"] is None
    target = "/api/v1/mailbox/evidence/" + row["id"]
    assert (
        api_client.patch(
            target,
            headers=headers,
            json={"action": "match", "transaction_id": row["candidates"][0]["id"]},
        ).status_code
        == 422
    )
    matched = api_client.patch(
        target,
        headers=headers,
        json={"action": "match", "verified": True, "transaction_id": row["candidates"][0]["id"]},
    )
    assert matched.status_code == 200 and matched.json()["status"] == "matched"
    assert api_client.get("/api/v1/summary", headers=headers).json() == before
    sync(api_client, headers, pg_engine)
    assert (
        api_client.get("/api/v1/mailbox/evidence?status=matched", headers=headers).json()["total"]
        == 1
    )


def test_isolation_unknown_ids_and_strict_decisions(enabled, api_client, pg_engine):
    a, _ = account(api_client)
    b, _ = account(api_client)
    connect(api_client, a)
    job = sync(api_client, a, pg_engine)
    row = api_client.get("/api/v1/mailbox/evidence", headers=a).json()["items"][0]
    assert api_client.get("/api/v1/mailbox/evidence", headers=b).json()["total"] == 0
    assert api_client.get("/api/v1/mailbox/sync/" + job["id"], headers=b).status_code == 404
    assert (
        api_client.patch(
            "/api/v1/mailbox/evidence/" + row["id"], headers=b, json={"action": "ignore"}
        ).status_code
        == 404
    )
    assert (
        api_client.post(
            "/api/v1/mailbox/synthetic/connect",
            headers=b,
            json={"consent": True, "version": lab.CONSENT, "user_id": row["id"]},
        ).status_code
        == 422
    )
    assert api_client.post("/api/v1/mailbox/sync", headers=b).status_code == 409
    assert api_client.delete("/api/v1/mailbox/connection", headers=b).status_code == 200
    assert api_client.get("/api/v1/mailbox/evidence", headers=a).json()["total"] == 12


def test_disconnect_fences_running_sync_and_purges_data(enabled, api_client, pg_engine):
    headers, _ = account(api_client)
    connect(api_client, headers)
    api_client.post("/api/v1/mailbox/sync", headers=headers)
    identity = lab.claim(pg_engine)
    assert lab.step(pg_engine, identity)
    removed = api_client.delete("/api/v1/mailbox/connection", headers=headers).json()["deleted"]
    assert removed["receipt_evidence"] + removed["mailbox_syncs"] >= 1
    assert not lab.step(pg_engine, identity)
    assert api_client.get("/api/v1/mailbox/evidence", headers=headers).json()["total"] == 0
    assert not api_client.get("/api/v1/mailbox/config", headers=headers).json()["connected"]
    connect(api_client, headers)
    assert sync(api_client, headers, pg_engine)["accepted"] == 12


def test_worker_crash_resumes_cursor_and_rejects_old_lease(enabled, api_client, pg_engine):
    headers, _ = account(api_client)
    connect(api_client, headers)
    api_client.post("/api/v1/mailbox/sync", headers=headers)
    old = lab.claim(pg_engine)
    assert lab.step(pg_engine, old)
    with Session(pg_engine) as db, db.begin():
        row = repo.get_owned(db, old[1], m.MailboxSync, old[0])
        row.lease_until = lab.now() - timedelta(seconds=1)
    new = lab.claim(pg_engine)
    assert new[2] != old[2] and not lab.step(pg_engine, old)
    while lab.step(pg_engine, new):
        pass
    with Session(pg_engine) as db:
        row = repo.get_owned(db, old[1], m.MailboxSync, old[0])
        assert row.status == "done" and row.processed == 16 and row.attempts == 2
        assert repo.count_owned(db, old[1], m.ReceiptEvidence) == 12


def test_concurrent_sync_admission_and_claim(enabled, api_client, pg_engine):
    headers, user = account(api_client)
    connect(api_client, headers)
    uid = uuid.UUID(user["id"])

    def enqueue(_):
        with Session(pg_engine) as db:
            return lab.enqueue(db, uid).id

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert len(set(pool.map(enqueue, range(2)))) == 1
        claims = list(pool.map(lambda _: lab.claim(pg_engine), range(2)))
    assert sum(c is not None for c in claims) == 1


def test_failure_attempt_limit_and_ttl(enabled, api_client, pg_engine, monkeypatch):
    headers, user = account(api_client)
    connect(api_client, headers)
    row = api_client.post("/api/v1/mailbox/sync", headers=headers).json()

    def failure(*args, **kwargs):
        raise RuntimeError("synthetic-private-content-that-must-not-be-recorded")

    monkeypatch.setattr(lab, "step", failure)
    for _ in range(3):
        assert lab.run_once(pg_engine)
        with Session(pg_engine) as db, db.begin():
            job = repo.get_owned(db, uuid.UUID(user["id"]), m.MailboxSync, uuid.UUID(row["id"]))
            job.available_at = lab.now() - timedelta(seconds=1)
    assert not lab.run_once(pg_engine)
    result = api_client.get("/api/v1/mailbox/sync/" + row["id"], headers=headers).json()
    assert result["status"] == "failed" and result["attempts"] == 3
    assert "private-content" not in json.dumps(result)


def test_disabled_public_production_live_guards(api_client):
    headers, _ = account(api_client)
    assert not api_client.get("/api/v1/mailbox/config", headers=headers).json()["enabled"]
    assert (
        api_client.post(
            "/api/v1/mailbox/synthetic/connect", headers=headers, content=b"not even JSON"
        ).status_code
        == 404
    )
    for options in (
        {"mailbox_live_enabled": True},
        {"mailbox_lab_enabled": True, "public_demo_only": True},
        {"mailbox_lab_enabled": True, "environment": "production"},
        {"mailbox_lab_enabled": True, "llm_provider": "gemini"},
    ):
        with pytest.raises(ValidationError):
            Settings(**options)
    with pytest.raises(gmail.ProtocolError, match="Live Gmail is disabled"):
        gmail.GmailProtocol()


def test_oauth_state_scoping_single_use_encryption_expiry(enabled, api_client, pg_engine):
    _, user = account(api_client)
    uid = uuid.UUID(user["id"])
    with Session(pg_engine) as db:
        url = gmail.begin(db, uid, "synthetic-client", "https://api.subtrack.test/callback")
        fields = parse_qs(urlsplit(url).query)
        assert fields["scope"] == [gmail.SCOPE] and fields["code_challenge_method"] == ["S256"]
        state = fields["state"][0]
        stored = repo.list_owned(db, uid, m.MailboxOAuthState)[0]
        assert state not in stored.digest and state.encode() not in stored.verifier_cipher
        with pytest.raises(gmail.ProtocolError):
            gmail.consume(db, uuid.uuid4(), state)
        verifier = gmail.consume(db, uid, state)
        assert verifier.encode() not in stored.verifier_cipher
        with pytest.raises(gmail.ProtocolError):
            gmail.consume(db, uid, state)
        url = gmail.begin(db, uid, "synthetic-client", "https://api.subtrack.test/callback")
        with pytest.raises(gmail.ProtocolError):
            gmail.consume(
                db,
                uid,
                parse_qs(urlsplit(url).query)["state"][0],
                now=lab.now() + timedelta(minutes=6),
            )


def test_local_protocol_exchange_raw_refresh_revocation_and_history(caplog):
    requests = []

    def provider(request):
        requests.append(request)
        if request.url.path.endswith("/token"):
            return httpx.Response(
                200,
                json={
                    "token_type": "Bearer",
                    "scope": gmail.SCOPE,
                    "access_token": "synthetic-access-value",
                    "refresh_token": "synthetic-refresh-value",
                    "expires_in": 3600,
                },
            )
        if request.url.path.endswith("/history"):
            return httpx.Response(404, json={"error": "synthetic private provider detail"})
        if request.url.params.get("format") == "raw":
            return httpx.Response(200, json={"raw": "U3ludGhldGlj"})
        return httpx.Response(200, json={})

    client = gmail.GmailProtocol(test_transport=httpx.MockTransport(provider))
    try:
        token = client.exchange(
            code="synthetic-code",
            verifier="synthetic-verifier",
            client_id="synthetic-client",
            client_secret="synthetic-secret",
            redirect_uri="https://api.subtrack.test/callback",
        )
        assert token["expires_in"] == 3600
        client.refresh(
            refresh_token=token["refresh_token"],
            client_id="synthetic-client",
            client_secret="synthetic-secret",
        )
        assert client.raw_message(token["access_token"], "abc123") == b"Synthetic"
        client.revoke(token["refresh_token"])
        with pytest.raises(gmail.HistoryExpired):
            client.messages(token["access_token"], history_id="123")
        assert all(
            r.url.host in ("oauth2.googleapis.com", "gmail.googleapis.com") for r in requests
        )
        assert "code_verifier=synthetic-verifier" in requests[0].content.decode()
        assert "synthetic-secret" not in caplog.text and "private provider" not in caplog.text
    finally:
        client.close()


@pytest.mark.parametrize(
    "status,body",
    [
        (302, {}),
        (500, {"error": "private"}),
        (200, {"scope": [gmail.SCOPE], "token_type": "Bearer"}),
        (200, {"scope": gmail.SCOPE + " https://mail.google.com/", "token_type": "Bearer"}),
    ],
)
def test_protocol_rejects_redirect_errors_and_broader_scope(status, body):
    client = gmail.GmailProtocol(
        test_transport=httpx.MockTransport(lambda _: httpx.Response(status, json=body))
    )
    try:
        with pytest.raises(gmail.ProtocolError):
            client.exchange(
                code="synthetic",
                verifier="synthetic",
                client_id="synthetic",
                client_secret="synthetic",
                redirect_uri="https://api.subtrack.test/callback",
            )
    finally:
        client.close()


def test_interests_are_independent_voluntary_and_withdrawable(enabled, api_client, pg_engine):
    headers, user = account(api_client)
    assert (
        api_client.put(
            "/api/v1/interests",
            headers=headers,
            json={"consent": False, "version": interests.VERSION, "categories": ["music"]},
        ).status_code
        == 422
    )
    response = api_client.put(
        "/api/v1/interests",
        headers=headers,
        json={"consent": True, "version": interests.VERSION, "categories": ["music", "cloud"]},
    )
    assert response.status_code == 200 and set(response.json()["categories"]) == {"music", "cloud"}
    assert "Transaction" not in inspect.getsource(interests)
    assert "ReceiptEvidence" not in inspect.getsource(interests)
    assert api_client.get("/api/v1/ops/interest-cohorts", headers=headers).status_code == 404
    assert api_client.delete("/api/v1/interests", headers=headers).status_code == 200
    with Session(pg_engine) as db:
        assert repo.count_owned(db, uuid.UUID(user["id"]), m.PlanInterest) == 0


def test_delete_cascades_every_new_owned_table_and_preserves_other_user(
    enabled, api_client, pg_engine
):
    a, user = account(api_client)
    b, other = account(api_client)
    connect(api_client, a)
    sync(api_client, a, pg_engine)
    connect(api_client, b)
    sync(api_client, b, pg_engine)
    with Session(pg_engine) as db:
        gmail.begin(db, uuid.UUID(user["id"]), "synthetic", "https://api.subtrack.test/callback")
    assert api_client.delete("/api/v1/me/data", headers=a).status_code == 200
    with Session(pg_engine) as db:
        for model in (
            m.MailboxConnection,
            m.MailboxOAuthState,
            m.MailboxSync,
            m.ReceiptEvidence,
            m.PlanInterest,
        ):
            assert repo.count_owned(db, uuid.UUID(user["id"]), model) == 0
        assert repo.count_owned(db, uuid.UUID(other["id"]), m.ReceiptEvidence) == 12


def test_token_storage_encrypted_refresh_preserved_and_scoped(enabled, api_client, pg_engine):
    _, user = account(api_client)
    uid = uuid.UUID(user["id"])
    with Session(pg_engine) as db:
        connection = repo.create_owned(
            db,
            uid,
            m.MailboxConnection,
            mode="gmail",
            consent_version=lab.CONSENT,
            consented_at=lab.now(),
        )
        db.commit()
        gmail.save_tokens(
            db,
            uid,
            connection.id,
            {
                "access_token": "synthetic-access-value",
                "refresh_token": "synthetic-refresh-value",
                "expires_in": 3600,
            },
        )
        assert b"synthetic-access" not in connection.token_cipher
        gmail.save_tokens(
            db,
            uid,
            connection.id,
            {"access_token": "synthetic-refreshed-access", "expires_in": 3600},
        )
        value = json.loads(gmail.cipher().decrypt(connection.token_cipher))
        assert value["refresh_token"] == "synthetic-refresh-value"
        with pytest.raises(gmail.ProtocolError):
            gmail.save_tokens(db, uuid.uuid4(), connection.id, value)


def test_live_provider_guard_blocks_mailbox_workspaces(enabled, api_client, pg_engine):
    from types import SimpleNamespace

    from app.services.llm import LLMError
    from app.services.llm_controls import guard_user

    headers, user = account(api_client)
    connect(api_client, headers)
    uid = uuid.UUID(user["id"])
    with Session(pg_engine) as db, db.begin():
        repo.get_user(db, uid).live_opt_in = True
    with pytest.raises(LLMError, match="offline-only"):
        guard_user(pg_engine, SimpleNamespace(live=True), 1, uid)


def test_review_invalid_fields_and_ignore_survive_resync(enabled, api_client, pg_engine):
    headers, _ = account(api_client)
    connect(api_client, headers)
    sync(api_client, headers, pg_engine)
    row = next(
        r
        for r in api_client.get("/api/v1/mailbox/evidence", headers=headers).json()["items"]
        if r["amount"] is None
    )
    route = "/api/v1/mailbox/evidence/" + row["id"]
    assert (
        api_client.patch(
            route,
            headers=headers,
            json={
                "action": "review",
                "verified": True,
                "merchant": "netflix",
                "charged_on": "2026-09-01",
                "amount": 499.0,
            },
        ).status_code
        == 422
    )
    reviewed = api_client.patch(
        route,
        headers=headers,
        json={
            "action": "review",
            "verified": True,
            "merchant": "netflix",
            "charged_on": "2026-09-01",
            "amount": "499.00",
        },
    )
    assert reviewed.status_code == 200 and reviewed.json()["amount"] == "499.00"
    assert api_client.patch(route, headers=headers, json={"action": "ignore"}).status_code == 200
    sync(api_client, headers, pg_engine)
    assert (
        api_client.get("/api/v1/mailbox/evidence?status=ignored", headers=headers).json()["total"]
        == 1
    )


def test_consent_size_rate_and_live_route_blocked(enabled, api_client):
    headers, _ = account(api_client)
    assert (
        api_client.post(
            "/api/v1/mailbox/synthetic/connect",
            headers=headers,
            json={"consent": True, "version": "obsolete"},
        ).status_code
        == 422
    )
    assert (
        api_client.post(
            "/api/v1/mailbox/synthetic/connect",
            headers=headers,
            json={"consent": True, "version": lab.CONSENT, "extra": "x" * 32768},
        ).status_code
        == 413
    )
    assert api_client.post("/api/v1/mailbox/gmail/authorize", headers=headers).status_code == 503
    statuses = [
        api_client.post(
            "/api/v1/mailbox/synthetic/connect",
            headers=headers,
            json={"consent": True, "version": lab.CONSENT},
        ).status_code
        for _ in range(12)
    ]
    assert 429 in statuses


def test_scheduled_sync_respects_interval_and_revocation(enabled, api_client, pg_engine):
    headers, user = account(api_client)
    connect(api_client, headers)
    assert lab.queue_due(pg_engine) == 1
    assert lab.run_once(pg_engine)
    assert lab.queue_due(pg_engine) == 0
    with Session(pg_engine) as db, db.begin():
        for job in repo.list_owned(db, uuid.UUID(user["id"]), m.MailboxSync):
            job.created_at = lab.now() - timedelta(hours=2)
    assert lab.queue_due(pg_engine) == 1
    api_client.delete("/api/v1/mailbox/connection", headers=headers)
    assert lab.queue_due(pg_engine) == 0 and not lab.run_once(pg_engine)


def test_oauth_atomic_race_and_key_rotation(enabled, api_client, pg_engine, monkeypatch):
    _, user = account(api_client)
    uid = uuid.UUID(user["id"])
    with Session(pg_engine) as db:
        url = gmail.begin(db, uid, "synthetic", "https://api.subtrack.test/callback")
    state = parse_qs(urlsplit(url).query)["state"][0]

    def consume(_):
        with Session(pg_engine) as db:
            try:
                gmail.consume(db, uid, state)
                return True
            except gmail.ProtocolError:
                return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(consume, range(2))) == 1
    with Session(pg_engine) as db:
        url = gmail.begin(db, uid, "synthetic", "https://api.subtrack.test/callback")
        monkeypatch.setenv("MAILBOX_TOKEN_KEY", Fernet.generate_key().decode())
        get_settings.cache_clear()
        with pytest.raises(gmail.ProtocolError, match="key rotation"):
            gmail.consume(db, uid, parse_qs(urlsplit(url).query)["state"][0])


def test_retention_purges_evidence_and_expired_oauth(enabled, api_client, pg_engine):
    headers, user = account(api_client)
    uid = uuid.UUID(user["id"])
    connect(api_client, headers)
    sync(api_client, headers, pg_engine)
    with Session(pg_engine) as db, db.begin():
        for evidence in repo.list_owned(db, uid, m.ReceiptEvidence):
            evidence.created_at = lab.now() - timedelta(days=31)
        repo.create_owned(
            db,
            uid,
            m.MailboxOAuthState,
            digest="0" * 64,
            verifier_cipher=b"discarded-synthetic",
            expires_at=lab.now() - timedelta(seconds=1),
        )
    lab.maintenance(pg_engine)
    with Session(pg_engine) as db:
        tombstones = repo.list_owned(db, uid, m.ReceiptEvidence)
        assert len(tombstones) == 12
        assert all(
            row.amount is None
            and row.merchant is None
            and row.charged_on is None
            and row.flags == ["retention_purged"]
            for row in tombstones
        )
        assert repo.count_owned(db, uid, m.MailboxOAuthState) == 0
    replay = sync(api_client, headers, pg_engine)
    assert replay["accepted"] == 0 and replay["duplicates"] == 12


def test_cohort_counts_only_declarations_and_suppresses_small_groups(
    enabled, api_client, pg_engine
):
    from app.auth import hash_password

    with Session(pg_engine) as db:
        for index in range(10):
            user = m.User(
                email=f"voluntary-{index}@example.org",
                password_hash=hash_password("SyntheticDemo42!"),
            )
            db.add(user)
            db.flush()
            repo.create_owned(
                db, user.id, m.PlanInterest, category="music", consent_version=interests.VERSION
            )
            if index < 9:
                repo.create_owned(
                    db, user.id, m.PlanInterest, category="cloud", consent_version=interests.VERSION
                )
        db.commit()
        assert interests.cohorts(db) == [{"category": "music", "count": 10}]


def test_protocol_limits_and_no_redirect_following():
    requests = []

    def provider(request):
        requests.append(request)
        return httpx.Response(200, content=b"x" * 65537)

    client = gmail.GmailProtocol(test_transport=httpx.MockTransport(provider))
    try:
        with pytest.raises(gmail.ProtocolError, match="exceeded"):
            client.messages("synthetic-access-value")
        with pytest.raises(gmail.ProtocolError, match="identity"):
            client.raw_message("synthetic-access-value", "../../other-user")
        assert len(requests) == 1
    finally:
        client.close()


def test_oauth_protocol_against_actual_loopback_http_server():
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    from urllib.parse import parse_qs

    received = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            size = int(self.headers.get("Content-Length", "0"))
            assert 0 < size <= 8192
            received.append((self.path, parse_qs(self.rfile.read(size).decode())))
            body = json.dumps(
                {
                    "token_type": "Bearer",
                    "scope": gmail.SCOPE,
                    "access_token": "synthetic-access-value",
                    "refresh_token": "synthetic-refresh-value",
                    "expires_in": 3600,
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    class LocalOnly(httpx.BaseTransport):
        def __init__(self):
            self.transport = httpx.HTTPTransport()

        def handle_request(self, request):
            assert request.url.host == "oauth2.googleapis.com"
            target = f"http://127.0.0.1:{server.server_port}" + request.url.path
            return self.transport.handle_request(
                httpx.Request(
                    request.method, target, headers=request.headers, content=request.read()
                )
            )

        def close(self):
            self.transport.close()

    client = gmail.GmailProtocol(test_transport=LocalOnly())
    try:
        response = client.exchange(
            code="synthetic-code",
            verifier="synthetic-verifier",
            client_id="synthetic-client",
            client_secret="synthetic-secret",
            redirect_uri="https://api.subtrack.test/callback",
        )
        assert response["expires_in"] == 3600
        assert received[0][0] == "/token"
        assert received[0][1]["code_verifier"] == ["synthetic-verifier"]
    finally:
        client.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_export_includes_evidence_and_consent_without_credentials(enabled, api_client, pg_engine):
    headers, user = account(api_client)
    connect(api_client, headers)
    sync(api_client, headers, pg_engine)
    with Session(pg_engine) as db:
        gmail.begin(db, uuid.UUID(user["id"]), "synthetic", "https://api.subtrack.test/callback")
    response = api_client.get("/api/v1/me/export", headers=headers)
    assert response.status_code == 200
    value = response.json()
    assert len(value["receipt_evidence"]) == 12
    assert len(value["mailbox_connections"]) == 1
    assert "mailbox_oauth_states" not in value
    for forbidden in ("token_cipher", "verifier_cipher", "claim_token", "synthetic-access"):
        assert forbidden not in response.text


def test_mailbox_evidence_cannot_match_legacy_receipt_transactions(
    enabled, api_client, pg_engine, monkeypatch
):
    from test_api import wait
    from test_email_receipts import confirm, preview

    monkeypatch.setenv("RECEIPT_IMPORT_ENABLED", "true")
    get_settings.cache_clear()
    headers, _ = account(api_client)
    previewed = preview(api_client, headers).json()
    imported = confirm(api_client, headers, previewed)
    assert imported.status_code == 202
    assert wait(api_client, headers, imported.json()["id"])[0]["inserted_count"] == 1
    connect(api_client, headers)
    sync(api_client, headers, pg_engine)
    rows = api_client.get("/api/v1/mailbox/evidence?limit=100", headers=headers).json()["items"]
    target = next(r for r in rows if r["merchant"] == "netflix" and r["charged_on"] == "2026-07-01")
    assert target["candidates"] == []


def test_stale_consent_stops_sync_until_explicit_reconsent(enabled, api_client, pg_engine):
    headers, user = account(api_client)
    connect(api_client, headers)
    old = api_client.post("/api/v1/mailbox/sync", headers=headers).json()
    with Session(pg_engine) as db, db.begin():
        lab.connection(db, uuid.UUID(user["id"]), lock=True).consent_version = "obsolete-purpose"
    assert not api_client.get("/api/v1/mailbox/config", headers=headers).json()["connected"]
    assert api_client.post("/api/v1/mailbox/sync", headers=headers).status_code == 409
    identity = lab.claim(pg_engine)
    assert not lab.step(pg_engine, identity)
    assert (
        api_client.get("/api/v1/mailbox/sync/" + old["id"], headers=headers).json()["status"]
        == "cancelled"
    )
    connect(api_client, headers)
    assert sync(api_client, headers, pg_engine)["accepted"] == 12
