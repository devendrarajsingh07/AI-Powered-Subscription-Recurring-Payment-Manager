"""Bounded synthetic-only operational drills. Never uses the normal .env or hosted services.

Private settings, fixture account tokens, database archives and detailed reports live in
ignored var/drills. Stdout contains step names, counts and timing only, not financial records.
"""

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
import platform
import re
import secrets
import subprocess
import sys
import tarfile
import time
import uuid
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "var/drills"
COMPOSE = [
    "docker",
    "compose",
    "--env-file",
    str(PRIVATE / "compose.env"),
    "-p",
    "subtrack-drills",
    "-f",
    str(ROOT / "docker-compose.drills.yml"),
]
BASES = ["http://api1:8000/api/v1", "http://api2:8000/api/v1"]
MAPPING = {k: k for k in ("date", "description", "amount", "type")}
DAY = "2026-10-18"
K6_IMAGE = (
    "grafana/k6@sha256:3e4186aea62e11a45560bfc51e19eeafe82fc07ce069c78aff44b7ff893d9a5e"
)
ZAP_IMAGE = "ghcr.io/zaproxy/zaproxy@sha256:030d3df57735dacbb83464854758e674dd9ad01d79d12a129a8e58b1fd384238"


class HttpFailure(AssertionError):
    def __init__(self, status, method, route, retry_after=None):
        super().__init__(
            f"Unexpected status {status} for {method} {route.split('?')[0]}"
        )
        self.status, self.retry_after = status, retry_after


def run(args, *, capture=True, data=None, check=True, timeout=300):
    result = subprocess.run(
        [str(x) for x in args],
        cwd=ROOT,
        input=data,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        timeout=timeout,
    )
    if check and result.returncode:
        # Tool output may contain private settings; do not include it in the exception.
        raise RuntimeError(
            "Local command failed: " + str(args[0]) + "; exit=" + str(result.returncode)
        )
    return result


def compose(*args, **kwargs):
    return run(COMPOSE + list(args), **kwargs)


def finite_container(name, args, *, timeout):
    if not re.fullmatch(r"subtrack-drills-(k6|zap-web|zap-api)", name):
        raise ValueError("Only named disposable scanner/load containers are allowed")
    try:
        return run(
            ["docker", "run", "--rm", "--name", name, "--label", "subtrack.drill=true"]
            + args,
            check=False,
            timeout=timeout,
        )
    finally:
        # A killed docker CLI can leave its container running. Bound the container itself too.
        existing = (
            run(
                ["docker", "ps", "-aq", "--filter", "name=^/" + name + "$"], check=False
            )
            .stdout.decode()
            .strip()
        )
        if existing:
            value = json.loads(run(["docker", "inspect", existing]).stdout)[0]
            if value["Config"]["Labels"].get("subtrack.drill") != "true":
                raise RuntimeError(
                    "Refusing to remove a container not owned by the drill"
                )
            run(["docker", "rm", "-f", existing])


def save(name, value):
    PRIVATE.mkdir(parents=True, exist_ok=True)
    (PRIVATE / name).write_text(json.dumps(value, indent=2), encoding="utf-8")


def load(name):
    return json.loads((PRIVATE / name).read_text(encoding="utf-8"))


def sql(query, service="db", database="drill"):
    if service not in {"db", "restore-db"} or database not in {"drill", "restored"}:
        raise ValueError("Only isolated drill databases are allowed")
    return (
        compose(
            "exec",
            "-T",
            service,
            "psql",
            "-X",
            "-qAt",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "drill",
            "-d",
            database,
            "-c",
            query,
        )
        .stdout.decode()
        .strip()
    )


def ident(value):
    return str(uuid.UUID(str(value)))


def request(
    base,
    route,
    *,
    token=None,
    method="GET",
    payload=None,
    fields=None,
    file=None,
    expected=(200,),
    timeout=45,
):
    if base not in BASES + [
        "http://restore-api:8000/api/v1",
        "http://rollback-api:8000/api/v1",
        "http://web:8080/api/v1",
        "http://web:8080",
    ]:
        raise ValueError("Drills may only contact explicit local API ports")
    headers = {}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    if fields is not None or file is not None:
        boundary = "subtrackdrill" + secrets.token_hex(12)
        chunks = []
        for key, value in (fields or {}).items():
            chunks.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
            )
        if file is not None:
            filename, content = file
            chunks += [
                f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode(),
                content,
                b"\r\n",
            ]
        chunks.append(f"--{boundary}--\r\n".encode())
        data = b"".join(chunks)
        headers["Content-Type"] = "multipart/form-data; boundary=" + boundary
    payload = dict(
        base=base,
        route=route,
        method=method,
        headers=headers,
        timeout=timeout,
        data=base64.b64encode(data).decode() if data is not None else None,
    )
    raw = compose(
        "exec",
        "-T",
        "probe",
        "python",
        "/drills/drill_http.py",
        data=json.dumps(payload).encode(),
        timeout=timeout + 15,
    ).stdout
    result = json.loads(raw)
    status, body = result["status"], result["body"]
    if status not in expected:
        raise HttpFailure(status, method, route, result.get("retry_after"))
    if result["type"] == "text/event-stream":
        return status, body
    return status, json.loads(body) if body else {}


def account(label, api=0):
    password = "SyntheticOnly!" + secrets.token_hex(12)
    email = f"ops-{label}-{uuid.uuid4().hex[:10]}@example.org"
    request(
        BASES[api],
        "/auth/register",
        method="POST",
        payload={"email": email, "password": password},
        expected=(201,),
    )
    auth = login(email, password, api=api)
    _, me = request(BASES[1 - api], "/auth/me", token=auth["access_token"])
    accounts = load("accounts.json") if (PRIVATE / "accounts.json").exists() else {}
    value = dict(
        email=email, password=password, token=auth["access_token"], id=me["id"]
    )
    accounts[label] = value
    save("accounts.json", accounts)
    return value


def login(email, password, *, api=0):
    for attempt in range(2):
        try:
            return request(
                BASES[api],
                "/auth/login",
                method="POST",
                payload={"email": email, "password": password},
            )[1]
        except HttpFailure as error:
            delay = int(error.retry_after or 0)
            if attempt or error.status != 429 or not 1 <= delay <= 60:
                raise
            time.sleep(delay + 0.1)
    raise AssertionError("Setup login did not finish")


def renew(label):
    """Use normal login when a long drill outlives its short access token."""
    accounts = load("accounts.json")
    who = accounts[label]
    auth = login(who["email"], who["password"])
    who["token"] = auth["access_token"]
    accounts[label] = who
    save("accounts.json", accounts)
    return who


def poll(base, route, token, target, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        _, value = request(base, route, token=token)
        if value["status"] in target:
            return value
        if value["status"] in {"failed", "dead_letter", "cancelled"}:
            raise AssertionError("Work ended unexpectedly: " + value["status"])
        time.sleep(0.15)
    raise AssertionError("Real work did not reach expected state before deadline")


def upload(who, *, api=0, data=None):
    data = data or (ROOT / "backend/data/sample_transactions.csv").read_bytes()
    return request(
        BASES[api],
        "/uploads",
        token=who["token"],
        method="POST",
        fields={"mapping": json.dumps(MAPPING)},
        file=("synthetic.csv", data),
        expected=(202,),
    )[1]


def preview(who, filename="scanned.pdf", api=0):
    content = (ROOT / "backend/data/extraction" / filename).read_bytes()
    return request(
        BASES[api],
        "/uploads/preview",
        token=who["token"],
        method="POST",
        file=(filename, content),
        expected=(202,),
    )[1]


def step(name, action, report):
    start = time.monotonic()
    value = action()
    report.append(
        dict(step=name, seconds=round(time.monotonic() - start, 3), result=value)
    )
    save("coordination.json", report)
    print("PASS " + name, flush=True)


def prepare():
    PRIVATE.mkdir(parents=True, exist_ok=True)
    if (PRIVATE / "runtime.env").exists():
        raise RuntimeError(
            "Existing drill configuration preserved; reuse up, or explicitly clean it"
        )
    revision = run(["git", "rev-parse", "HEAD"]).stdout.decode().strip()
    password = secrets.token_hex(24)
    values = {
        "DRILL_DB_PASSWORD": password,
        "DRILL_DATABASE_URL": f"postgresql+psycopg://drill:{password}@db/drill",
        "DRILL_RESTORE_URL": f"postgresql+psycopg://drill:{password}@restore-db/restored",
        "DRILL_REVISION": revision,
    }
    (PRIVATE / "compose.env").write_text(
        "\n".join(f"{k}={v}" for k, v in values.items()) + "\n", encoding="utf-8"
    )
    settings = {
        "ENVIRONMENT": "development",
        "JWT_SECRET": secrets.token_hex(32),
        "WEB_ORIGIN": "http://localhost:18080",
        "API_ORIGIN": "http://localhost:18000",
        "AUTH_SESSION_MODE": "strict",
        "PUBLIC_DEMO_ONLY": "false",
        "DEMO_ENABLED": "true",
        "REGISTRATION_MODE": "open",
        "REQUIRE_EMAIL_VERIFICATION": "false",
        "BCRYPT_ROUNDS": "12",
        "AUTH_REGISTER_LIMIT": "100",
        "AUTH_LOGIN_LIMIT": "10",
        "AUTH_WINDOW_SECONDS": "60",
        "JOB_MODE": "postgres",
        "UPLOAD_QUEUE_LIMIT": "8",
        "JOB_USER_LIMIT": "3",
        "JOB_LEASE_SECONDS": "6",
        "JOB_RETRY_SECONDS": "1",
        "JOB_MAX_ATTEMPTS": "3",
        "CHAT_TIMEOUT_SECONDS": "10",
        "CHAT_MINUTE_LIMIT": "2",
        "CHAT_DAILY_LIMIT": "100",
        "STATEMENT_DAILY_LIMIT": "2",
        "STATEMENT_CONCURRENT_LIMIT": "2",
        "APP_TEST_AS_OF": DAY,
        "APP_TIMEZONE": "Asia/Kolkata",
        "LLM_PROVIDER": "fake",
        "LLM_API_KEY": "",
        "SCHEDULER_ENABLED": "false",
        "NOTIFIER_PROVIDER": "console",
        "OUTBOX_DIR": "/var/subtrack/outbox",
        "EXTRACTOR_SOCKET": "/var/subtrack/extractor/rpc.sock",
        "RECEIPT_IMPORT_ENABLED": "false",
        "MAILBOX_LAB_ENABLED": "false",
        "MAILBOX_LIVE_ENABLED": "false",
        "OPS_METRICS_TOKEN": secrets.token_hex(24),
    }
    (PRIVATE / "runtime.env").write_text(
        "\n".join(f"{k}={v}" for k, v in settings.items()) + "\n", encoding="utf-8"
    )
    machine = json.loads(run(["docker", "info", "--format", "{{json .}} "]).stdout)
    save(
        "manifest.json",
        dict(
            source_revision=revision,
            environment="local synthetic only",
            platform=platform.platform(),
            docker_version=machine["ServerVersion"],
            docker_cpus=machine["NCPU"],
            docker_memory_bytes=machine["MemTotal"],
            settings={
                k: v
                for k, v in settings.items()
                if k not in {"JWT_SECRET", "OPS_METRICS_TOKEN"}
            },
        ),
    )
    print("PASS prepared isolated development settings; no normal .env was read")


def up():
    # Reuse credentials/volumes, but never label freshly built source with an old revision.
    path = PRIVATE / "compose.env"
    lines = path.read_text(encoding="utf-8").splitlines()
    revision = run(["git", "rev-parse", "HEAD"]).stdout.decode().strip()
    if not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise RuntimeError("Cannot identify local source revision")
    if sum(line.startswith("DRILL_REVISION=") for line in lines) != 1:
        raise RuntimeError("Private configuration needs exactly one source revision")
    path.write_text(
        "\n".join(
            "DRILL_REVISION=" + revision if line.startswith("DRILL_REVISION=") else line
            for line in lines
        )
        + "\n",
        encoding="utf-8",
    )
    compose("up", "--build", "-d", "--wait", capture=False, timeout=900)


def lock_rows(query):
    args = COMPOSE + [
        "exec",
        "-T",
        "-e",
        "PGAPPNAME=subtrack-drill-lock",
        "db",
        "psql",
        "-X",
        "-qAt",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        "drill",
        "-d",
        "drill",
    ]
    process = subprocess.Popen(
        args,
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Separate psql commands flush the readiness marker while the transaction still holds
    # its lock. A single libpq -c batch buffers that marker until pg_sleep has finished.
    process.stdin.write(
        (
            "BEGIN;\n"
            + query
            + ";\nSELECT 'LOCKED:' || pg_backend_pid();\nSELECT pg_sleep(45);\nROLLBACK;\n"
        ).encode()
    )
    process.stdin.flush()
    while True:
        line = process.stdout.readline().decode().strip()
        if line.startswith("LOCKED:"):
            return process
        if process.poll() is not None:
            raise RuntimeError("Could not establish the isolated fault-injection lock")


def release_lock(process):
    sql(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='drill' AND application_name='subtrack-drill-lock'"
    )
    process.communicate(timeout=10)


def coordination(only=None):
    allowed = {
        "worker-kill-reclaim",
        "two-api-dedupe-isolation",
        "shared-preview-quota",
        "shared-chat-cap",
        "api-kill-chat-recovery",
        "shared-queue-and-deletion",
        "delete-running-extraction",
        "shared-auth-window",
    }
    if only and not set(only.split(",")).issubset(allowed):
        raise ValueError("Unknown coordination step; no drill was run")
    report = (
        load("coordination.json")
        if only and (PRIVATE / "coordination.json").exists()
        else []
    )
    if only:
        accounts = load("accounts.json")
        who, other = accounts["primary"], accounts["other"]
    else:
        who, other = account("primary"), account("other", api=1)
    truth = json.loads(
        (ROOT / "backend/data/ground_truth.json").read_text(encoding="utf-8")
    )
    expected_products = sorted((r["merchant"], r["cadence"]) for r in truth["patterns"])
    expected_rows = (
        len(
            (ROOT / "backend/data/sample_transactions.csv")
            .read_text(encoding="utf-8")
            .splitlines()
        )
        - 1
    )

    def worker_crash():
        compose("stop", "worker")
        job = upload(who)
        owner_id = ident(who["id"])
        blocker = lock_rows(f"SELECT id FROM users WHERE id='{owner_id}' FOR UPDATE")
        try:
            compose("start", "worker")
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                count = sql(
                    f"SELECT count(*) FROM durable_jobs WHERE upload_id='{ident(job['id'])}' AND status='running'"
                )
                if count == "1":
                    break
                time.sleep(0.1)
            else:
                raise AssertionError("Worker never claimed real queued input")
            compose("kill", "-s", "SIGKILL", "worker")
        finally:
            release_lock(blocker)
        time.sleep(7)
        compose("start", "worker")
        result = poll(BASES[1], "/uploads/" + job["id"], who["token"], {"done"})
        assert result["inserted_count"] == expected_rows
        record = sql(
            f"SELECT attempt_count || ':' || (encrypted_input IS NULL)::text FROM durable_jobs WHERE upload_id='{ident(job['id'])}'"
        )
        assert record == "2:true", record
        return dict(attempts=2, inserted=expected_rows, encrypted_input_purged=True)

    def dedupe():
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = list(pool.map(lambda api: upload(who, api=api), [0, 1]))
        for item in jobs:
            result = poll(BASES[1], "/uploads/" + item["id"], who["token"], {"done"})
            assert (
                result["inserted_count"] == 0
                and result["duplicate_count"] == expected_rows
            )
        _, subs = request(BASES[0], "/subscriptions?limit=100", token=who["token"])
        assert (
            sorted((r["merchant"], r["cadence"]) for r in subs["items"])
            == expected_products
        )
        assert sql(
            f"SELECT count(*) FROM transactions WHERE user_id='{ident(who['id'])}'"
        ) == str(expected_rows)
        request(
            BASES[1], "/uploads/" + jobs[0]["id"], token=other["token"], expected=(404,)
        )
        return dict(
            concurrent_uploads=2,
            products=len(expected_products),
            transactions=expected_rows,
        )

    def preview_quota():
        for api in [0, 1]:
            value = preview(other, api=api)
            poll(
                BASES[1 - api],
                "/uploads/previews/" + value["id"],
                other["token"],
                {"ready"},
            )
            request(
                BASES[api],
                "/uploads/previews/" + value["id"],
                token=other["token"],
                method="DELETE",
            )
        content = (ROOT / "backend/data/extraction/scanned.pdf").read_bytes()
        _, error = request(
            BASES[0],
            "/uploads/preview",
            token=other["token"],
            method="POST",
            file=("scanned.pdf", content),
            expected=(429,),
        )
        assert error["error"]["code"] == "preview_quota"
        return dict(attempts=2, cross_instance_rejection=429)

    def chat_shared():
        for api in [0, 1]:
            _, result = request(
                BASES[api],
                "/chat",
                token=who["token"],
                method="POST",
                payload={"message": "monthly spend"},
            )
            assert "event: final" in result and '"verified": true' in result
        request(
            BASES[0],
            "/chat",
            token=who["token"],
            method="POST",
            payload={"message": "monthly spend"},
            expected=(429,),
        )
        return dict(successful_turns=2, shared_minute_rejection=429)

    def chat_crash():
        person = account("chat-crash")
        blocker = lock_rows("LOCK TABLE subscriptions IN ACCESS EXCLUSIVE MODE")
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                request,
                BASES[0],
                "/chat",
                token=person["token"],
                method="POST",
                payload={"message": "monthly spend"},
                timeout=30,
            )
            try:
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    if (
                        sql(
                            f"SELECT count(*) FROM chat_leases WHERE user_id='{ident(person['id'])}' AND expires_at>now()"
                        )
                        == "1"
                    ):
                        break
                    time.sleep(0.1)
                else:
                    raise AssertionError("Chat was not admitted before fault injection")
                compose("kill", "-s", "SIGKILL", "api1")
                _, error = request(
                    BASES[1],
                    "/chat",
                    token=person["token"],
                    method="POST",
                    payload={"message": "monthly spend"},
                    expected=(429,),
                )
                assert error["error"]["code"] == "chat_busy"
            finally:
                release_lock(blocker)
            try:
                _, interrupted = future.result()
                assert "event: final" not in interrupted
            except (OSError, ValueError):
                pass  # The killed API must not produce a final answer/history.
            except AssertionError as error:
                assert "Unexpected status 0" in str(error)
        assert (
            sql(
                f"SELECT count(*) FROM chat_messages WHERE user_id='{ident(person['id'])}'"
            )
            == "0"
        )
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if (
                sql(
                    f"SELECT count(*) FROM chat_leases WHERE user_id='{ident(person['id'])}' AND expires_at>now()"
                )
                == "0"
            ):
                break
            time.sleep(0.3)
        _, result = request(
            BASES[1],
            "/chat",
            token=person["token"],
            method="POST",
            payload={"message": "monthly spend"},
        )
        assert "event: final" in result and '"verified": true' in result
        assert (
            sql(
                f"SELECT count(*) FROM chat_messages WHERE user_id='{ident(person['id'])}'"
            )
            == "2"
        )
        compose("start", "api1")
        compose("up", "-d", "--wait", "api1", "api2", timeout=90)
        return dict(killed_api=1, stale_history_rows=0, recovered_on_api=2)

    def capacity_delete():
        compose("stop", "worker")
        people = [account("queue-" + str(i), api=i % 2) for i in range(3)]
        try:
            first_jobs = [upload(people[0], api=i % 2) for i in range(3)]
            request(
                BASES[1],
                "/uploads",
                token=people[0]["token"],
                method="POST",
                fields={"mapping": json.dumps(MAPPING)},
                file=(
                    "synthetic.csv",
                    b"date,description,amount,type\n2026-01-01,test,1.00,debit\n",
                ),
                expected=(429,),
            )
            for i in range(5):
                upload(people[1 + i // 3], api=i % 2)
            request(
                BASES[0],
                "/uploads",
                token=other["token"],
                method="POST",
                fields={"mapping": json.dumps(MAPPING)},
                file=(
                    "synthetic.csv",
                    b"date,description,amount,type\n2026-01-01,test,1.00,debit\n",
                ),
                expected=(429,),
            )
            assert (
                sql(
                    "SELECT count(*) FROM durable_jobs WHERE status IN ('queued','running','staging')"
                )
                == "8"
            )
            request(BASES[1], "/me/data", token=people[0]["token"], method="DELETE")
            assert (
                sql(
                    f"SELECT count(*) FROM durable_jobs WHERE user_id='{ident(people[0]['id'])}'"
                )
                == "0"
            )
            request(
                BASES[0],
                "/jobs/" + first_jobs[0]["id"],
                token=other["token"],
                expected=(404,),
            )
        finally:
            for person in people[1:]:
                request(BASES[0], "/me/data", token=person["token"], method="DELETE")
            compose("start", "worker")
        return dict(shared_capacity=8, user_capacity=3, queued_account_purged=True)

    def running_delete():
        victim = account("running-delete")
        compose("pause", "extractor")
        try:
            item = preview(victim)
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                active = sql(
                    "SELECT count(*) FROM durable_jobs j JOIN statement_previews p ON p.id=j.preview_id "
                    f"WHERE j.preview_id='{ident(item['id'])}' AND j.status='running' AND p.status='processing'"
                )
                if active == "1":
                    break
                time.sleep(0.1)
            else:
                raise AssertionError("Real extraction did not enter running state")
            request(BASES[1], "/me/data", token=victim["token"], method="DELETE")
        finally:
            compose("unpause", "extractor")
        time.sleep(1)
        for table in [
            "transactions",
            "subscriptions",
            "durable_jobs",
            "statement_previews",
        ]:
            assert (
                sql(
                    f"SELECT count(*) FROM {table} WHERE user_id='{ident(victim['id'])}'"
                )
                == "0"
            )
        clean = (
            compose(
                "exec",
                "-T",
                "extractor",
                "python",
                "-c",
                "from pathlib import Path; print(len(list(Path('/tmp').glob('subtrack-extract-*'))))",
            )
            .stdout.decode()
            .strip()
        )
        assert clean == "0"
        return dict(
            deleted_during_running_extraction=True,
            orphan_rows=0,
            extraction_temp_dirs=0,
        )

    def auth_limit():
        # Start this bounded counter test with an empty isolated coordination fixture.
        # Earlier real registrations/logins must not make its expected starting count ambiguous.
        sql("TRUNCATE rate_limit_buckets")
        nonce = uuid.uuid4().hex[:8]
        for i in range(10):
            request(
                BASES[i % 2],
                "/auth/login",
                method="POST",
                payload={
                    "email": f"missing-{nonce}-{i}@example.org",
                    "password": "NotARealPassword42!",
                },
                expected=(401,),
            )
        request(
            BASES[1],
            "/auth/login",
            method="POST",
            payload={
                "email": f"missing-{nonce}-last@example.org",
                "password": "NotARealPassword42!",
            },
            expected=(429,),
        )
        return dict(shared_login_attempts=10, next_attempt=429)

    try:
        for name, action in [
            ("worker-kill-reclaim", worker_crash),
            ("two-api-dedupe-isolation", dedupe),
            ("shared-preview-quota", preview_quota),
            ("shared-chat-cap", chat_shared),
            ("api-kill-chat-recovery", chat_crash),
            ("shared-queue-and-deletion", capacity_delete),
            ("delete-running-extraction", running_delete),
            ("shared-auth-window", auth_limit),
        ]:
            if not only or name in only.split(","):
                step(name, action, report)
    finally:
        compose("start", "api1", "worker", check=False)


def snapshot(service="db", database="drill"):
    tables = sql(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename",
        service,
        database,
    ).splitlines()
    result = {}
    for table in tables:
        if not re.fullmatch(r"[a-z_]+", table):
            raise RuntimeError("Unexpected drill table name")
        value = sql(
            "SELECT json_build_object('count',count(*),'digest',"
            "md5(coalesce(string_agg(row_to_json(t)::text,E'\\n' ORDER BY row_to_json(t)::text),''))) "
            f'FROM "{table}" t',
            service,
            database,
        )
        result[table] = json.loads(value)
    return result


def restore():
    who = renew("primary")
    renew("other")
    accounts = load("accounts.json")
    routes = [
        "/auth/me",
        "/subscriptions?limit=100",
        "/summary?period=month",
        "/summary?period=year",
        "/summary/trend?months=12",
        "/recommendations?limit=100",
        "/renewals/upcoming?days=30",
        "/budget",
        "/settings/alerts",
        "/jobs?limit=100",
    ]
    expected = {
        route: request(BASES[0], route, token=who["token"])[1] for route in routes
    }
    compose("--profile", "restore", "stop", "restore-worker", "restore-api")
    compose("stop", "worker", "api1", "api2")
    try:
        before = snapshot()
        start = time.monotonic()
        compose(
            "exec",
            "-T",
            "db",
            "pg_dump",
            "-U",
            "drill",
            "-d",
            "drill",
            "--format=custom",
            "--no-owner",
            "--no-privileges",
            "--file=/tmp/subtrack-drill.dump",
        )
        dump_seconds = round(time.monotonic() - start, 3)
        compose(
            "cp", "db:/tmp/subtrack-drill.dump", str(PRIVATE / "synthetic-backup.dump")
        )
        compose(
            "cp",
            str(PRIVATE / "synthetic-backup.dump"),
            "restore-db:/tmp/subtrack-drill.dump",
        )
        # This DB is explicitly disposable and separate from both source and normal stack.
        sql(
            "DROP SCHEMA public CASCADE; CREATE SCHEMA public", "restore-db", "restored"
        )
        start = time.monotonic()
        compose(
            "exec",
            "-T",
            "restore-db",
            "pg_restore",
            "-U",
            "drill",
            "-d",
            "restored",
            "--single-transaction",
            "--exit-on-error",
            "--no-owner",
            "--no-privileges",
            "/tmp/subtrack-drill.dump",
        )
        restore_seconds = round(time.monotonic() - start, 3)
        after = snapshot("restore-db", "restored")
        assert before == after, "Restored table count/digest differs"
        compose(
            "--profile",
            "restore",
            "up",
            "-d",
            "--wait",
            "restore-api",
            "restore-worker",
            timeout=120,
        )
        base = "http://restore-api:8000/api/v1"
        for route, original in expected.items():
            assert request(base, route, token=who["token"])[1] == original, (
                "Restored API response differs: " + route
            )
        request(
            base,
            "/subscriptions/" + expected["/subscriptions?limit=100"]["items"][0]["id"],
            token=accounts["other"]["token"],
            expected=(404,),
        )
        # A new real login proves restored password/session data work, without exporting tokens.
        request(
            base,
            "/auth/login",
            method="POST",
            payload={"email": who["email"], "password": who["password"]},
        )
        job = request(
            base,
            "/uploads",
            token=who["token"],
            method="POST",
            fields={"mapping": json.dumps(MAPPING)},
            file=(
                "synthetic.csv",
                (ROOT / "backend/data/sample_transactions.csv").read_bytes(),
            ),
            expected=(202,),
        )[1]
        result = poll(base, "/uploads/" + job["id"], who["token"], {"done"})
        assert result["inserted_count"] == 0 and result["duplicate_count"] == 399
        request(base, "/me/data", token=accounts["other"]["token"], method="DELETE")
        assert (
            sql(
                f"SELECT count(*) FROM users WHERE id='{ident(accounts['other']['id'])}'"
            )
            == "1"
        )
        compose("exec", "-T", "restore-api", "alembic", "check")
        count = before["transactions"]["count"]
        evidence = dict(
            dump_seconds=dump_seconds,
            restore_seconds=restore_seconds,
            archive_bytes=(PRIVATE / "synthetic-backup.dump").stat().st_size,
            tables_equal=len(before),
            rows_equal=sum(v["count"] for v in before.values()),
            transactions=count,
            exact_api_comparisons=len(routes),
            isolation_404=True,
            restored_login=True,
            restored_dedupe=True,
            schema_model_drift=False,
            restored_deletion_kept_source_user=True,
        )
        save("restore.json", evidence)
        save("restore-counts.json", before)
        print(
            "PASS synthetic restore: counts/digests, API comparisons, login, isolation, real dedupe and Alembic drift",
            flush=True,
        )
    finally:
        compose("start", "api1", "api2", "worker", check=False)


def isolation():
    details = {}
    for service in ["api1", "api2", "worker", "extractor", "web"]:
        container = compose("ps", "-q", service).stdout.decode().strip()
        value = json.loads(run(["docker", "inspect", container]).stdout)[0]
        config, host = value["Config"], value["HostConfig"]
        assert config["User"] and config["User"] not in {"root", "0"}
        assert host["ReadonlyRootfs"] and "ALL" in host["CapDrop"]
        assert "no-new-privileges:true" in host["SecurityOpt"]
        details[service] = dict(
            user=config["User"], read_only=True, capabilities_dropped=True
        )
        if service == "extractor":
            names = {entry.split("=", 1)[0] for entry in config["Env"]}
            assert not names & {
                "JWT_SECRET",
                "DATABASE_URL",
                "LLM_API_KEY",
                "SMTP_PASSWORD",
                "POSTGRES_PASSWORD",
            }
            assert host["NetworkMode"] == "none" and host["Memory"] == 768 * 1024 * 1024
            details[service].update(
                no_credentials=True,
                network="none",
                memory_bytes=host["Memory"],
                cpus=host["NanoCpus"] / 1_000_000_000,
                pids=host["PidsLimit"],
            )
    network = json.loads(
        run(["docker", "network", "inspect", "subtrack-drills_drill"]).stdout
    )[0]
    assert network["Internal"]
    details["network_internal"] = True
    save("isolation.json", details)
    print("PASS actual container isolation and non-root controls")


def load_test():
    config = PRIVATE / "runtime.env"
    original = config.read_text(encoding="utf-8")
    overrides = {
        "AUTH_LOGIN_LIMIT": "1000",
        "AUTH_REGISTER_LIMIT": "1000",
        "CHAT_MINUTE_LIMIT": "60",
        "CHAT_DAILY_LIMIT": "500",
        "STATEMENT_DAILY_LIMIT": "100",
    }
    config.write_text(
        "\n".join(
            f"{line.split('=', 1)[0]}={overrides.get(line.split('=', 1)[0], line.split('=', 1)[1])}"
            for line in original.splitlines()
        )
        + "\n",
        encoding="utf-8",
    )
    try:
        compose(
            "up",
            "-d",
            "--no-deps",
            "--force-recreate",
            "--wait",
            "api1",
            "api2",
            "worker",
            timeout=120,
        )
        users = [account("load-" + str(i), api=i % 2) for i in range(3)]
        truth = json.loads(
            (ROOT / "backend/data/ground_truth.json").read_text(encoding="utf-8")
        )["patterns"]
        factors = dict(
            weekly=Decimal(52),
            monthly=Decimal(12),
            quarterly=Decimal(4),
            yearly=Decimal(1),
        )
        year = sum(
            (
                Decimal(r["new_amount"] if r["price_increase"] else r["avg_amount"])
                * factors[r["cadence"]]
                for r in truth
            ),
            Decimal(0),
        )
        expected = format(
            (year / 12).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ".2f"
        )
        save("load-input.json", dict(users=users, expected_monthly=expected))
        report_dir = PRIVATE / "load"
        report_dir.mkdir(exist_ok=True)
        image = json.loads(run(["docker", "image", "inspect", K6_IMAGE]).stdout)[0]
        digest = image["RepoDigests"][0]
        result = finite_container(
            "subtrack-drills-k6",
            [
                "--network",
                "subtrack-drills_drill",
                "--read-only",
                "--tmpfs",
                "/tmp:size=32m",
                "--memory",
                "256m",
                "--cpus",
                "1",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges:true",
                "--mount",
                f"type=bind,source={ROOT / 'scripts'},target=/scripts,readonly",
                "--mount",
                f"type=bind,source={ROOT / 'backend/data'},target=/fixtures,readonly",
                "--mount",
                f"type=bind,source={PRIVATE / 'load-input.json'},target=/private/load-input.json,readonly",
                "--mount",
                f"type=bind,source={report_dir},target=/reports",
                digest,
                "run",
                "/scripts/drill_load.js",
            ],
            timeout=240,
        )
        (report_dir / "console.log").write_bytes(result.stdout + result.stderr)
        save(
            "load-run.json",
            dict(
                exit_code=result.returncode,
                image=digest,
                vus=3,
                iterations_per_vu=3,
                max_duration_seconds=180,
                quota_overrides=overrides,
                api_replicas=2,
                workers=1,
            ),
        )
        if result.returncode:
            raise AssertionError(
                "k6 workload/threshold failure; inspect ignored load report"
            )
        print(
            "PASS bounded local k6 workload and exact financial/verified-chat assertions",
            flush=True,
        )
    finally:
        config.write_text(original, encoding="utf-8")
        compose(
            "up",
            "-d",
            "--no-deps",
            "--force-recreate",
            "--wait",
            "api1",
            "api2",
            "worker",
            timeout=120,
        )


def sanitize_zap(report):
    """Publish finding metadata only, never instance URLs, headers, evidence or bodies."""
    return [
        dict(
            id=item["pluginid"],
            name=item["name"],
            risk=int(item["riskcode"]),
            confidence=int(item["confidence"]),
            instances=len(item.get("instances", [])),
        )
        for site in report.get("site", [])
        for item in site.get("alerts", [])
    ]


def scan(only=None):
    if only and only not in {"web", "api"}:
        raise ValueError("Scan target must be web or api")
    image = json.loads(run(["docker", "image", "inspect", ZAP_IMAGE]).stdout)[0]
    digest = image["RepoDigests"][0]
    summaries = (
        [r for r in load("zap-summary.json") if r["target"] != only]
        if only and (PRIVATE / "zap-summary.json").exists()
        else []
    )
    for label, target in [
        ("web", "http://web:8080"),
        ("api", "http://api1:8000/api/v1/openapi.json"),
    ]:
        if only and only != label:
            continue
        output = PRIVATE / ("zap-" + label)
        output.mkdir(exist_ok=True)
        result = finite_container(
            "subtrack-drills-zap-" + label,
            [
                "--network",
                "subtrack-drills_drill",
                "--memory",
                "1g",
                "--cpus",
                "1",
                "--shm-size",
                "256m",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges:true",
                "-e",
                "JAVA_OPTS=-Xmx512m",
                "--mount",
                f"type=bind,source={output},target=/zap/wrk",
                digest,
                "zap-baseline.py",
                "-t",
                target,
                "-m",
                "1",
                "-T",
                "5",
                "-J",
                "report.json",
                "-r",
                "report.html",
                "-w",
                "report.md",
                "-z",
                "-config autoupdate.checkOnStart=false -config autoupdate.downloadNewRelease=false -config autoupdate.installAddonUpdates=false",
            ],
            timeout=390,
        )
        (output / "console.log").write_bytes(result.stdout + result.stderr)
        if result.returncode not in {0, 1, 2} or not (output / "report.json").exists():
            raise AssertionError(
                "ZAP did not produce a completed local baseline report"
            )
        report = json.loads((output / "report.json").read_text(encoding="utf-8"))
        alerts = sanitize_zap(report)
        summaries.append(
            dict(
                target=label,
                exit_code=result.returncode,
                alerts=alerts,
                image=digest,
                scope="unauthenticated passive baseline; not a pentest",
            )
        )
        save("zap-summary.json", summaries)
        print(
            f"COMPLETE ZAP {label}: {len(alerts)} finding types; exit={result.returncode}",
            flush=True,
        )


def source_image(ref, *, web=False):
    sha = run(["git", "rev-parse", ref + "^{commit}"]).stdout.decode().strip()
    assert re.fullmatch(r"[a-f0-9]{40}", sha)
    run(["git", "merge-base", "--is-ancestor", sha, "HEAD"])
    directory = PRIVATE / ("source-" + sha)
    directory.mkdir(exist_ok=True)
    archive = run(["git", "archive", sha, "backend", "frontend"]).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
        for member in stream.getmembers():
            target = (directory / member.name).resolve()
            if (
                not target.is_relative_to(directory.resolve())
                or member.issym()
                or member.islnk()
            ):
                raise RuntimeError("Unsafe archive member; source preparation stopped")
        stream.extractall(directory, filter="data")
    old_lock = (
        (directory / "backend/requirements.lock").read_bytes().replace(b"\r\n", b"\n")
    )
    current_lock = (
        (ROOT / "backend/requirements.lock").read_bytes().replace(b"\r\n", b"\n")
    )
    assert hashlib.sha256(old_lock).digest() == hashlib.sha256(current_lock).digest(), (
        "Rollback dependencies differ; separate dependency build required"
    )
    name = "subtrack-drill-" + ("web" if web else "api") + ":source-" + sha[:12]
    if web:
        args = [
            "docker",
            "build",
            "--build-context",
            "contract=" + str(directory / "backend/openapi"),
            "--build-arg",
            "SOURCE_REVISION=" + sha,
            "-f",
            ROOT / "ops/web.Dockerfile",
            "-t",
            name,
            directory / "frontend",
        ]
    else:
        dockerfile = directory / "Dockerfile.drill"
        # Only the disposable image's /app is replaced, never a host directory. Dependencies
        # are reused only after exact lock comparison; all source comes from the Git archive.
        dockerfile.write_text(
            "FROM subtrack-drill-api:current\nUSER root\nRUN rm -rf /app\nWORKDIR /app\nCOPY --chown=appuser:appuser backend/ /app/\nUSER appuser\n",
            encoding="utf-8",
        )
        args = ["docker", "build", "-f", dockerfile, "-t", name, directory]
    result = run(args, check=False, timeout=600)
    (
        PRIVATE / ("build-" + sha[:12] + ("-web" if web else "-api") + ".log")
    ).write_bytes(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError("Archived-source drill image build failed")
    return sha, name


def remove_rollback_container():
    ids = (
        run(["docker", "ps", "-aq", "--filter", "name=^/subtrack-drills-rollback$"])
        .stdout.decode()
        .strip()
    )
    if ids:
        value = json.loads(run(["docker", "inspect", ids]).stdout)[0]
        assert value["Config"]["Labels"].get("subtrack.drill") == "true"
        run(["docker", "rm", "-f", ids])


def start_rollback(sha, image):
    remove_rollback_container()
    values = dict(
        line.split("=", 1)
        for line in (PRIVATE / "compose.env").read_text(encoding="utf-8").splitlines()
    )
    runtime = (PRIVATE / "runtime.env").read_text(encoding="utf-8")
    config = PRIVATE / "rollback.env"
    config.write_text(
        runtime
        + "\nDATABASE_URL="
        + values["DRILL_DATABASE_URL"]
        + "\nRENDER_GIT_COMMIT="
        + sha
        + "\n",
        encoding="utf-8",
    )
    run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            "subtrack-drills-rollback",
            "--label",
            "subtrack.drill=true",
            "--network",
            "subtrack-drills_drill",
            "--network-alias",
            "rollback-api",
            "--read-only",
            "--tmpfs",
            "/tmp:size=64m,mode=1777",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--env-file",
            config,
            "--mount",
            "type=volume,source=subtrack-drills_drill_socket,target=/var/subtrack/extractor,readonly",
            image,
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
            "--no-access-log",
        ]
    )
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            _, health = request("http://rollback-api:8000/api/v1", "/health", timeout=2)
            if health["revision"] == sha:
                return
        except (AssertionError, RuntimeError):
            pass
        time.sleep(0.3)
    raise AssertionError("Archived API did not start")


def rollback():
    # Actual master ancestors, not fabricated version strings. Both sources are archived and
    # built; source hashes/limitations are written to the evidence report.
    previous, previous_api = source_image("92b9ae6")
    _, previous_web = source_image("92b9ae6", web=True)
    incompatible, old_api = source_image("7c56cb1")
    original_config = (PRIVATE / "compose.env").read_text(encoding="utf-8")
    current = load("manifest.json")["source_revision"]
    who = renew("primary")
    compose("stop", "worker")
    before = snapshot()
    _, summary = request(BASES[0], "/summary", token=who["token"])
    start = time.monotonic()
    try:
        start_rollback(incompatible, old_api)
        status, _ = request(
            "http://rollback-api:8000/api/v1", "/health/ready", expected=(503,)
        )
        assert status == 503  # Its Alembic head16 cannot certify a head17 database.
        start_rollback(previous, previous_api)
        request("http://rollback-api:8000/api/v1", "/health/ready")
        config = (ROOT / "ops/drill-nginx.conf").read_text(encoding="utf-8")
        config = config.replace(
            "server api1:8000 resolve;\n    server api2:8000 resolve;",
            "server rollback-api:8000 resolve;",
        )
        target = PRIVATE / "rollback-nginx.conf"
        target.write_text(config, encoding="utf-8")
        (PRIVATE / "compose.env").write_text(
            original_config
            + "DRILL_NGINX_CONFIG="
            + target.as_posix()
            + "\nDRILL_WEB_IMAGE="
            + previous_web
            + "\n",
            encoding="utf-8",
        )
        compose(
            "up",
            "-d",
            "--no-deps",
            "--no-build",
            "--pull",
            "never",
            "--force-recreate",
            "--wait",
            "web",
            timeout=90,
        )
        _, health = request("http://web:8080/api/v1", "/health/ready")
        _, version = request("http://web:8080", "/version.json")
        assert health["revision"] == version["revision"] == previous
        assert (
            request("http://web:8080/api/v1", "/summary", token=who["token"])[1]
            == summary
        )
        assert snapshot() == before, "Rollback changed the database"
        evidence = dict(
            previous=previous,
            current=current,
            rejected_source=incompatible,
            incompatible_readiness=503,
            frontend_and_api_rolled_back=True,
            unchanged_database=True,
            unchanged_summary=True,
            seconds_to_verify=round(time.monotonic() - start, 3),
            scope="local same-schema source rollback; previous/current business code is unchanged; no hosted rollback or database downgrade",
        )
    finally:
        (PRIVATE / "compose.env").write_text(original_config, encoding="utf-8")
        compose(
            "up",
            "-d",
            "--no-deps",
            "--no-build",
            "--pull",
            "never",
            "--force-recreate",
            "--wait",
            "web",
            timeout=90,
        )
        remove_rollback_container()
        compose("start", "worker")
    assert request("http://web:8080/api/v1", "/health/ready")[1]["revision"] == current
    assert request("http://web:8080", "/version.json")[1]["revision"] == current
    evidence["current_repromoted"] = True
    save("rollback.json", evidence)
    print(
        "PASS local source rollback/re-promotion and incompatible-head refusal; no DB downgrade",
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=[
            "prepare",
            "tools",
            "up",
            "coordination",
            "restore",
            "isolation",
            "load",
            "scan",
            "rollback",
            "down",
        ],
    )
    parser.add_argument(
        "--only",
        help="Resume selected coordination steps; does not count omitted steps as passed",
    )
    args = parser.parse_args()
    if args.action == "prepare":
        prepare()
    elif args.action == "tools":
        for image in [K6_IMAGE, ZAP_IMAGE]:
            run(["docker", "pull", image], capture=False, timeout=600)
    elif args.action == "up":
        up()
    elif args.action == "coordination":
        coordination(args.only)
    elif args.action == "restore":
        restore()
    elif args.action == "isolation":
        isolation()
    elif args.action == "load":
        load_test()
    elif args.action == "scan":
        scan(args.only)
    elif args.action == "rollback":
        rollback()
    else:
        # Intentionally keep volumes and private evidence; no recursive deletion or data purge.
        compose("--profile", "restore", "down", capture=False)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("FAIL local drill: " + str(error), file=sys.stderr)
        raise SystemExit(1) from None
