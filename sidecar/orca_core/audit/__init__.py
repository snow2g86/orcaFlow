"""Audit 레이어 — append-only 감사 로그.

schema.md §3.15, §5 #8, design.md §6.5 참조.
"""

from __future__ import annotations

from .record import build_audit_log, compute_hash
from .scrub import MASK, mask_home_path, scrub_mapping, scrub_value
from .sink import AuditDbWriter, AuditSink, AuditWriteError
from .verify import VerifyResult, verify_chain

__all__ = [
    "MASK",
    "AuditDbWriter",
    "AuditSink",
    "AuditWriteError",
    "VerifyResult",
    "build_audit_log",
    "compute_hash",
    "mask_home_path",
    "scrub_mapping",
    "scrub_value",
    "verify_chain",
]
