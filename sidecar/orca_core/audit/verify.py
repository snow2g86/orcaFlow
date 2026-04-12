"""AuditLog 해시 체인 검증 유틸."""

from __future__ import annotations

from collections.abc import Iterable

from ..schema.audit import AuditLog
from .record import compute_hash

__all__ = ["VerifyResult", "verify_chain"]


class VerifyResult:
    """체인 검증 결과.

    - `ok` : 전체 체인이 유효한지
    - `broken_at` : 불일치 발견 시 해당 AuditLog.id (없으면 None)
    - `reason` : 사람 친화 설명
    """

    __slots__ = ("broken_at", "ok", "reason")

    def __init__(self, *, ok: bool, broken_at: str | None = None, reason: str = "") -> None:
        self.ok = ok
        self.broken_at = broken_at
        self.reason = reason

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"VerifyResult(ok={self.ok}, broken_at={self.broken_at!r}, reason={self.reason!r})"


def verify_chain(records: Iterable[AuditLog]) -> VerifyResult:
    """순서대로 정렬된 AuditLog 리스트에 대해 해시 체인을 검증한다.

    첫 레코드의 `hash_prev` 는 `None` 이어야 하고, 이후 레코드는 이전 레코드의
    `hash_self` 와 일치해야 한다. `hash_self` 값도 재계산해 비교한다.
    """
    previous: AuditLog | None = None
    for rec in records:
        if rec.hash_self is None:
            return VerifyResult(
                ok=False,
                broken_at=rec.id,
                reason="hash_self is missing",
            )

        expected_prev = previous.hash_self if previous is not None else None
        if rec.hash_prev != expected_prev:
            return VerifyResult(
                ok=False,
                broken_at=rec.id,
                reason=(f"hash_prev mismatch: expected {expected_prev!r}, got {rec.hash_prev!r}"),
            )

        recomputed = compute_hash(
            record_id=rec.id,
            at_iso=rec.at.isoformat(),
            actor=rec.actor,
            action=rec.action,
            target=rec.target,
            status=rec.status,
            hash_prev=rec.hash_prev,
        )
        if recomputed != rec.hash_self:
            return VerifyResult(
                ok=False,
                broken_at=rec.id,
                reason="hash_self does not match recomputed digest",
            )
        previous = rec

    return VerifyResult(ok=True, reason="chain valid")
