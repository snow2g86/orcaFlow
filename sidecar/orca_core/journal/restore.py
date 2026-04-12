"""Journal 복구 엔진 (design.md §6.4).

현재 M2 범위에서는 파일/클립보드 되돌리기의 **결정 로직 + 체크섬 검증**만
구현한다. 실제 파일 쓰기/클립보드 조작은 tools 레이어(M3+)에서 담당한다.
Domain 순수성 유지.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..schema.journal import JournalEntry
from .store import JournalStore

__all__ = ["RestorePlan", "RestoreStatus", "plan_restore"]

RestoreStatus = str  # "ready" | "conflict" | "not_reversible" | "no_before"


@dataclass(frozen=True, slots=True)
class RestorePlan:
    """복구 계획.

    - `status`:
      * `ready` — before 페이로드가 있고 체크섬 일치 (실행 가능)
      * `conflict` — after 가 사용자가 제공한 현재 상태와 다르면 충돌
      * `not_reversible` — reversible=False
      * `no_before` — before 페이로드가 없음
    - `target_payload`: 복구할 payload (파일 내용 등)
    - `reason`: 사람 친화 설명
    """

    status: RestoreStatus
    entry_id: str
    target_payload: dict[str, Any] | None
    reason: str


def plan_restore(
    store: JournalStore,
    entry: JournalEntry,
    *,
    current_state: dict[str, Any] | None = None,
) -> RestorePlan:
    """JournalEntry 로부터 복구 계획을 생성한다.

    `current_state` 가 주어지면 entry.after 와 체크섬 비교해 충돌을 판정.
    충돌이 있으면 복구를 허용하지 않는다 (design.md §6.4).
    """
    if not entry.reversible:
        return RestorePlan(
            status="not_reversible",
            entry_id=entry.id,
            target_payload=None,
            reason="entry is not reversible",
        )

    before_payload: dict[str, Any] | None
    if entry.before is not None:
        before_payload = entry.before
    elif entry.before_storage_ref is not None:
        before_payload = store.load_payload(entry.before_storage_ref)
    else:
        return RestorePlan(
            status="no_before",
            entry_id=entry.id,
            target_payload=None,
            reason="no before payload or before_storage_ref",
        )

    # Resolve recorded after state (may be inline or spilled).
    recorded_after: dict[str, Any] | None
    if entry.after is not None:
        recorded_after = entry.after
    elif entry.after_storage_ref is not None:
        recorded_after = store.load_payload(entry.after_storage_ref)
    else:
        recorded_after = None

    if current_state is not None and recorded_after is not None:
        expected = JournalStore.checksum(recorded_after)
        actual = JournalStore.checksum(current_state)
        if expected != actual:
            return RestorePlan(
                status="conflict",
                entry_id=entry.id,
                target_payload=None,
                reason="current state differs from recorded 'after' (checksum mismatch)",
            )

    return RestorePlan(
        status="ready",
        entry_id=entry.id,
        target_payload=before_payload,
        reason="ready to restore",
    )
