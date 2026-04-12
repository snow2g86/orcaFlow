"""AuditRecord 빌더 — 해시 체인 계산 포함."""

from __future__ import annotations

import hashlib

from ..schema._base import generate_uuid_v7, utc_now
from ..schema.audit import (
    AuditLog,
    AuditPolicyDecision,
    AuditStatus,
)

__all__ = ["build_audit_log", "compute_hash"]


def compute_hash(
    *,
    record_id: str,
    at_iso: str,
    actor: str,
    action: str,
    target: str,
    status: str,
    hash_prev: str | None,
) -> str:
    """`sha256(id || at || actor || action || target || status || hash_prev)`.

    design.md §3.1.4 에 정의된 감사 해시 체인.
    """
    buf = "|".join(
        [
            record_id,
            at_iso,
            actor,
            action,
            target,
            status,
            hash_prev or "",
        ]
    ).encode("utf-8")
    return hashlib.sha256(buf).hexdigest()


def build_audit_log(
    *,
    actor: str,
    action: str,
    target: str,
    status: AuditStatus,
    policy_decision: AuditPolicyDecision,
    run_id: str,
    run_step_id: str,
    hash_prev: str | None = None,
) -> AuditLog:
    """AuditLog 1건을 빌드한다 (해시 자동 계산).

    반환되는 모델은 `frozen=True` 이므로 이후 수정 불가.
    """
    rec_id = generate_uuid_v7()
    at = utc_now()
    at_iso = at.isoformat()
    hash_self = compute_hash(
        record_id=rec_id,
        at_iso=at_iso,
        actor=actor,
        action=action,
        target=target,
        status=status,
        hash_prev=hash_prev,
    )
    return AuditLog(
        id=rec_id,
        at=at,
        actor=actor,
        action=action,
        target=target,
        status=status,
        policy_decision=policy_decision,
        run_id=run_id,
        run_step_id=run_step_id,
        hash_prev=hash_prev,
        hash_self=hash_self,
    )
