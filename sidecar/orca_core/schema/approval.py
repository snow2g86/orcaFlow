"""ApprovalRequest (schema.md §3.14)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from ._base import OrcaModel, generate_uuid_v7

__all__ = ["ApprovalRequest", "ApprovalState"]

ApprovalState = Literal["pending", "approved", "rejected", "expired"]


class ApprovalRequest(OrcaModel):
    """민감/파괴적 작업에 대한 사용자 승인 요청 (schema.md §3.14)."""

    id: str = Field(default_factory=generate_uuid_v7)
    run_step_id: str
    tool_call_id: str | None = None
    reason: str
    diff_preview: dict[str, Any] | None = None
    state: ApprovalState = "pending"
    decided_at: datetime | None = None
    decided_by: str | None = None
    ttl_seconds: int = Field(default=300, ge=1)
