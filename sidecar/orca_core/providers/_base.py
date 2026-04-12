"""Provider 공통 타입: ProviderAdapter Protocol, ChatRequest/Response/Chunk.

design.md §6.6 에 정의된 Protocol 을 Pydantic v2 모델로 구현한다.
OpenAI 함수 호출 포맷을 네이티브 표현으로 흡수해 모든 어댑터가 동일한
입출력 타입을 공유하도록 한다.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from ..schema.llm import ProviderKind

__all__ = [
    "ChatChunk",
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "ChatRole",
    "ChatToolCall",
    "ChatToolDefinition",
    "ChatUsage",
    "ProviderAdapter",
    "ProviderHealth",
]


ChatRole = Literal["system", "user", "assistant", "tool"]


class ChatToolDefinition(BaseModel):
    """LLM 에 노출할 툴 메타 (OpenAI function-call 포맷 호환)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class ChatToolCall(BaseModel):
    """모델이 요청한 tool call (OpenAI `tool_calls` 엔트리 1개)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    """단일 메시지. `role=tool` 인 경우 `tool_call_id` 필수."""

    model_config = ConfigDict(extra="forbid")

    role: ChatRole
    content: str = ""
    tool_calls: list[ChatToolCall] = Field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None  # OpenAI 'name' (legacy function-call)


class ChatRequest(BaseModel):
    """`provider.chat` 요청."""

    model_config = ConfigDict(extra="forbid")

    model: str
    messages: list[ChatMessage]
    tools: list[ChatToolDefinition] = Field(default_factory=list)
    tool_choice: Literal["auto", "none", "required"] | None = None
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    stop: list[str] | None = None
    stream: bool = False
    extra: dict[str, Any] = Field(default_factory=dict)


class ChatUsage(BaseModel):
    """토큰 사용량."""

    model_config = ConfigDict(extra="forbid")

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatResponse(BaseModel):
    """`provider.chat` 응답."""

    model_config = ConfigDict(extra="forbid")

    model: str
    message: ChatMessage
    finish_reason: Literal["stop", "length", "tool_calls", "content_filter", "error"] | None = None
    usage: ChatUsage = Field(default_factory=ChatUsage)
    raw: dict[str, Any] = Field(default_factory=dict)


class ChatChunk(BaseModel):
    """스트리밍 델타 1건."""

    model_config = ConfigDict(extra="forbid")

    delta: str = ""
    tool_calls_delta: list[ChatToolCall] = Field(default_factory=list)
    finish_reason: str | None = None


class ProviderHealth(BaseModel):
    """헬스체크 결과."""

    model_config = ConfigDict(extra="forbid")

    ok: bool
    latency_ms: int | None = None
    models: list[str] = Field(default_factory=list)
    message: str | None = None


@runtime_checkable
class ProviderAdapter(Protocol):
    """Provider 어댑터 공통 Protocol (design.md §6.6).

    구현체는 `chat`, `stream_chat`, `health` 세 메서드를 제공해야 한다.
    """

    kind: ProviderKind

    async def chat(self, req: ChatRequest) -> ChatResponse: ...

    def stream_chat(self, req: ChatRequest) -> AsyncIterator[ChatChunk]: ...

    async def health(self) -> ProviderHealth: ...
