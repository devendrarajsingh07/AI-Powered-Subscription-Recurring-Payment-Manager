"""Guard local destructive probes from normal/hosted data; no live services or secrets."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
pytestmark = pytest.mark.skipif(
    not (SCRIPTS / "local_drills.py").exists(), reason="root scripts not mounted"
)


@pytest.fixture
def drills():
    spec = importlib.util.spec_from_file_location(
        "drill_guard_subject", SCRIPTS / "local_drills.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("base", ["https://example.org/api/v1", "http://localhost:8000/api/v1"])
def test_remote_and_normal_stack_targets_rejected_before_transport(drills, base, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("A disallowed target reached Docker/network transport")

    monkeypatch.setattr(drills, "compose", forbidden)
    with pytest.raises(ValueError):
        drills.request(base, "/health")


@pytest.mark.parametrize(
    "service,database", [("api", "drill"), ("db", "subtrack"), ("hosted", "restored")]
)
def test_sql_cannot_target_normal_or_hosted_database(drills, service, database):
    with pytest.raises(ValueError):
        drills.sql("SELECT 1", service, database)


def test_prepare_preserves_existing_private_keys(drills, tmp_path, monkeypatch):
    original = "owner-private-configuration\n"
    (tmp_path / "runtime.env").write_text(original)
    monkeypatch.setattr(drills, "PRIVATE", tmp_path)
    with pytest.raises(RuntimeError, match="preserved"):
        drills.prepare()
    assert (tmp_path / "runtime.env").read_text() == original


def test_invalid_step_cannot_report_empty_success(drills):
    with pytest.raises(ValueError, match="Unknown coordination step"):
        drills.coordination("misspelled-step")


def test_setup_login_honors_server_backoff_without_changing_limits(drills, monkeypatch):
    attempts, delays = [], []

    def transport(*args, **kwargs):
        attempts.append(1)
        if len(attempts) == 1:
            raise drills.HttpFailure(429, "POST", "/auth/login", "2")
        return 200, {"access_token": "synthetic-test-token"}

    monkeypatch.setattr(drills, "request", transport)
    monkeypatch.setattr(drills.time, "sleep", delays.append)
    assert (
        drills.login("synthetic@example.org", "synthetic-test-only")["access_token"]
        == "synthetic-test-token"
    )
    assert delays == [2.1] and len(attempts) == 2


def test_scanner_summary_strips_sensitive_instance_evidence(drills):
    report = {
        "site": [
            {
                "alerts": [
                    {
                        "pluginid": "10000",
                        "name": "Synthetic scanner rule",
                        "riskcode": "1",
                        "confidence": "2",
                        "instances": [
                            {
                                "uri": "http://local/?private-token",
                                "evidence": "private-financial-body",
                                "headers": "private-address",
                            }
                        ],
                        "description": "private-full-description",
                    }
                ]
            }
        ]
    }
    result = drills.sanitize_zap(report)
    assert result == [
        dict(id="10000", name="Synthetic scanner rule", risk=1, confidence=2, instances=1)
    ]
    encoded = json.dumps(result)
    assert all(
        value not in encoded
        for value in [
            "private-token",
            "private-financial-body",
            "private-address",
            "private-full-description",
        ]
    )


def test_probe_rejects_remote_before_network():
    value = dict(
        base="https://example.org", route="/", headers={}, data=None, method="GET", timeout=1
    )
    process = subprocess.run(
        [sys.executable, str(SCRIPTS / "drill_http.py")],
        input=json.dumps(value).encode(),
        capture_output=True,
        timeout=5,
    )
    assert process.returncode != 0
    assert b"Only isolated drill APIs" in process.stderr


@pytest.mark.parametrize("name", ["subtrack-api-1", "production-k6"])
def test_finite_container_cannot_remove_normal_services(drills, name):
    with pytest.raises(ValueError):
        drills.finite_container(name, [], timeout=1)


@pytest.mark.parametrize("owned", [True, False])
def test_timeout_cleanup_checks_container_ownership(drills, monkeypatch, owned):
    commands = []

    def transport(args, **kwargs):
        commands.append(args)
        if args[1] == "run":
            raise subprocess.TimeoutExpired(args, 1)
        if args[1] == "ps":
            return SimpleNamespace(stdout=b"synthetic-container-id", returncode=0)
        if args[1] == "inspect":
            labels = {"subtrack.drill": "true"} if owned else {}
            return SimpleNamespace(
                stdout=json.dumps([{"Config": {"Labels": labels}}]).encode(), returncode=0
            )
        assert args == ["docker", "rm", "-f", "synthetic-container-id"] and owned
        return SimpleNamespace(stdout=b"", returncode=0)

    monkeypatch.setattr(drills, "run", transport)
    with pytest.raises(subprocess.TimeoutExpired if owned else RuntimeError):
        drills.finite_container("subtrack-drills-k6", [], timeout=1)
    assert any(args[1] == "rm" for args in commands) is owned
