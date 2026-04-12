"""OpenAICompatibleAdapter — httpx.MockTransport 기반 단위 테스트."""

from __future__ import annotations

import json

import httpx
import pytest

from orca_core.providers import (
    ChatMessage,
    ChatRequest,
    ChatToolCall,
    ChatToolDefinition,
    InMemorySecretStore,
    OpenAICompatibleAdapter,
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from orca_core.schema import Provider


def _make_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _provider(api_key_ref: str | None = None) -> Provider:
    return Provider(
        name="test",
        kind="openai_compatible",
        base_url="https://example.test",
        api_key_ref=api_key_ref,
        timeout_ms=5_000,
    )


def _chat_req() -> ChatRequest:
    return ChatRequest(
        model="gpt-test",
        messages=[ChatMessage(role="user", content="hi")],
    )


def _success_body(content: str = "hello") -> dict:
    return {
        "model": "gpt-test",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


async def test_chat_success_parses_response():
    calls: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        return httpx.Response(200, json=_success_body())

    client = _make_client(handler)
    adapter = OpenAICompatibleAdapter(_provider(), http_client=client)
    resp = await adapter.chat(_chat_req())

    assert resp.message.content == "hello"
    assert resp.usage.total_tokens == 2
    assert resp.finish_reason == "stop"
    assert calls[0].url.path == "/v1/chat/completions"


async def test_chat_auth_header_from_secret_store():
    captured: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        return httpx.Response(200, json=_success_body())

    client = _make_client(handler)
    store = InMemorySecretStore({"my-key": "sk-topsecret"})
    adapter = OpenAICompatibleAdapter(
        _provider(api_key_ref="my-key"), secret_store=store, http_client=client
    )
    await adapter.chat(_chat_req())
    auth = captured[0].headers.get("Authorization")
    assert auth == "Bearer sk-topsecret"


async def test_chat_auth_error_raises_provider_auth_error():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    adapter = OpenAICompatibleAdapter(_provider(), http_client=_make_client(handler))
    with pytest.raises(ProviderAuthError):
        await adapter.chat(_chat_req())


async def test_chat_rate_limited_raises_after_retries():
    count = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        count["n"] += 1
        return httpx.Response(429, json={"error": "slow down"})

    adapter = OpenAICompatibleAdapter(_provider(), http_client=_make_client(handler), max_retries=2)
    with pytest.raises(ProviderRateLimitedError):
        await adapter.chat(_chat_req())
    assert count["n"] == 2


async def test_chat_500_retries_then_raises_unavailable():
    count = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        count["n"] += 1
        return httpx.Response(503, text="unavailable")

    adapter = OpenAICompatibleAdapter(_provider(), http_client=_make_client(handler), max_retries=2)
    with pytest.raises(ProviderUnavailableError):
        await adapter.chat(_chat_req())
    assert count["n"] == 2


async def test_chat_500_recovers_on_second_attempt():
    count = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        count["n"] += 1
        if count["n"] == 1:
            return httpx.Response(503, text="unavailable")
        return httpx.Response(200, json=_success_body("second"))

    adapter = OpenAICompatibleAdapter(_provider(), http_client=_make_client(handler), max_retries=3)
    resp = await adapter.chat(_chat_req())
    assert resp.message.content == "second"


async def test_chat_client_error_4xx_non_retry():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="bad request body here")

    adapter = OpenAICompatibleAdapter(_provider(), http_client=_make_client(handler))
    with pytest.raises(ProviderError):
        await adapter.chat(_chat_req())


async def test_chat_timeout_raises_timeout_error():
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=req)

    adapter = OpenAICompatibleAdapter(_provider(), http_client=_make_client(handler), max_retries=2)
    with pytest.raises(ProviderTimeoutError):
        await adapter.chat(_chat_req())


async def test_chat_tool_call_parsing():
    tool_args = {"path": "/tmp/x"}
    body = {
        "model": "gpt-test",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "fs.read_file",
                                "arguments": json.dumps(tool_args),
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    adapter = OpenAICompatibleAdapter(_provider(), http_client=_make_client(handler))
    resp = await adapter.chat(
        ChatRequest(
            model="gpt-test",
            messages=[ChatMessage(role="user", content="read")],
            tools=[
                ChatToolDefinition(
                    name="fs.read_file",
                    description="read",
                    parameters={"type": "object"},
                )
            ],
            tool_choice="auto",
        )
    )
    assert resp.finish_reason == "tool_calls"
    assert len(resp.message.tool_calls) == 1
    assert resp.message.tool_calls[0].name == "fs.read_file"
    assert resp.message.tool_calls[0].arguments == tool_args


async def test_chat_payload_contains_tools_and_params():
    captured: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        return httpx.Response(200, json=_success_body())

    adapter = OpenAICompatibleAdapter(_provider(), http_client=_make_client(handler))
    await adapter.chat(
        ChatRequest(
            model="gpt-test",
            messages=[ChatMessage(role="user", content="hi")],
            temperature=0.2,
            max_tokens=100,
            stop=["\n\n"],
            tools=[
                ChatToolDefinition(name="fs.read_file", description="read", parameters={"x": 1})
            ],
            tool_choice="required",
        )
    )
    payload = json.loads(captured[0].content.decode())
    assert payload["temperature"] == 0.2
    assert payload["max_tokens"] == 100
    assert payload["stop"] == ["\n\n"]
    assert payload["tools"][0]["function"]["name"] == "fs.read_file"
    assert payload["tool_choice"] == "required"


async def test_health_returns_models_from_v1_models():
    body = {"data": [{"id": "gpt-4"}, {"id": "gpt-3.5"}]}

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    adapter = OpenAICompatibleAdapter(_provider(), http_client=_make_client(handler))
    health = await adapter.health()
    assert health.ok is True
    assert set(health.models) == {"gpt-4", "gpt-3.5"}


async def test_health_failure_reports_not_ok():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="down")

    adapter = OpenAICompatibleAdapter(_provider(), http_client=_make_client(handler))
    health = await adapter.health()
    assert health.ok is False


async def test_message_tool_call_serializes_to_openai_format():
    captured: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        return httpx.Response(200, json=_success_body())

    adapter = OpenAICompatibleAdapter(_provider(), http_client=_make_client(handler))
    await adapter.chat(
        ChatRequest(
            model="gpt-test",
            messages=[
                ChatMessage(role="user", content="hi"),
                ChatMessage(
                    role="assistant",
                    content="",
                    tool_calls=[
                        ChatToolCall(id="call_1", name="fs.read_file", arguments={"path": "/a"})
                    ],
                ),
                ChatMessage(role="tool", content="result", tool_call_id="call_1"),
            ],
        )
    )
    payload = json.loads(captured[0].content.decode())
    msgs = payload["messages"]
    assert msgs[1]["tool_calls"][0]["function"]["name"] == "fs.read_file"
    assert msgs[2]["tool_call_id"] == "call_1"


async def test_stream_chat_emits_at_least_one_chunk():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_success_body("streaming"))

    adapter = OpenAICompatibleAdapter(_provider(), http_client=_make_client(handler))
    chunks = [c async for c in adapter.stream_chat(_chat_req())]
    assert len(chunks) == 1
    assert chunks[0].delta == "streaming"


async def test_aclose_external_client_is_noop():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_success_body())

    client = _make_client(handler)
    adapter = OpenAICompatibleAdapter(_provider(), http_client=client)
    await adapter.aclose()
    # External client should still be usable
    assert not client.is_closed


async def test_health_transport_error_returns_not_ok():
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=req)

    adapter = OpenAICompatibleAdapter(_provider(), http_client=_make_client(handler))
    health = await adapter.health()
    assert health.ok is False
    assert health.message == "ConnectError"


async def test_chat_response_without_choices_raises_provider_error():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"model": "x", "choices": []})

    adapter = OpenAICompatibleAdapter(_provider(), http_client=_make_client(handler))
    with pytest.raises(ProviderError, match="no choices"):
        await adapter.chat(_chat_req())


async def test_chat_response_non_json_raises_provider_error():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json", headers={"content-type": "text/plain"})

    adapter = OpenAICompatibleAdapter(_provider(), http_client=_make_client(handler))
    with pytest.raises(ProviderError):
        await adapter.chat(_chat_req())


async def test_error_messages_do_not_leak_secrets():
    captured: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        return httpx.Response(500, text="boom")

    store = InMemorySecretStore({"key1": "sk-supersecret-123"})
    adapter = OpenAICompatibleAdapter(
        _provider(api_key_ref="key1"),
        secret_store=store,
        http_client=_make_client(handler),
        max_retries=1,
    )
    try:
        await adapter.chat(_chat_req())
    except ProviderUnavailableError as exc:
        # error payload should NOT contain the secret value
        payload = exc.to_payload()
        assert "sk-supersecret-123" not in json.dumps(payload)


# ---------------------------------------------------------------------------
# H1: 4xx body must be scrubbed of free-text secrets
# ---------------------------------------------------------------------------


async def test_4xx_error_body_scrubs_bearer_sk_jwt_and_kv():
    """H1 regression: 4xx response bodies are scrubbed via
    `mask_free_text_secrets` before being attached to `ProviderError.details`.
    """
    leaky_body = (
        "ERROR: request failed\n"
        "Authorization: Bearer abcdefg1234567890\n"
        'Session: {"api_key": "sk-LeakyLeaky1234567", "retry": 1}\n'
        "JWT=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.SflKxwRJSMeKKF\n"
        'config = {"token": "veryveryverysecretvalue123", "ok": true}'
    )

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text=leaky_body)

    adapter = OpenAICompatibleAdapter(_provider(), http_client=_make_client(handler))
    with pytest.raises(ProviderError) as excinfo:
        await adapter.chat(_chat_req())
    payload_str = json.dumps(excinfo.value.to_payload())
    # None of the raw secret substrings may survive.
    for leaked in (
        "abcdefg1234567890",
        "sk-LeakyLeaky1234567",
        "eyJhbGciOiJIUzI1NiJ9",
        "veryveryverysecretvalue123",
    ):
        assert leaked not in payload_str, f"unscrubbed: {leaked!r} still in payload"
    # The body field is still present but truncated to <= 256 chars.
    body_field = excinfo.value.details.get("body", "")
    assert body_field
    # 256 truncate + optional ellipsis char
    assert len(body_field) <= 257


# ---------------------------------------------------------------------------
# H6: health() must return ok=False on unparseable body / missing fields
# ---------------------------------------------------------------------------


async def test_health_unparseable_html_body_returns_not_ok():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>not json</html>")

    adapter = OpenAICompatibleAdapter(_provider(), http_client=_make_client(handler))
    health = await adapter.health()
    assert health.ok is False
    assert "unparseable body" in (health.message or "")


async def test_health_empty_body_returns_not_ok():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"")

    adapter = OpenAICompatibleAdapter(_provider(), http_client=_make_client(handler))
    health = await adapter.health()
    assert health.ok is False


async def test_health_truncated_json_body_returns_not_ok():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b'{"data": [{"id":')

    adapter = OpenAICompatibleAdapter(_provider(), http_client=_make_client(handler))
    health = await adapter.health()
    assert health.ok is False


async def test_health_missing_data_field_returns_not_ok():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    adapter = OpenAICompatibleAdapter(_provider(), http_client=_make_client(handler))
    health = await adapter.health()
    assert health.ok is False
    assert "missing field" in (health.message or "")


# ---------------------------------------------------------------------------
# H7: invalid tool_call arguments must raise ProviderError, not silently
# wrap in `{_raw: …}`
# ---------------------------------------------------------------------------


async def test_tool_call_invalid_arguments_raises_provider_error():
    body = {
        "model": "gpt-test",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "fs.read_file",
                                "arguments": "{not-valid-json: true",
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    adapter = OpenAICompatibleAdapter(_provider(), http_client=_make_client(handler))
    with pytest.raises(ProviderError) as excinfo:
        await adapter.chat(_chat_req())
    details = excinfo.value.details
    assert details.get("tool_name") == "fs.read_file"
    assert "raw_truncated" in details
    assert "error_type" in details


async def test_tool_call_invalid_arguments_raw_is_scrubbed():
    """H7: raw_truncated field must also scrub secrets so error logs are
    safe to ship.
    """
    body = {
        "model": "gpt-test",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "fs.write_file",
                                "arguments": ('{"api_key": "sk-FloatingLeak123456", "path":'),
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    adapter = OpenAICompatibleAdapter(_provider(), http_client=_make_client(handler))
    with pytest.raises(ProviderError) as excinfo:
        await adapter.chat(_chat_req())
    raw = excinfo.value.details.get("raw_truncated", "")
    assert "sk-FloatingLeak123456" not in raw
    assert len(raw) <= 128
