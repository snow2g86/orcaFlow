"""ToolCall repository."""

from __future__ import annotations

from typing import Any

import aiosqlite

from ...schema.run import ToolCall
from ._base import BaseRepository, json_dumps, json_loads_or_none

__all__ = ["ToolCallsRepository"]


class ToolCallsRepository(BaseRepository):
    async def insert(
        self,
        call: ToolCall,
        *,
        conn: aiosqlite.Connection | None = None,
    ) -> None:
        query = """
        INSERT INTO tool_calls (id, run_step_id, tool_id, args_json, result_json,
                                error_json, dry_run, policy_decision, audit_log_id,
                                duration_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        params: tuple[Any, ...] = (
            call.id,
            call.run_step_id,
            call.tool_id,
            json_dumps(call.args),
            json_dumps(call.result) if call.result is not None else None,
            json_dumps(call.error) if call.error is not None else None,
            int(call.dry_run),
            call.policy_decision,
            call.audit_log_id,
            call.duration_ms,
        )
        await self._execute(query, params, conn=conn)

    async def update_result(
        self,
        tool_call_id: str,
        *,
        result_json: dict[str, Any] | None,
        error_json: dict[str, Any] | None,
        duration_ms: int | None,
        audit_log_id: str | None,
        policy_decision: str | None = None,
        conn: aiosqlite.Connection | None = None,
    ) -> None:
        """H3 regression — Step 6 이후 back-fill 경로.

        preliminary insert 로 기록된 행의 결과/오류/소요시간/audit_log_id 를
        갱신한다. rowcount 가 1 이 아니면 `RepositoryError`.
        """
        if policy_decision is not None:
            query = """
            UPDATE tool_calls
               SET result_json = ?,
                   error_json = ?,
                   duration_ms = ?,
                   audit_log_id = ?,
                   policy_decision = ?
             WHERE id = ?;
            """
            params: tuple[Any, ...] = (
                json_dumps(result_json) if result_json is not None else None,
                json_dumps(error_json) if error_json is not None else None,
                duration_ms,
                audit_log_id,
                policy_decision,
                tool_call_id,
            )
        else:
            query = """
            UPDATE tool_calls
               SET result_json = ?,
                   error_json = ?,
                   duration_ms = ?,
                   audit_log_id = ?
             WHERE id = ?;
            """
            params = (
                json_dumps(result_json) if result_json is not None else None,
                json_dumps(error_json) if error_json is not None else None,
                duration_ms,
                audit_log_id,
                tool_call_id,
            )
        await self._execute_write(
            query,
            params,
            expected_rows=1,
            error_message="tool_calls.update_result: row not found",
            conn=conn,
        )

    async def get(
        self, call_id: str, *, conn: aiosqlite.Connection | None = None
    ) -> ToolCall | None:
        row = await self._fetch_one("SELECT * FROM tool_calls WHERE id = ?;", (call_id,), conn=conn)
        return _row_to_call(row) if row else None

    async def list_for_step(
        self, run_step_id: str, *, conn: aiosqlite.Connection | None = None
    ) -> list[ToolCall]:
        rows = await self._fetch_all(
            "SELECT * FROM tool_calls WHERE run_step_id = ?;", (run_step_id,), conn=conn
        )
        return [_row_to_call(r) for r in rows]


def _row_to_call(row: aiosqlite.Row) -> ToolCall:
    return ToolCall(
        id=str(row["id"]),
        run_step_id=str(row["run_step_id"]),
        tool_id=str(row["tool_id"]),
        args=json_loads_or_none(row["args_json"]) or {},
        result=json_loads_or_none(row["result_json"]),
        error=json_loads_or_none(row["error_json"]),
        dry_run=bool(row["dry_run"]),
        policy_decision=str(row["policy_decision"]),  # type: ignore[arg-type]
        audit_log_id=(str(row["audit_log_id"]) if row["audit_log_id"] else None),
        duration_ms=(int(row["duration_ms"]) if row["duration_ms"] is not None else None),
    )
