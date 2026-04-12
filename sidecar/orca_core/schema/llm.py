"""LLMProfile / Provider (schema.md sections 3.6-3.7)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from ._base import OrcaModel, generate_uuid_v7

__all__ = ["LLMProfile", "Provider", "ProviderKind"]

ProviderKind = Literal[
    "ollama",
    "vllm",
    "llama_cpp",
    "lm_studio",
    "tgi",
    "openai_compatible",
    "together",
    "groq",
    "fireworks",
]
"""LLM 공급자 종류 (schema.md §3.7)."""


class Provider(OrcaModel):
    """LLM 공급자 (schema.md §3.7).

    시크릿은 저장하지 않는다. `api_key_ref` 만 키체인 엔트리 ID 로 보관.
    """

    id: str = Field(default_factory=generate_uuid_v7)
    name: str
    kind: ProviderKind
    base_url: str
    api_key_ref: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    timeout_ms: int = Field(default=30_000, ge=1, le=600_000)
    health_url: str | None = None


class LLMProfile(OrcaModel):
    """LLM 파라미터 프리셋 (schema.md §3.6)."""

    id: str = Field(default_factory=generate_uuid_v7)
    name: str
    provider_id: str
    model: str
    params: dict[str, Any] = Field(default_factory=dict)
    context_window: int | None = Field(default=None, ge=1)
    is_tool_capable: bool = True
    is_planner: bool = False
    is_default: bool = False
