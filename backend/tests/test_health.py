import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.db import get_db
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_liveness(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_contains_health_contract(client):
    spec = client.get("/api/v1/openapi.json").json()
    assert "/api/v1/health/ready" in spec["paths"]
    assert spec["info"]["title"] == "SubTrack API"


def test_readiness_does_not_hide_database_outage(client):
    class UnavailableSession:
        def execute(self, _query):
            raise OperationalError("", {}, Exception("private connection details"))

    app.dependency_overrides[get_db] = lambda: UnavailableSession()
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "not_ready"
    assert "private" not in response.text


def test_cors_only_allows_configured_origin(client):
    good = client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
    bad = client.get("/api/v1/health", headers={"Origin": "https://untrusted.example"})
    assert good.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-origin" not in bad.headers


@pytest.mark.parametrize(
    "actual,expected_status", [(["new_head"], 200), (["0001_scaffold"], 503), ([], 503)]
)
def test_readiness_compares_database_to_script_heads(client, monkeypatch, actual, expected_status):
    from unittest.mock import MagicMock

    import app.migrations as migrations

    scripts = MagicMock()
    scripts.get_heads.return_value = ["new_head"]
    monkeypatch.setattr(migrations, "ScriptDirectory", lambda _: scripts)
    session = MagicMock()
    session.execute.return_value.scalars.return_value.all.return_value = actual
    app.dependency_overrides[get_db] = lambda: session
    assert client.get("/api/v1/health/ready").status_code == expected_status
