"""JournalEntry (schema.md §3.16)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from ._base import OrcaModel, generate_uuid_v7, utc_now

__all__ = ["JournalEntry", "JournalKind"]

JournalKind = Literal[
    "fs_write",
    "fs_move",
    "fs_delete_to_trash",
    "clipboard_write",
    "custom",
]


class JournalEntry(OrcaModel):
    """되돌리기 가능한 변경 이력 (schema.md §3.16).

    **Invariant (schema.md §5 #2)**: reversible=True 인 툴 콜은 실행 전
    JournalEntry.before 를 반드시 기록한다. 기록 실패 시 실행 중단.

    `before_storage_ref` 와 `after_storage_ref` 는 각각 before/after payload
    가 spill threshold 를 넘었을 때의 파일 경로이다. 과거에는 단일
    `storage_ref` 를 공유했으나, record_after 가 before 경로를 덮어써서
    복구 시점에 파괴적 변경이 재적용되는 버그가 있었다 (1.1 에서 분리).
    """

    id: str = Field(default_factory=generate_uuid_v7)
    run_step_id: str
    tool_call_id: str
    kind: JournalKind
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    before_storage_ref: str | None = None
    after_storage_ref: str | None = None
    reversible: bool
    restored_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def _validate_before_present_when_reversible(self) -> JournalEntry:
        if self.reversible and self.before is None and self.before_storage_ref is None:
            raise ValueError(
                "JournalEntry with reversible=True must have either 'before' payload "
                "or 'before_storage_ref' (invariant schema.md §5 #2)"
            )
        return self
