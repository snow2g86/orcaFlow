"""Provider 어댑터 패키지 (M3).

design.md §6.6 에 정의된 `ProviderAdapter` Protocol 과 구현체들을 제공한다.
모든 공급자는 동일 입출력 타입(`ChatRequest`/`ChatResponse`)을 공유하며,
시크릿은 `ProviderSecretStore` 경유로만 조회한다.
"""

from __future__ import annotations

from ._base import (
    ChatChunk,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatRole,
    ChatToolCall,
    ChatToolDefinition,
    ChatUsage,
    ProviderAdapter,
    ProviderHealth,
)
from .errors import (
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderToolNotSupportedError,
    ProviderUnavailableError,
)
from .fake import FakeProviderAdapter
from .ollama import OllamaAdapter
from .openai_compatible import OpenAICompatibleAdapter
from .registry import ProviderRegistry, ProviderRegistryEntry
from .secret_store import (
    InMemorySecretStore,
    ProviderSecretNotFoundError,
    ProviderSecretStore,
)

__all__ = [
    "ChatChunk",
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "ChatRole",
    "ChatToolCall",
    "ChatToolDefinition",
    "ChatUsage",
    "FakeProviderAdapter",
    "InMemorySecretStore",
    "OllamaAdapter",
    "OpenAICompatibleAdapter",
    "ProviderAdapter",
    "ProviderAuthError",
    "ProviderError",
    "ProviderHealth",
    "ProviderRateLimitedError",
    "ProviderRegistry",
    "ProviderRegistryEntry",
    "ProviderSecretNotFoundError",
    "ProviderSecretStore",
    "ProviderTimeoutError",
    "ProviderToolNotSupportedError",
    "ProviderUnavailableError",
]
