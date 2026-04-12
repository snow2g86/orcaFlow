"""AuditSink — append-only 감사 로그 싱크.

핵심 규칙 (schema.md §5 #8, conventions.md §7.5, design.md §6.5):
- 유일한 public 쓰기 API 는 `AuditSink.record(...)`.
- UPDATE/DELETE 경로 없음.
- DB 쓰기 + 파일 미러(`~/.orcaflow/logs/audit.log`) 가 원자적으로 실패하면
  `AuditWriteError` 를 raise. 호출자는 `fail_run` 정책을 적용한다.
- 시크릿 스크러빙은 파일 미러 경로에서 강제 적용.

Domain 순수성을 위해 DB 쓰기 경로는 Protocol (`AuditDbWriter`) 로 추상화해서
persistence 레이어가 구현체를 주입한다. 이렇게 하면 `orca_core/audit/` 는
`aiosqlite` 같은 외부 I/O 라이브러리를 import 하지 않는다.

파일 미러는 표준 라이브러리 `pathlib` + `json` 만 사용하므로 Domain 규칙
위반이 아니다 (conventions.md §6.3 은 DB·네트워크 I/O 만 금지, 감사 파일
미러는 design.md §6.5 에서 허용).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import json
from pathlib import Path
from typing import Protocol

from ..errors import OrcaError
from ..schema.audit import (
    AuditLog,
    AuditPolicyDecision,
    AuditStatus,
)
from .record import build_audit_log
from .scrub import scrub_mapping

__all__ = [
    "AuditDbWriter",
    "AuditSink",
    "AuditWriteError",
]


class AuditWriteError(OrcaError):
    """감사 로그 기록 실패. Run 을 blocked 상태로 전이시켜야 한다."""

    code = "audit.write_failed"
    http_status = 500


class AuditDbWriter(Protocol):
    """감사 DB 쓰기 경로 (persistence 레이어가 구현).

    insert 만 노출. UPDATE/DELETE 경로는 타입에 존재하지 않는다.
    """

    async def insert(self, record: AuditLog) -> None: ...


class AuditSink:
    """Append-only 감사 로그 싱크.

    Parameters:
        db_writer : DB insert 구현체 (선택 — None 이면 파일만 기록)
        log_path  : JSONL 파일 미러 경로 (`~/.orcaflow/logs/audit.log`)
        hash_prev_provider : 이전 레코드의 hash_self 를 반환하는 콜러블
                              (해시 체인 사용 시)
        lock : 동시 write 직렬화 (기본 asyncio.Lock)
    """

    def __init__(
        self,
        *,
        log_path: Path,
        db_writer: AuditDbWriter | None = None,
        hash_prev_provider: Callable[[], Awaitable[str | None]] | None = None,
    ) -> None:
        self._log_path = log_path
        self._db_writer = db_writer
        self._hash_prev_provider = hash_prev_provider
        self._lock = asyncio.Lock()
        # 파일 미러 디렉토리 준비 — 최초 record 시점에 lazy 생성
        self._parent_ready = False

    async def record(
        self,
        *,
        actor: str,
        action: str,
        target: str,
        status: AuditStatus,
        policy_decision: AuditPolicyDecision,
        run_id: str,
        run_step_id: str,
    ) -> AuditLog:
        """append-only 감사 기록. 실패 시 `AuditWriteError`."""
        async with self._lock:
            hash_prev = (
                await self._hash_prev_provider() if self._hash_prev_provider is not None else None
            )
            entry = build_audit_log(
                actor=actor,
                action=action,
                target=target,
                status=status,
                policy_decision=policy_decision,
                run_id=run_id,
                run_step_id=run_step_id,
                hash_prev=hash_prev,
            )

            # 1. DB insert (가능한 경우)
            if self._db_writer is not None:
                try:
                    await self._db_writer.insert(entry)
                except Exception as exc:
                    raise AuditWriteError(
                        "감사 DB 기록에 실패했습니다",
                        details={"cause": str(exc), "record_id": entry.id},
                    ) from exc

            # 2. 파일 미러 (JSONL append)
            try:
                self._append_jsonl(entry)
            except Exception as exc:
                raise AuditWriteError(
                    "감사 파일 미러 기록에 실패했습니다",
                    details={
                        "cause": str(exc),
                        "record_id": entry.id,
                        "path": str(self._log_path),
                    },
                ) from exc

            return entry

    def _ensure_parent(self) -> None:
        if not self._parent_ready:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            self._parent_ready = True

    def _append_jsonl(self, entry: AuditLog) -> None:
        self._ensure_parent()
        payload = entry.model_dump(mode="json")
        # 시크릿/PII 스크러빙 (conventions.md §7.4)
        payload = scrub_mapping(payload)
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        with self._log_path.open("a", encoding="utf-8") as fp:
            fp.write(line + "\n")
