"""Run repository."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import aiosqlite

from ...schema.run import Run
from ._base import BaseRepository, json_dumps, json_loads_or_none

__all__ = ["RunsRepository"]


class RunsRepository(BaseRepository):
    async def insert(
        self,
        run: Run,
        *,
        conn: aiosqlite.Connection | None = None,
    ) -> None:
        query = """
        INSERT INTO runs (id, workflow_id, workflow_snapshot, trigger, status,
                          started_at, ended_at, stats_json, error_json, parent_run_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        params: tuple[Any, ...] = (
            run.id,
            run.workflow_id,
            run.workflow_snapshot,
            run.trigger,
            run.status,
            run.started_at.isoformat(),
            run.ended_at.isoformat() if run.ended_at else None,
            json_dumps(run.stats) if run.stats else None,
            json_dumps(run.error) if run.error else None,
            run.parent_run_id,
        )
        await self._execute(query, params, conn=conn)

    async def update_status(
        self,
        run_id: str,
        *,
        status: str,
        ended_at: datetime | None = None,
        conn: aiosqlite.Connection | None = None,
    ) -> None:
        await self._execute_write(
            "UPDATE runs SET status = ?, ended_at = ? WHERE id = ?;",
            (status, ended_at.isoformat() if ended_at else None, run_id),
            expected_rows=1,
            error_message=f"runs.update_status: no row for id={run_id}",
            conn=conn,
        )

    async def get(self, run_id: str, *, conn: aiosqlite.Connection | None = None) -> Run | None:
        row = await self._fetch_one("SELECT * FROM runs WHERE id = ?;", (run_id,), conn=conn)
        return _row_to_run(row) if row else None

    async def list_all(self, *, conn: aiosqlite.Connection | None = None) -> list[Run]:
        rows = await self._fetch_all("SELECT * FROM runs ORDER BY started_at DESC;", conn=conn)
        return [_row_to_run(r) for r in rows]


def _row_to_run(row: aiosqlite.Row) -> Run:
    return Run(
        id=str(row["id"]),
        workflow_id=str(row["workflow_id"]),
        workflow_snapshot=str(row["workflow_snapshot"]),
        trigger=str(row["trigger"]),  # type: ignore[arg-type]
        status=str(row["status"]),  # type: ignore[arg-type]
        started_at=datetime.fromisoformat(str(row["started_at"])),
        ended_at=(datetime.fromisoformat(str(row["ended_at"])) if row["ended_at"] else None),
        stats=json_loads_or_none(row["stats_json"]) or {},
        error=json_loads_or_none(row["error_json"]),
        parent_run_id=(str(row["parent_run_id"]) if row["parent_run_id"] else None),
    )
