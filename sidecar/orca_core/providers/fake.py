"""FakeProviderAdapter — 결정론적 테스트용 어댑터.

테스트에서 실제 LLM 호출은 금지(conventions.md §10). 본 어댑터는 주입된
큐에서 응답을 순서대로 꺼내 반환한다. 큐가 비면 기본 "ok" 응답 반환.
"""

from __future__ import annotations

from collections import deque
from collections.abc import AsyncIterator, Iterable

from ._base import (
    ChatChunk,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatUsage,
    ProviderHealth,
)

__all__ = ["FakeProviderAdapter"]


class FakeProviderAdapter:
    """결정론적 Provider 어댑터.

    사용 예::

        fake = FakeProviderAdapter(responses=[ChatResponse(...)])
        resp = await fake.chat(req)

    또는 편의 메서드로 간단한 텍스트 응답 큐를 쓸 수 있다::

        fake = FakeProviderAdapter()
        fake.enqueue_text("hello")
    """

    kind = "openai_compatible"

    def __init__(
        self,
        *,
        responses: Iterable[ChatResponse] | None = None,
        healthy: bool = True,
        strict: bool = True,
    ) -> None:
        """결정론적 provider adapter.

        Parameters:
            responses : 선-enqueue 할 응답 목록.
            healthy : `health()` 가 돌려줄 ok 값.
            strict : M2 regression — 큐가 비었을 때 기본 `"ok"` 응답으로
                fallback 할지 여부. 기본 True → 예외 raise. 명시적으로
                False 를 지정하면 과거 동작(조용한 fallback) 을 보존.
        """
        self._queue: deque[ChatResponse] = deque(responses or [])
        self._healthy = healthy
        self._strict = strict
        self.requests: list[ChatRequest] = []

    def enqueue(self, response: ChatResponse) -> None:
        self._queue.append(response)

    def enqueue_text(self, text: str, *, model: str = "fake-model") -> None:
        self._queue.append(
            ChatResponse(
                model=model,
                message=ChatMessage(role="assistant", content=text),
                finish_reason="stop",
                usage=ChatUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            )
        )

    async def chat(self, req: ChatRequest) -> ChatResponse:
        self.requests.append(req)
        if self._queue:
            return self._queue.popleft()
        if self._strict:
            # M2: 큐 고갈 시 조용히 `"ok"` fallback 하면 실제 LLM 응답을
            # 검증하려던 테스트가 거짓 양성이 된다. strict=True 기본값에서
            # 즉시 IndexError raise.
            raise IndexError("FakeProviderAdapter: response queue exhausted")
        return ChatResponse(
            model=req.model,
            message=ChatMessage(role="assistant", content="ok"),
            finish_reason="stop",
            usage=ChatUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        )

    async def stream_chat(self, req: ChatRequest) -> AsyncIterator[ChatChunk]:
        resp = await self.chat(req)
        yield ChatChunk(delta=resp.message.content, finish_reason=resp.finish_reason)

    async def health(self) -> ProviderHealth:
        return ProviderHealth(
            ok=self._healthy,
            latency_ms=0,
            models=["fake-model"],
            message="fake" if self._healthy else "unhealthy",
        )
