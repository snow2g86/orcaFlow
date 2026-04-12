"""Run / RunStep / ToolCall / Message / ConversationTurn.

(schema.md sections 3.10-3.14, 3.17)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from ._base import OrcaModel, generate_uuid_v7, utc_now

__all__ = [
    "ConversationTurn",
    "Message",
    "MessageRole",
    "Run",
    "RunStatus",
    "RunStep",
    "RunStepKind",
    "RunStepStatus",
    "RunTrigger",
    "ToolCall",
    "ToolCallDecision",
]

RunTrigger = Literal["chat", "manual", "scheduled", "api"]
RunStatus = Literal[
    "pending",
    "running",
    "awaiting_approval",
    "succeeded",
    "failed",
    "cancelled",
]
RunStepKind = Literal["llm_call", "tool_call", "route", "approval", "dry_run"]
RunStepStatus = Literal["queued", "running", "succeeded", "failed", "blocked"]
ToolCallDecision = Literal["allow", "denied", "approved", "dry_run_only"]
MessageRole = Literal["system", "user", "assistant", "tool"]


class Run(OrcaModel):
    """워크플로우 1회 실행 인스턴스 (schema.md §3.10).

    불변 규칙 (schema.md §5 #3):
        `workflow_snapshot` 은 실행 시점 YAML 을 그대로 보관해
        이후 워크플로우 수정이 있어도 재현 가능해야 한다.
    """

    id: str = Field(default_factory=generate_uuid_v7)
    workflow_id: str
    workflow_snapshot: str = Field(..., min_length=1)
    trigger: RunTrigger
    status: RunStatus
    started_at: datetime = Field(default_factory=utc_now)
    ended_at: datetime | None = None
    stats: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] | None = None
    parent_run_id: str | None = None


class RunStep(OrcaModel):
    """Run 내 단일 스텝 (schema.md §3.11)."""

    id: str = Field(default_factory=generate_uuid_v7)
    run_id: str
    parent_step_id: str | None = None
    node_id: str | None = None
    kind: RunStepKind
    payload: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    status: RunStepStatus
    started_at: datetime = Field(default_factory=utc_now)
    ended_at: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    tokens_in: int | None = Field(default=None, ge=0)
    tokens_out: int | None = Field(default=None, ge=0)


class ToolCall(OrcaModel):
    """툴 호출 기록 (schema.md §3.12)."""

    id: str = Field(default_factory=generate_uuid_v7)
    run_step_id: str
    tool_id: str
    args: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    dry_run: bool = False
    policy_decision: ToolCallDecision
    audit_log_id: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)


class Message(OrcaModel):
    """에이전트/사용자 메시지 (schema.md §3.13)."""

    id: str = Field(default_factory=generate_uuid_v7)
    run_id: str
    node_id: str | None = None
    role: MessageRole
    content: str
    tool_call_id: str | None = None
    tokens: int | None = Field(default=None, ge=0)
    created_at: datetime = Field(default_factory=utc_now)


class ConversationTurn(OrcaModel):
    """채팅 턴 (schema.md §3.17)."""

    id: str = Field(default_factory=generate_uuid_v7)
    session_id: str
    user_text: str
    planner_trace: dict[str, Any] | None = None
    resolved_workflow_id: str | None = None
    run_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
