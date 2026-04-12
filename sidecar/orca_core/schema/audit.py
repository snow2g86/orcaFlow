"""AuditLog (schema.md §3.15).

**Core Invariant #8**: AuditLog 는 UPDATE/DELETE 금지. 애플리케이션 레이어
(`orca_core/audit/`) 에서 insert 경로만 노출한다. 본 Pydantic 모델은
`frozen=True` 로 변경 불가능하게 고정한다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field

from ._base import OrcaModel, generate_uuid_v7, utc_now

__all__ = [
    "AuditAction",
    "AuditLog",
    "AuditPolicyDecision",
    "AuditStatus",
]

AuditStatus = Literal["success", "failed", "blocked", "approved"]
AuditPolicyDecision = Literal["allow", "denied", "approved", "dry_run_only"]
AuditAction = str  # free-form e.g. "fs.delete", "shell.exec"


class AuditLog(OrcaModel):
    """파괴적/민감 작업의 불변 감사 기록 (schema.md §3.15)."""

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
        frozen=True,  # 불변 객체 — 생성 후 필드 수정 금지
    )

    id: str = Field(default_factory=generate_uuid_v7)
    at: datetime = Field(default_factory=utc_now)
    actor: str
    action: AuditAction
    target: str
    status: AuditStatus
    policy_decision: AuditPolicyDecision
    run_id: str
    run_step_id: str
    hash_prev: str | None = None
    hash_self: str | None = None
