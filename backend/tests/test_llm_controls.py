"""WP6: kill switch, shared global caps, visible offline fallback. Local stand-ins only."""

import json
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select
from test_api import account
from test_chat_evals import answer

from app import models as m
from app.config import get_settings
from app.main import app
from app.services import llm_controls as controls
from app.services.llm import LLMError, get_client
from app.services.llm.fake import FakeLLM


class LiveFake(FakeLLM):
    """Deterministic stand-in for a live provider: same tools, but marked as leaving the host."""

    live = True


class Broken(LiveFake):
    async def stream(self, **kwargs):
        raise LLMError()
        yield  # pragma: no cover - makes this an async generator


def consent(client, headers):
    response = client.put("/api/v1/chat/config", headers=headers, json={"live_opt_in": True})
    assert response.status_code == 200


def setup(api_client, client_cls=LiveFake):
    app.dependency_overrides[get_client] = lambda: client_cls()
    headers, _ = account(api_client)
    consent(api_client, headers)
    return headers


def test_live_turn_counts_a_request_and_estimated_tokens(api_client, pg_engine):
    headers = setup(api_client)
    result, _ = answer(api_client, headers, "monthly total")
    assert result["mode"] == "live" and result["fallback_reason"] is None and result["verified"]
    used = controls.usage(pg_engine)
    assert used["requests"] == 1 and used["tokens"] > 0
    assert used["fallbacks"] == 0 and used["errors"] == 0


def test_database_kill_switch_forces_offline_immediately_without_consent(api_client, pg_engine):
    headers = setup(api_client)
    controls.set_switch(pg_engine, True)  # Operator action; no restart, no deploy.
    result, events = answer(api_client, headers, "monthly total")
    assert result["mode"] == "offline" and result["fallback_reason"] == "kill_switch"
    assert result["verified"]
    used = controls.usage(pg_engine)
    assert used["requests"] == 0 and used["fallbacks"] == 1
    controls.set_switch(pg_engine, False)
    assert answer(api_client, headers, "monthly total")[0]["mode"] == "live"
    # A killed provider needs no consent at all: nothing leaves the deployment.
    app.dependency_overrides[get_client] = lambda: LiveFake()
    other, _ = account(api_client, "second-user@example.org")
    controls.set_switch(pg_engine, True)
    assert answer(api_client, other, "monthly total")[0]["fallback_reason"] == "kill_switch"


def test_environment_kill_switch(api_client, pg_engine, monkeypatch):
    headers = setup(api_client)
    monkeypatch.setenv("LLM_KILL_SWITCH", "true")
    get_settings.cache_clear()
    result, _ = answer(api_client, headers, "monthly total")
    assert result["mode"] == "offline" and result["fallback_reason"] == "kill_switch"


def test_global_request_cap_is_shared_and_falls_back_visibly(api_client, pg_engine, monkeypatch):
    monkeypatch.setenv("LLM_GLOBAL_DAILY_REQUESTS", "2")
    get_settings.cache_clear()
    headers = setup(api_client)
    modes = [answer(api_client, headers, "monthly total")[0] for _ in range(3)]
    assert [r["mode"] for r in modes] == ["live", "live", "offline"]
    assert modes[2]["fallback_reason"] == "daily_cap" and modes[2]["verified"]
    assert controls.usage(pg_engine)["requests"] == 2  # The refused call is not counted.


def test_global_token_cap_stops_live_calls(api_client, pg_engine, monkeypatch):
    monkeypatch.setenv("LLM_GLOBAL_DAILY_TOKENS", "1000")
    get_settings.cache_clear()
    headers = setup(api_client)
    controls.note(pg_engine, "tokens", 1000)
    result, _ = answer(api_client, headers, "monthly total")
    assert result["fallback_reason"] == "daily_cap" and result["mode"] == "offline"


def test_cap_is_atomic_across_independent_connections(pg_engine, monkeypatch):
    monkeypatch.setenv("LLM_GLOBAL_DAILY_REQUESTS", "3")
    get_settings.cache_clear()
    with ThreadPoolExecutor(max_workers=10) as pool:
        outcomes = list(pool.map(lambda _: controls.reserve(pg_engine), range(10)))
    assert outcomes.count(None) == 3 and outcomes.count("daily_cap") == 7
    assert controls.usage(pg_engine)["requests"] == 3


def test_provider_error_falls_back_to_verified_offline_answer_without_duplicate_history(
    api_client, pg_engine, db
):
    headers = setup(api_client, Broken)
    result, events = answer(api_client, headers, "monthly total")
    assert result["mode"] == "offline" and result["fallback_reason"] == "provider_error"
    assert result["verified"] and not any(e[0] == "error" for e in events)
    used = controls.usage(pg_engine)
    assert used["errors"] == 1 and used["fallbacks"] == 1
    db.expire_all()
    rows = list(db.scalars(select(m.ChatMessage)))
    assert sorted(r.role for r in rows) == ["assistant", "user"]  # One pair, not two.


def test_offline_deployment_is_untouched_and_never_counts(api_client, pg_engine):
    app.dependency_overrides[get_client] = lambda: FakeLLM()
    headers, _ = account(api_client)
    result, _ = answer(api_client, headers, "monthly total")
    assert result["mode"] == "offline" and result["fallback_reason"] is None
    assert controls.usage(pg_engine) == dict(requests=0, tokens=0, fallbacks=0, errors=0)


def test_config_reports_why_live_is_off_without_leaking_secrets(api_client, pg_engine, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("LLM_API_KEY", "synthetic-key-never-returned")
    monkeypatch.setenv("LLM_MODEL", "synthetic-model")
    get_settings.cache_clear()
    headers, _ = account(api_client)
    live = api_client.get("/api/v1/chat/config", headers=headers).json()
    assert live["mode"] == "live" and live["fallback_reason"] is None
    controls.set_switch(pg_engine, True)
    off = api_client.get("/api/v1/chat/config", headers=headers)
    assert off.json()["mode"] == "offline" and off.json()["fallback_reason"] == "kill_switch"
    assert "synthetic-key" not in off.text and "synthetic-key" not in json.dumps(live)
