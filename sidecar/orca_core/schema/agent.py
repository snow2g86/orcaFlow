"""AgentRole (schema.md §3.2)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ._base import OrcaModel, generate_uuid_v7

__all__ = ["AgentRole", "RoleType"]

RoleType = Literal["worker", "planner", "supervisor", "critic"]
"""AgentRole 의 기본 행동 유형."""


class AgentRole(OrcaModel):
    """재사용 가능한 에이전트 역할 템플릿 (schema.md §3.2).

    Fields mirror schema.md exactly:
    - `tools` : 허용 툴 ID 목록
    - `llm_profile_id` : 기본 LLMProfile 참조
    """

    id: str = Field(default_factory=generate_uuid_v7)
    name: str
    display_name: str | None = None
    role_type: RoleType
    system_prompt: str
    goal: str | None = None
    tools: list[str] = Field(default_factory=list)
    llm_profile_id: str
    max_steps: int = Field(default=10, ge=1, le=1000)
    temperature_override: float | None = Field(default=None, ge=0.0, le=2.0)
    tags: list[str] = Field(default_factory=list)
