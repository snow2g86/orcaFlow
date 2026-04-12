"""RunStep repository."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import aiosqlite

from ...schema.run import RunStep
from ._base import BaseRepository, json_dumps, json_loads_or_none

__all__ = ["RunStepsRepository"]


class RunStepsRepository(BaseRepository):
    async def insert(
        self,
        step: RunStep,
        *,
        conn: aiosqlite.Connection | None = None,
    ) -> None:
        query = """
        INSERT INTO run_steps (id, run_id, parent_step_id, node_id, kind, payload_json,
                               result_json, status, started_at, ended_at, duration_ms,
                               tokens_in, tokens_out)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        params: tuple[Any, ...] = (
            step.id,
            step.run_id,
            step.parent_step_id,
            step.node_id,
            step.kind,
            json_dumps(step.payload),
            json_dumps(step.result) if step.result is not None else None,
            step.status,
            step.started_at.isoformat(),
            step.ended_at.isoformat() if step.ended_at else None,
            step.duration_ms,
            step.tokens_in,
            step.tokens_out,
        )
        await self._execute(query, params, conn=conn)

    async def list_for_run(
        self, run_id: str, *, conn: aiosqlite.Connection | None = None
    ) -> list[RunStep]:
        rows = await self._fetch_all(
            "SELECT * FROM run_steps WHERE run_id = ? ORDER BY started_at;",
            (run_id,),
            conn=conn,
        )
        return [_row_to_step(r) for r in rows]


def _row_to_step(row: aiosqlite.Row) -> RunStep:
    return RunStep(
        id=str(row["id"]),
        run_id=str(row["run_id"]),
        parent_step_id=(str(row["parent_step_id"]) if row["parent_step_id"] else None),
        node_id=(str(row["node_id"]) if row["node_id"] else None),
        kind=str(row["kind"]),  # type: ignore[arg-type]
        payload=json_loads_or_none(row["payload_json"]) or {},
        result=json_loads_or_none(row["result_json"]),
        status=str(row["status"]),  # type: ignore[arg-type]
        started_at=datetime.fromisoformat(str(row["started_at"])),
        ended_at=(datetime.fromisoformat(str(row["ended_at"])) if row["ended_at"] else None),
        duration_ms=(int(row["duration_ms"]) if row["duration_ms"] is not None else None),
        tokens_in=(int(row["tokens_in"]) if row["tokens_in"] is not None else None),
        tokens_out=(int(row["tokens_out"]) if row["tokens_out"] is not None else None),
    )
