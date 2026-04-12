"""ApprovalRequest repository."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import aiosqlite

from ...schema.approval import ApprovalRequest
from ._base import BaseRepository, json_dumps, json_loads_or_none

__all__ = ["ApprovalsRepository"]


class ApprovalsRepository(BaseRepository):
    async def insert(
        self,
        req: ApprovalRequest,
        *,
        conn: aiosqlite.Connection | None = None,
    ) -> None:
        query = """
        INSERT INTO approval_requests (id, run_step_id, tool_call_id, reason,
                                       diff_preview_json, state, decided_at, decided_by,
                                       ttl_seconds)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        params: tuple[Any, ...] = (
            req.id,
            req.run_step_id,
            req.tool_call_id,
            req.reason,
            json_dumps(req.diff_preview) if req.diff_preview else None,
            req.state,
            req.decided_at.isoformat() if req.decided_at else None,
            req.decided_by,
            req.ttl_seconds,
        )
        await self._execute(query, params, conn=conn)

    async def update_state(
        self,
        req_id: str,
        *,
        state: str,
        decided_at: datetime,
        decided_by: str,
        conn: aiosqlite.Connection | None = None,
    ) -> None:
        """Pending 상태의 request 만 state 전이 가능.

        race-free: WHERE 에 `state='pending'` 포함. 이미 결정된(또는 존재하지
        않는) request 는 rowcount=0 이 되어 `RepositoryError` 를 raise.
        """
        await self._execute_write(
            """
            UPDATE approval_requests
            SET state = ?, decided_at = ?, decided_by = ?
            WHERE id = ? AND state = 'pending';
            """,
            (state, decided_at.isoformat(), decided_by, req_id),
            expected_rows=1,
            error_message=(f"approval_requests.update_state: no pending row for id={req_id}"),
            conn=conn,
        )

    async def get(
        self,
        req_id: str,
        *,
        conn: aiosqlite.Connection | None = None,
    ) -> ApprovalRequest | None:
        row = await self._fetch_one(
            "SELECT * FROM approval_requests WHERE id = ?;", (req_id,), conn=conn
        )
        return _row_to_approval(row) if row else None


def _row_to_approval(row: aiosqlite.Row) -> ApprovalRequest:
    return ApprovalRequest(
        id=str(row["id"]),
        run_step_id=str(row["run_step_id"]),
        tool_call_id=(str(row["tool_call_id"]) if row["tool_call_id"] else None),
        reason=str(row["reason"]),
        diff_preview=json_loads_or_none(row["diff_preview_json"]),
        state=str(row["state"]),  # type: ignore[arg-type]
        decided_at=(datetime.fromisoformat(str(row["decided_at"])) if row["decided_at"] else None),
        decided_by=(str(row["decided_by"]) if row["decided_by"] else None),
        ttl_seconds=int(row["ttl_seconds"]) if row["ttl_seconds"] is not None else 300,
    )
