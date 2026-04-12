"""OllamaAdapter — /api/tags 헬스 override 테스트."""

from __future__ import annotations

import httpx

from orca_core.providers import ChatMessage, ChatRequest, OllamaAdapter
from orca_core.schema import Provider


def _ollama_provider() -> Provider:
    return Provider(
        name="fake-ollama",
        kind="ollama",
        base_url="http://localhost:11434",
        timeout_ms=5_000,
    )


def _make_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_health_hits_api_tags_and_parses_models():
    captured: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        assert req.url.path == "/api/tags"
        return httpx.Response(
            200,
            json={
                "models": [
                    {"name": "qwen2.5:14b"},
                    {"name": "llama3:8b"},
                ]
            },
        )

    adapter = OllamaAdapter(_ollama_provider(), http_client=_make_client(handler))
    health = await adapter.health()
    assert health.ok is True
    assert set(health.models) == {"qwen2.5:14b", "llama3:8b"}
    assert captured[0].url.path == "/api/tags"


async def test_health_reports_unhealthy_on_transport_error():
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=req)

    adapter = OllamaAdapter(_ollama_provider(), http_client=_make_client(handler))
    health = await adapter.health()
    assert health.ok is False


async def test_health_reports_http_error_status():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="broken")

    adapter = OllamaAdapter(_ollama_provider(), http_client=_make_client(handler))
    health = await adapter.health()
    assert health.ok is False
    assert "500" in (health.message or "")


async def test_health_unparseable_body_returns_not_ok():
    """H6 regression: Ollama /api/tags returning non-JSON must flip ok=False
    instead of silently falling back to `models=[]`.
    """

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json")

    adapter = OllamaAdapter(_ollama_provider(), http_client=_make_client(handler))
    health = await adapter.health()
    assert health.ok is False
    assert "unparseable body" in (health.message or "")


async def test_health_missing_models_field_returns_not_ok():
    """H6 regression: missing the `models` field must flip ok=False."""

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": 1})

    adapter = OllamaAdapter(_ollama_provider(), http_client=_make_client(handler))
    health = await adapter.health()
    assert health.ok is False
    assert "missing field" in (health.message or "")


async def test_chat_reuses_openai_compatible_path():
    """Ollama's `/v1/chat/completions` is OpenAI-compatible — parent impl works."""

    captured: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        return httpx.Response(
            200,
            json={
                "model": "qwen2.5:14b",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "pong"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )

    adapter = OllamaAdapter(_ollama_provider(), http_client=_make_client(handler))
    resp = await adapter.chat(
        ChatRequest(
            model="qwen2.5:14b",
            messages=[ChatMessage(role="user", content="ping")],
        )
    )
    assert resp.message.content == "pong"
    assert captured[0].url.path == "/v1/chat/completions"
