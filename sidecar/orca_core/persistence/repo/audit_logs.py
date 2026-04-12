"""AuditLog repository — **append-only**.

Core invariant (schema.md §5 #8): AuditLog 는 UPDATE/DELETE 금지.
본 repository 는 insert + read 경로만 노출한다. DELETE/UPDATE 메서드를
타입 레벨에서 제공하지 않는다.

`AuditDbWriter` Protocol (`orca_core/audit/sink.py`) 을 구현해서 Audit 레이어가
주입받도록 설계한다.
"""

from __future__ import annotations

from datetime import datetime

import aiosqlite

from ...audit.sink import AuditDbWriter
from ...errors import OrcaError
from ...schema.audit import AuditLog
from ._base import BaseRepository

__all__ = ["AuditIntegrityError", "AuditLogsRepository"]


class AuditIntegrityError(OrcaError):
    """Audit 체인 무결성 위반 (빈 hash_self 등)."""

    code = "audit.chain_corrupted"
    http_status = 500


class AuditLogsRepository(BaseRepository, AuditDbWriter):
    """Append-only audit log repository.

    NOTE: update/delete 메서드는 의도적으로 존재하지 않는다. CI 의
    import-linter 및 코드 리뷰가 이 제약을 강제한다.
    """

    async def insert(
        self,
        record: AuditLog,
        *,
        conn: aiosqlite.Connection | None = None,
    ) -> None:
        query = """
        INSERT INTO audit_logs (id, at, actor, action, target, status, policy_decision,
                                run_id, run_step_id, hash_prev, hash_self)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        params = (
            record.id,
            record.at.isoformat(),
            record.actor,
            record.action,
            record.target,
            record.status,
            record.policy_decision,
            record.run_id,
            record.run_step_id,
            record.hash_prev,
            record.hash_self,
        )
        await self._execute(query, params, conn=conn)

    async def get(
        self, record_id: str, *, conn: aiosqlite.Connection | None = None
    ) -> AuditLog | None:
        row = await self._fetch_one(
            "SELECT * FROM audit_logs WHERE id = ?;", (record_id,), conn=conn
        )
        return _row_to_audit(row) if row else None

    async def list_for_run(
        self, run_id: str, *, conn: aiosqlite.Connection | None = None
    ) -> list[AuditLog]:
        rows = await self._fetch_all(
            "SELECT * FROM audit_logs WHERE run_id = ? ORDER BY at, id;",
            (run_id,),
            conn=conn,
        )
        return [_row_to_audit(r) for r in rows]

    async def latest_hash(self, *, conn: aiosqlite.Connection | None = None) -> str | None:
        """가장 최근 감사 레코드의 hash_self (체인 연속성용).

        hash_self 가 빈 문자열이면 감사 체인이 손상된 상태이므로
        `AuditIntegrityError` 를 raise. None 으로 강등하면 다음 레코드가
        `hash_prev=None` 으로 저장돼 체인 연결이 끊긴다.
        """
        row = await self._fetch_one(
            "SELECT id, hash_self FROM audit_logs ORDER BY at DESC, id DESC LIMIT 1;",
            conn=conn,
        )
        if row is None:
            return None
        hash_self = row["hash_self"]
        if hash_self is None or str(hash_self) == "":
            raise AuditIntegrityError(
                f"audit chain corrupted: empty hash_self at id={row['id']}",
                details={"record_id": str(row["id"])},
            )
        return str(hash_self)


def _row_to_audit(row: aiosqlite.Row) -> AuditLog:
    return AuditLog(
        id=str(row["id"]),
        at=datetime.fromisoformat(str(row["at"])),
        actor=str(row["actor"]),
        action=str(row["action"]),
        target=str(row["target"]),
        status=str(row["status"]),  # type: ignore[arg-type]
        policy_decision=str(row["policy_decision"]),  # type: ignore[arg-type]
        run_id=str(row["run_id"]),
        run_step_id=str(row["run_step_id"]),
        hash_prev=(str(row["hash_prev"]) if row["hash_prev"] else None),
        hash_self=(str(row["hash_self"]) if row["hash_self"] else None),
    )
