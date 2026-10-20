import asyncio
import json
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from app.config import get_settings
from app.services.llm import LLMError
from app.services.llm.gemini import GeminiClient


@contextmanager
def server(responses):
    requests = []
    headers = []
    paths = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            paths.append(self.path)
            headers.append(dict(self.headers))
            requests.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            code, events = responses[min(len(requests) - 1, len(responses) - 1)]
            self.send_response(code)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            if callable(events):
                events = events()
            try:
                for value in events:
                    self.wfile.write(("data: " + json.dumps(value) + "\n\n").encode())
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        # Keep request bodies compatible with earlier tests; transport metadata is separate.
        server.last_headers = headers
        server.last_paths = paths
        yield f"http://127.0.0.1:{http.server_port}", requests
    finally:
        http.shutdown()
        http.server_close()
        thread.join()


def tokens(text="Safe answer"):
    return [{"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}]}]


def tool(name="suggest_category", args='{"category":"software"}'):
    return [
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "functionCall": {"name": name, "args": json.loads(args)},
                                "thoughtSignature": "local-signature",
                            }
                        ]
                    },
                    "finishReason": "STOP",
                }
            ]
        }
    ]


def client(url):
    from pydantic import SecretStr

    cfg = get_settings().model_copy(
        update={
            "llm_model": "local-test-model",
            "llm_api_key": SecretStr("test-key-not-real"),
            "llm_timeout_seconds": 2,
        }
    )
    return GeminiClient(cfg, base_url=url)


def test_live_adapter_real_local_http_stream_and_transient_retries(caplog):
    with server([(503, []), (200, tokens())]) as (url, requests):

        async def run():
            return [
                event
                async for event in client(url).stream(
                    system="system", messages=[{"role": "user", "content": "question"}], tools=[]
                )
            ]

        result = asyncio.run(run())
        assert result[0].text == "Safe answer"
        assert len(requests) == 2 and "contents" in requests[0]
        assert requests[0]["generationConfig"]["maxOutputTokens"] == get_settings().llm_max_tokens
    assert "test-key-not-real" not in caplog.text


def test_live_adapter_auth_errors_not_retried_or_leaked():
    with server([(401, tokens("SECRET_PROVIDER_RESPONSE"))]) as (url, requests):

        async def run():
            return [event async for event in client(url).stream(system="", messages=[], tools=[])]

        with pytest.raises(LLMError) as error:
            asyncio.run(run())
        assert len(requests) == 1 and "SECRET" not in str(error.value)


def test_gemini_preserves_signed_function_parts_and_real_tool_response():
    with server(
        [
            (200, tool(name="spend_summary", args='{"period":"month"}')),
            (200, tokens("Monthly spend: ₹123.45")),
        ]
    ) as (url, requests):
        sender = client(url)

        async def run():
            events = [
                event
                async for event in sender.stream(
                    system="system", messages=[{"role": "user", "content": "spend"}], tools=[]
                )
            ]
            call = events[0].call
            messages = [
                {"role": "user", "content": "spend"},
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": call.id,
                            "name": call.name,
                            "input": call.arguments,
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": call.id,
                            "content": '{"monthly_total":"123.45"}',
                        }
                    ],
                },
            ]
            return [
                event
                async for event in sender.stream(
                    system="system", messages=messages, tools=[], force_final=True
                )
            ]

        events = asyncio.run(run())
        assert events[0].text == "Monthly spend: ₹123.45"
        assert requests[1]["contents"][1]["parts"][0]["thoughtSignature"] == "local-signature"
        assert requests[1]["contents"][2]["parts"][0]["functionResponse"]["response"] == {
            "monthly_total": "123.45"
        }


def test_live_adapter_per_call_timeout_closes_local_stream():
    def delayed():
        time.sleep(2)
        return tokens("too late")

    with server([(200, delayed)]) as (url, requests):
        sender = client(url)
        sender.settings = sender.settings.model_copy(
            update={"llm_timeout_seconds": 1, "llm_retries": 0}
        )

        async def run():
            return [e async for e in sender.stream(system="", messages=[], tools=[])]

        with pytest.raises(LLMError):
            asyncio.run(run())
        assert len(requests) == 1


@pytest.mark.parametrize(
    "arguments,expected",
    [
        ('{"category":"software"}', "software"),
        ('{"category":"anything"}', None),
        ('{"category":"software","user_id":"x"}', None),
    ],
)
def test_categorization_body_is_merchant_only_and_schema_constrained(arguments, expected):
    with server([(200, tokens(arguments))]) as (url, requests):
        assert asyncio.run(client(url).categorize("mystery merchant")) == expected
        body = requests[0]
        assert body["contents"] == [
            {"role": "user", "parts": [{"text": json.dumps({"merchant": "mystery merchant"})}]}
        ]
        assert "amount" not in json.dumps(body) and "date" not in json.dumps(body)
        assert "user_id" not in json.dumps(body)
        assert body["generationConfig"]["responseJsonSchema"]["additionalProperties"] is False
        assert body["generationConfig"]["responseMimeType"] == "application/json"
        assert "tools" not in body


def test_all_seven_provider_schemas_are_sanitized_without_weakening_server_validation():
    from copy import deepcopy

    from pydantic import ValidationError

    from app.services.chat_tools import SCHEMAS, definitions
    from app.services.llm.schemas import KEYWORDS, provider_schema

    def check(node):
        assert not set(node) - KEYWORDS
        for child in node.get("properties", {}).values():
            check(child)
        if "items" in node:
            check(node["items"])

    for definition in definitions():
        original = deepcopy(definition["input_schema"])
        check(provider_schema(original))
        assert original == definition["input_schema"]
        with pytest.raises(ValidationError):
            SCHEMAS[definition["name"]].model_validate({"user_id": "other-user"})
    nested = {
        "$defs": {"Thing": {"type": "string", "minLength": 1}},
        "type": "object",
        "properties": {"value": {"$ref": "#/$defs/Thing"}},
    }
    assert provider_schema(nested)["properties"]["value"] == {"type": "string"}
    with pytest.raises(ValueError):
        provider_schema({"$ref": "https://invalid.example/schema"})


@pytest.mark.parametrize("reason", ["SAFETY", "MAX_TOKENS", "RECITATION", "BLOCKLIST"])
def test_safety_and_truncated_completions_signal_blocked(reason):
    events = tokens("unverified provider material")
    events[0]["candidates"][0]["finishReason"] = reason
    with server([(200, events)]) as (url, _):

        async def run():
            return [e async for e in client(url).stream(system="", messages=[], tools=[])]

        assert asyncio.run(run())[-1].kind == "blocked"


@pytest.mark.parametrize(
    "events",
    [
        [],
        [{"candidates": []}],
        [{"promptFeedback": {"blockReason": "SAFETY"}}],
        [{"candidates": [{"finishReason": "STOP", "content": {"parts": []}}]}],
    ],
)
def test_empty_and_prompt_blocked_responses_signal_blocked(events):
    with server([(200, events)]) as (url, _):

        async def run():
            return [e async for e in client(url).stream(system="", messages=[], tools=[])]

        assert [event.kind for event in asyncio.run(run())] == ["blocked"]


@pytest.mark.parametrize("code", [429, 500, 502, 503, 504])
def test_transient_retry_bound_and_secret_header_only(code, caplog):
    with server([(code, [])]) as (url, requests):

        async def run():
            return [e async for e in client(url).stream(system="", messages=[], tools=[])]

        with pytest.raises(LLMError):
            asyncio.run(run())
        assert len(requests) == get_settings().llm_retries + 1
        assert all(h.get("x-goog-api-key") == "test-key-not-real" for h in server.last_headers)
        assert all(
            "key=" not in path and "test-key-not-real" not in path for path in server.last_paths
        )
    assert "test-key-not-real" not in caplog.text
    assert "test-key-not-real" not in json.dumps(requests)


def test_parallel_calls_keep_order_and_malformed_arguments_are_not_executed():
    events = tool(name="spend_summary", args='{"period":"year"}')
    parts = events[0]["candidates"][0]["content"]["parts"]
    parts.append({"functionCall": {"name": "potential_savings", "args": "invalid"}})
    with server([(200, events)]) as (url, _):

        async def run():
            return [e async for e in client(url).stream(system="", messages=[], tools=[])]

        result = asyncio.run(run())
        assert [e.call.name for e in result] == ["spend_summary", "potential_savings"]
        assert result[1].call.arguments == {"invalid_provider_arguments": True}


def test_every_declared_tool_uses_sanitized_wire_schema():
    from app.services.chat_tools import definitions
    from app.services.llm.schemas import provider_schema

    tools = definitions()
    with server([(200, tokens())]) as (url, requests):

        async def run():
            return [e async for e in client(url).stream(system="", messages=[], tools=tools)]

        asyncio.run(run())
        declared = requests[0]["tools"][0]["functionDeclarations"]
        assert len(declared) == 7
        for original, sent in zip(tools, declared):
            assert sent["parametersJsonSchema"] == provider_schema(original["input_schema"])
        assert "$ref" not in json.dumps(declared) and "$defs" not in json.dumps(declared)


def test_cancellation_closes_provider_stream_without_retry():
    def delayed():
        time.sleep(1)
        return tokens("late")

    with server([(200, delayed)]) as (url, requests):

        async def run():
            async def read():
                return [e async for e in client(url).stream(system="", messages=[], tools=[])]

            task = asyncio.create_task(read())
            await asyncio.sleep(0.2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

        asyncio.run(run())
        assert len(requests) == 1


@pytest.mark.parametrize(
    "provider,key,model",
    [("unknown", "", ""), ("gemini", "", "model"), ("gemini", "secret-key", "")],
)
def test_invalid_live_config_has_safe_startup_error(monkeypatch, provider, key, model):
    monkeypatch.setenv("LLM_PROVIDER", provider)
    monkeypatch.setenv("LLM_API_KEY", key)
    monkeypatch.setenv("LLM_MODEL", model)
    get_settings.cache_clear()
    with pytest.raises(RuntimeError) as error:
        get_settings()
    assert "Invalid configuration" in str(error.value)
    assert "secret-key" not in str(error.value)
    get_settings.cache_clear()
