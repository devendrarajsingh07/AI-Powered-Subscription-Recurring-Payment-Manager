import asyncio
import json
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from app.config import get_settings
from app.services.llm import LLMError
from app.services.llm.anthropic import AnthropicClient


@contextmanager
def server(responses):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
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
        yield f"http://127.0.0.1:{http.server_port}", requests
    finally:
        http.shutdown()
        http.server_close()
        thread.join()


def tokens(text="Safe answer"):
    return [
        dict(type="content_block_start", index=0, content_block={"type": "text", "text": ""}),
        dict(type="content_block_delta", index=0, delta={"type": "text_delta", "text": text}),
        dict(type="content_block_stop", index=0),
        dict(type="message_stop"),
    ]


def tool(name="suggest_category", args='{"category":"software"}'):
    return [
        dict(
            type="content_block_start",
            index=0,
            content_block={"type": "tool_use", "id": "test-call", "name": name, "input": {}},
        ),
        dict(
            type="content_block_delta",
            index=0,
            delta={"type": "input_json_delta", "partial_json": args[:8]},
        ),
        dict(
            type="content_block_delta",
            index=0,
            delta={"type": "input_json_delta", "partial_json": args[8:]},
        ),
        dict(type="content_block_stop", index=0),
        dict(type="message_stop"),
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
    return AnthropicClient(cfg, base_url=url)


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
        assert len(requests) == 2 and requests[0]["stream"] is True
        assert requests[0]["max_tokens"] == get_settings().llm_max_tokens
    assert "test-key-not-real" not in caplog.text


def test_live_adapter_auth_errors_not_retried_or_leaked():
    with server([(401, tokens("SECRET_PROVIDER_RESPONSE"))]) as (url, requests):

        async def run():
            return [event async for event in client(url).stream(system="", messages=[], tools=[])]

        with pytest.raises(LLMError) as error:
            asyncio.run(run())
        assert len(requests) == 1 and "SECRET" not in str(error.value)


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
    with server([(200, tool(args=arguments))]) as (url, requests):
        assert asyncio.run(client(url).categorize("mystery merchant")) == expected
        body = requests[0]
        assert body["messages"] == [
            {"role": "user", "content": json.dumps({"merchant": "mystery merchant"})}
        ]
        assert "amount" not in json.dumps(body) and "date" not in json.dumps(body)
        assert "user_id" not in json.dumps(body)
        assert body["tools"][0]["input_schema"]["additionalProperties"] is False


@pytest.mark.parametrize(
    "provider,key,model",
    [("unknown", "", ""), ("anthropic", "", "model"), ("anthropic", "secret-key", "")],
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
