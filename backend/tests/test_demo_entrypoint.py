"""Real subprocess checks: invalid demo configuration fails before touching the DB."""

import os
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from conftest import alembic_config

from alembic import command


@pytest.mark.parametrize("environment", ["production", "test", ""])
def test_demo_entrypoint_refuses_non_development(environment):
    result = run(environment=environment)
    assert result.returncode != 0
    assert "only for a development/demo" in result.stderr
    assert "alembic" not in result.stderr


def run(**values):
    env = dict(os.environ, ENVIRONMENT="development", JWT_SECRET="", PORT="8000")
    env.update({key.upper(): value for key, value in values.items()})
    return subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts/start_demo_server.py")],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def test_demo_entrypoint_missing_secret_is_safe():
    result = run()
    assert result.returncode != 0
    assert "Configure a generated JWT_SECRET" in result.stderr


@pytest.mark.parametrize("port", ["zero", "0", "65536"])
def test_demo_entrypoint_rejects_invalid_port_without_echoing_secret(port):
    secret = secrets.token_urlsafe(48)
    result = run(jwt_secret=secret, port=port)
    assert result.returncode != 0
    assert "PORT must be" in result.stderr
    assert secret not in result.stderr + result.stdout


def test_demo_entrypoint_migrates_empty_postgres_and_serves_readiness(pg_engine):
    assert pg_engine.url.database.startswith("subtrack_test_")
    with pg_engine.begin() as connection:
        command.downgrade(alembic_config(connection), "base")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    secret = secrets.token_urlsafe(48)
    env = dict(
        os.environ,
        ENVIRONMENT="development",
        JWT_SECRET=secret,
        DATABASE_URL=pg_engine.url.render_as_string(hide_password=False),
        PORT=str(port),
        SCHEDULER_ENABLED="false",
    )
    process = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts/start_demo_server.py")],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            assert process.poll() is None, "Demo entry point exited before readiness"
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/api/v1/health/ready", timeout=1
                ) as response:
                    assert response.status == 200
                    break
            except (urllib.error.URLError, TimeoutError):
                time.sleep(0.1)
        else:
            pytest.fail("Demo entry point did not become ready within the test deadline")
    finally:
        process.terminate()
        stdout, stderr = process.communicate(timeout=10)
        with pg_engine.begin() as connection:
            command.upgrade(alembic_config(connection), "head")
    assert secret not in stdout + stderr
