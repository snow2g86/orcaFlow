"""JournalStore — 변경 저널 기록/조회 (design.md §6.4).

핵심 규칙 (schema.md §5 #2):
- `record_before` 실패 시 툴 실행 차단 (design.md §6.4).
- 대용량(>256KB) payload 는 파일로 spill, DB 에는 `before_storage_ref` /
  `after_storage_ref` 에 각각 경로만 저장.
- 체크섬 검증: 복구 시점에 after 가 여전히 원래 상태인지 확인.

Domain 순수성: DB 쓰기는 `JournalDbWriter` Protocol 로 persistence 레이어에
위임한다. 파일 spill 만 본 레이어에서 직접 수행한다 (design.md §6.4 허용).
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any, Protocol

from ..errors import OrcaError
from ..schema._base import generate_uuid_v7
from ..schema.journal import JournalEntry, JournalKind

__all__ = [
    "SPILL_THRESHOLD_BYTES",
    "JournalDbWriter",
    "JournalStore",
    "JournalWriteError",
]

SPILL_THRESHOLD_BYTES = 256 * 1024  # 256 KiB
"""이 크기를 넘는 before/after payload 는 파일로 spill."""


class JournalWriteError(OrcaError):
    code = "journal.write_failed"
    http_status = 500


class JournalDbWriter(Protocol):
    """Journal DB 쓰기 경로 (persistence 레이어가 구현)."""

    async def insert(self, entry: JournalEntry) -> None: ...

    async def update_after(
        self,
        entry_id: str,
        *,
        after: dict[str, Any] | None,
        after_storage_ref: str | None,
    ) -> None: ...

    async def mark_restored(self, entry_id: str) -> None: ...

    async def list_for_run(self, run_id: str) -> Iterable[JournalEntry]: ...


class JournalStore:
    """변경 저널 저장소.

    Parameters:
        base_dir : `~/.orcaflow/journal/` (spill 파일 루트)
        db_writer : DB 쓰기 구현 (선택)
    """

    def __init__(
        self,
        *,
        base_dir: Path,
        db_writer: JournalDbWriter | None = None,
    ) -> None:
        self._base_dir = base_dir
        self._db_writer = db_writer
        self._lock = asyncio.Lock()

    async def record_before(
        self,
        *,
        run_id: str,
        run_step_id: str,
        tool_call_id: str,
        kind: JournalKind,
        before: dict[str, Any] | None,
        reversible: bool,
    ) -> JournalEntry:
        """툴 실행 전 before 스냅샷 기록. 실패 시 `JournalWriteError`.

        `run_id` 는 필수. 누락 시 `JournalWriteError` 를 raise 해 spill 이
        엉뚱한 디렉토리로 흘러가지 않도록 한다.
        """
        if not run_id:
            raise JournalWriteError("run_id required for journal entry")
        async with self._lock:
            entry_id = generate_uuid_v7()
            stored_before, before_ref = self._maybe_spill(
                run_id=run_id, entry_id=entry_id, suffix="before", payload=before
            )
            entry = JournalEntry(
                id=entry_id,
                run_step_id=run_step_id,
                tool_call_id=tool_call_id,
                kind=kind,
                before=stored_before,
                after=None,
                before_storage_ref=before_ref,
                after_storage_ref=None,
                reversible=reversible,
            )

            if self._db_writer is not None:
                try:
                    await self._db_writer.insert(entry)
                except Exception as exc:
                    raise JournalWriteError(
                        "Journal 기록(before)에 실패했습니다",
                        details={"cause": str(exc), "entry_id": entry.id},
                    ) from exc

            return entry

    async def record_after(
        self,
        entry: JournalEntry,
        *,
        run_id: str,
        after: dict[str, Any] | None,
    ) -> JournalEntry:
        """after 스냅샷 기록 (in-place 업데이트 성격).

        after payload 는 before 와 **별도** 파일 경로에 저장된다. 이전 버전
        에서는 before_storage_ref 를 덮어써서 복구가 깨지는 버그가 있었다.
        반환값은 새 JournalEntry (immutable copy).
        """
        if not run_id:
            raise JournalWriteError("run_id required for journal entry")
        async with self._lock:
            stored_after, after_ref = self._maybe_spill(
                run_id=run_id, entry_id=entry.id, suffix="after", payload=after
            )

            new_entry = entry.model_copy(
                update={
                    "after": stored_after,
                    "after_storage_ref": after_ref,
                }
            )

            if self._db_writer is not None:
                try:
                    await self._db_writer.update_after(
                        entry_id=new_entry.id,
                        after=stored_after,
                        after_storage_ref=after_ref,
                    )
                except Exception as exc:
                    raise JournalWriteError(
                        "Journal 기록(after)에 실패했습니다",
                        details={"cause": str(exc), "entry_id": new_entry.id},
                    ) from exc
            return new_entry

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _run_dir(self, run_id: str) -> Path:
        return self._base_dir / run_id

    def _spill_path(self, run_id: str, entry_id: str, suffix: str) -> Path:
        return self._run_dir(run_id) / f"{entry_id}.{suffix}.bin"

    @staticmethod
    def _encoded_size(payload: dict[str, Any]) -> int:
        return len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def _maybe_spill(
        self,
        *,
        run_id: str,
        entry_id: str,
        suffix: str,
        payload: dict[str, Any] | None,
    ) -> tuple[dict[str, Any] | None, str | None]:
        if payload is None:
            return None, None
        size = self._encoded_size(payload)
        if size <= SPILL_THRESHOLD_BYTES:
            return payload, None
        ref = self._write_spill_file(
            run_id=run_id, entry_id=entry_id, suffix=suffix, payload=payload
        )
        return None, ref

    def _write_spill_file(
        self,
        *,
        run_id: str,
        entry_id: str,
        suffix: str,
        payload: dict[str, Any],
    ) -> str:
        path = self._spill_path(run_id, entry_id, suffix)
        path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        with gzip.open(path, "wb") as fp:
            fp.write(encoded)
        return str(path)

    # ------------------------------------------------------------------
    # Public helpers for restore flow
    # ------------------------------------------------------------------

    def load_payload(self, storage_ref: str) -> dict[str, Any]:
        """spill 파일에서 payload 를 역직렬화해 반환."""
        path = Path(storage_ref)
        with gzip.open(path, "rb") as fp:
            data = fp.read()
        loaded: dict[str, Any] = json.loads(data.decode("utf-8"))
        return loaded

    @staticmethod
    def checksum(payload: dict[str, Any]) -> str:
        """복구 검증용 SHA256 체크섬 (정렬된 키 기반)."""
        data = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(data).hexdigest()
