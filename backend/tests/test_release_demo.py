"""Release script against local stand-ins for Render, the API, Vercel and the web host.

The script lives at the repository root (scripts/), outside the backend container, so this test
skips when that directory is not mounted. Only synthetic values; no network beyond 127.0.0.1.
"""

import json
import os
import subprocess
import sys
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs, urlparse

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "release_demo.py"
SHA = "a" * 40
OLD = "b" * 40
pytestmark = pytest.mark.skipif(not SCRIPT.exists(), reason="repository scripts not mounted")


@contextmanager
def hosts(*, api_switches_after=2, vercel_state="READY", web_initial=OLD, hook_status=200):
    state = dict(hook_refs=[], promoted=[], api_polls=0, web=web_initial, auth=[])

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, code, body):
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            url = urlparse(self.path)
            if url.path == "/deploy/srv-test":
                state["hook_refs"].append(parse_qs(url.query).get("ref", [None])[0])
                return self.reply(hook_status, {"deploy": {"id": "dep-test"}})
            if url.path.startswith("/v10/projects/prj_test/promote/"):
                state["auth"].append(self.headers.get("Authorization"))
                state["promoted"].append(url.path.rsplit("/", 1)[1])
                state["web"] = SHA
                return self.reply(201, {})
            self.reply(404, {})

        def do_GET(self):
            url = urlparse(self.path)
            if url.path == "/api/v1/health":
                state["api_polls"] += 1
                new = state["hook_refs"] and state["api_polls"] > api_switches_after
                return self.reply(200, {"status": "ok", "revision": SHA if new else OLD})
            if url.path == "/api/v1/health/ready":
                return self.reply(200, {"status": "ready"})
            if url.path == "/v7/deployments":
                state["auth"].append(self.headers.get("Authorization"))
                assert parse_qs(url.query)["sha"] == [SHA]
                deployment = {"uid": "dpl_test123", "readyState": vercel_state}
                return self.reply(200, {"deployments": [deployment]})
            if url.path == "/version.json":
                return self.reply(200, {"revision": state["web"]})
            self.reply(404, {})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", state
    finally:
        server.shutdown()
        server.server_close()


def run(base, timeout=6, **extra):
    env = dict(
        os.environ,
        SHA=SHA,
        API_URL=base + "/api/v1",
        WEB_URL=base,
        RENDER_HOOK=base + "/deploy/srv-test?key=synthetic-hook-key",
        VERCEL_TOKEN="synthetic-vercel-token",
        VERCEL_PROJECT_ID="prj_test",
        VERCEL_API=base,
        RELEASE_TIMEOUT_SECONDS=str(timeout),
        RELEASE_POLL_SECONDS="0.2",
        RELEASE_MODE="full",
    )
    env.update(extra)
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=60
    )


def test_deploys_exact_commit_and_waits_until_both_hosts_serve_it():
    with hosts() as (base, state):
        result = run(base)
    assert result.returncode == 0, result.stdout + result.stderr
    assert state["hook_refs"] == [SHA]  # Render was told the exact commit.
    assert state["api_polls"] > 2  # The old-but-healthy API did not count as success.
    assert state["promoted"] == ["dpl_test123"]
    assert set(state["auth"]) == {"Bearer synthetic-vercel-token"}
    for secret in ("synthetic-hook-key", "synthetic-vercel-token"):
        assert secret not in result.stdout + result.stderr


def test_old_api_revision_never_counts_as_released():
    with hosts(api_switches_after=10**6) as (base, state):
        result = run(base, timeout=2)
    assert result.returncode != 0 and "Timed out" in result.stdout + result.stderr
    assert state["promoted"] == []  # The frontend is not released ahead of a failed API.


def test_failed_vercel_build_and_refused_hook_fail_the_release():
    with hosts(vercel_state="ERROR") as (base, state):
        failed = run(base)
    assert failed.returncode != 0 and state["promoted"] == []
    with hosts(hook_status=403) as (base, state):
        refused = run(base)
    assert refused.returncode != 0 and "refused" in refused.stdout + refused.stderr


def test_rejects_anything_but_a_full_sha():
    with hosts() as (base, state):
        env = dict(os.environ, SHA="main", RENDER_HOOK=base + "/deploy/srv-test?key=k")
        bad = subprocess.run(
            [sys.executable, "-I", str(SCRIPT)], env=env, capture_output=True, text=True
        )
    assert bad.returncode != 0 and state["hook_refs"] == []


def test_api_only_waits_for_exact_revision_without_vercel_credentials_or_requests():
    with hosts() as (base, state):
        result = run(
            base,
            RELEASE_MODE="api",
            VERCEL_TOKEN="",
            VERCEL_PROJECT_ID="",
            WEB_URL="",
        )
    assert result.returncode == 0, result.stdout + result.stderr
    assert state["hook_refs"] == [SHA] and state["api_polls"] > 2
    assert state["promoted"] == [] and state["auth"] == []
    assert "Released API" in result.stdout
    assert "synthetic-hook-key" not in result.stdout + result.stderr


def test_unknown_release_mode_cannot_trigger_any_deployment():
    with hosts() as (base, state):
        result = run(base, RELEASE_MODE="unknown")
    assert result.returncode != 0
    assert state["hook_refs"] == [] and state["promoted"] == []
