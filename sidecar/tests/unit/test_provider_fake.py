"""FakeProviderAdapter 단독 테스트."""

from __future__ import annotations

import pytest

from orca_core.providers import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatUsage,
    FakeProviderAdapter,
)


def _req(text: str) -> ChatRequest:
    return ChatRequest(
        model="fake",
        messages=[ChatMessage(role="user", content=text)],
    )


async def test_fake_returns_enqueued_response():
    fake = FakeProviderAdapter()
    fake.enqueue(
        ChatResponse(
            model="fake-1",
            message=ChatMessage(role="assistant", content="hello"),
            finish_reason="stop",
            usage=ChatUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )
    )
    resp = await fake.chat(_req("hi"))
    assert resp.message.content == "hello"
    assert resp.usage.total_tokens == 2
    assert len(fake.requests) == 1


async def test_fake_text_helper():
    fake = FakeProviderAdapter()
    fake.enqueue_text("quick reply")
    resp = await fake.chat(_req("hi"))
    assert resp.message.content == "quick reply"


async def test_fake_default_when_empty_queue():
    # M2 regression: strict=False to explicitly opt into the legacy "ok"
    # fallback behaviour. strict=True (default) raises IndexError instead.
    fake = FakeProviderAdapter(strict=False)
    resp = await fake.chat(_req("hi"))
    assert resp.message.content == "ok"
    assert resp.finish_reason == "stop"


async def test_fake_strict_mode_raises_on_empty_queue():
    """M2 regression: strict=True (default) raises when queue is empty."""
    fake = FakeProviderAdapter()
    with pytest.raises(IndexError, match="queue exhausted"):
        await fake.chat(_req("hi"))


async def test_fake_stream_yields_one_chunk():
    fake = FakeProviderAdapter()
    fake.enqueue_text("streamed")
    chunks = [c async for c in fake.stream_chat(_req("hi"))]
    assert len(chunks) == 1
    assert chunks[0].delta == "streamed"


async def test_fake_health_ok_by_default():
    fake = FakeProviderAdapter()
    health = await fake.health()
    assert health.ok is True
    assert health.models == ["fake-model"]


async def test_fake_health_unhealthy_flag():
    fake = FakeProviderAdapter(healthy=False)
    health = await fake.health()
    assert health.ok is False
    assert health.message == "unhealthy"


async def test_fake_records_requests_order():
    # strict=False: we only care about request ordering, not the queued
    # response payload itself.
    fake = FakeProviderAdapter(strict=False)
    await fake.chat(_req("first"))
    await fake.chat(_req("second"))
    assert fake.requests[0].messages[0].content == "first"
    assert fake.requests[1].messages[0].content == "second"


async def test_fake_registered_in_registry_and_health_check_all():
    from orca_core.providers import ProviderRegistry
    from orca_core.schema import Provider

    fake = FakeProviderAdapter()
    provider = Provider(name="fake", kind="openai_compatible", base_url="http://x")
    registry = ProviderRegistry()
    registry.register(provider, fake)
    assert provider.id in registry
    results = await registry.health_check_all()
    assert results[provider.id].ok


async def test_registry_raises_when_unknown():
    from orca_core.errors import NotFoundError
    from orca_core.providers import ProviderRegistry

    registry = ProviderRegistry()
    with pytest.raises(NotFoundError):
        registry.get("does-not-exist")
