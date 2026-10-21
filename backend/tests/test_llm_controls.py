"""WP6: kill switch, shared global caps, visible offline fallback. Local stand-ins only."""

import json
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
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


class Counting(LiveFake):
    """Counts provider requests actually sent (each `stream` call is one request)."""

    sent = 0

    async def stream(self, **kwargs):
        type(self).sent += 1
        async for item in super().stream(**kwargs):
            yield item


class KillAfterFirst(Counting):
    """The operator flips the kill switch while the first provider request is in flight."""

    engine = None

    async def stream(self, **kwargs):
        async for item in super().stream(**kwargs):
            yield item
        if type(self).sent == 1:
            controls.set_switch(type(self).engine, True)


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


def test_every_provider_request_is_reserved_before_it_is_sent(api_client, pg_engine):
    Counting.sent = 0
    headers = setup(api_client, Counting)
    result, _ = answer(api_client, headers, "monthly total")
    assert result["mode"] == "live" and result["fallback_reason"] is None and result["verified"]
    used = controls.usage(pg_engine)
    # One reservation per provider request (tool round + final round), never per turn.
    assert Counting.sent >= 2 and used["requests"] == Counting.sent
    # Each reservation includes the full output allowance, charged up front.
    assert used["tokens"] >= Counting.sent * get_settings().llm_max_tokens
    assert used["fallbacks"] == 0 and used["errors"] == 0


def test_kill_switch_stops_the_next_request_inside_an_active_turn(api_client, pg_engine, db):
    KillAfterFirst.sent, KillAfterFirst.engine = 0, pg_engine
    headers = setup(api_client, KillAfterFirst)
    result, events = answer(api_client, headers, "monthly total")
    assert KillAfterFirst.sent == 1  # The second round was never sent to the provider.
    assert result["mode"] == "offline" and result["fallback_reason"] == "kill_switch"
    assert result["verified"] and not any(e[0] == "error" for e in events)
    used = controls.usage(pg_engine)
    assert used["requests"] == 1 and used["fallbacks"] == 1
    db.expire_all()
    assert sorted(r.role for r in db.scalars(select(m.ChatMessage))) == ["assistant", "user"]


def test_request_cap_reached_mid_turn_sends_nothing_more(api_client, pg_engine, monkeypatch):
    monkeypatch.setenv("LLM_GLOBAL_DAILY_REQUESTS", "1")
    get_settings.cache_clear()
    Counting.sent = 0
    headers = setup(api_client, Counting)
    result, _ = answer(api_client, headers, "monthly total")
    assert Counting.sent == 1 and controls.usage(pg_engine)["requests"] == 1
    assert result["mode"] == "offline" and result["fallback_reason"] == "daily_cap"


def test_failed_provider_request_still_counts_requests_and_tokens(api_client, pg_engine):
    headers = setup(api_client, Broken)
    answer(api_client, headers, "monthly total")
    used = controls.usage(pg_engine)
    assert used["requests"] == 1 and used["tokens"] >= get_settings().llm_max_tokens


def test_rejected_requests_consume_no_shared_quota(api_client, pg_engine):
    headers = setup(api_client, Counting)
    for _ in range(2):
        missing = api_client.post(
            "/api/v1/chat",
            headers=headers,
            json={"message": "monthly total", "conversation_id": str(uuid.uuid4())},
        )
        assert missing.status_code == 404
    empty = api_client.post("/api/v1/chat", headers=headers, json={"message": "   "})
    assert empty.status_code in (400, 422)
    assert controls.usage(pg_engine) == dict(requests=0, tokens=0, fallbacks=0, errors=0)


def test_reservation_never_overshoots_token_cap(pg_engine, monkeypatch):
    monkeypatch.setenv("LLM_GLOBAL_DAILY_TOKENS", "5000")
    get_settings.cache_clear()
    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(lambda _: controls.reserve(pg_engine, 1500), range(8)))
    assert outcomes.count(None) == 3 and controls.usage(pg_engine)["tokens"] == 4500
    assert controls.reserve(pg_engine, 6000) == "daily_cap"  # Larger than the whole cap.


def test_transport_retries_are_guarded_individually(pg_engine, monkeypatch):
    """A 503 retry is a second provider request: it must pass the guard or never be sent."""
    import asyncio

    from test_llm import client as gemini
    from test_llm import server, tokens

    monkeypatch.setenv("LLM_GLOBAL_DAILY_REQUESTS", "1")
    get_settings.cache_clear()
    with server([(503, []), (200, tokens())]) as (url, requests):
        live = gemini(url)
        live.before_request = lambda: controls.guard(pg_engine, live, 10)
        assert controls.reserve(pg_engine, 10) is None  # The first attempt's reservation.

        async def run():
            return [
                e
                async for e in live.stream(
                    system="s", messages=[{"role": "user", "content": "q"}], tools=[]
                )
            ]

        with pytest.raises(controls.Bypass) as stopped:
            asyncio.run(run())
        assert len(requests) == 1  # The retry was refused before it reached the provider.
    assert stopped.value.reason == "daily_cap" and controls.usage(pg_engine)["requests"] == 1


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
    Counting.sent = 0
    headers = setup(api_client, Counting)
    answer(api_client, headers, "monthly total")
    per_turn = Counting.sent
    monkeypatch.setenv("LLM_GLOBAL_DAILY_REQUESTS", str(per_turn * 2))
    get_settings.cache_clear()
    modes = [answer(api_client, headers, "monthly total")[0] for _ in range(2)]
    assert [r["mode"] for r in modes] == ["live", "offline"]
    assert modes[1]["fallback_reason"] == "daily_cap" and modes[1]["verified"]
    # Never above the cap, and refused requests are not sent or counted.
    assert controls.usage(pg_engine)["requests"] == per_turn * 2 == Counting.sent


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
