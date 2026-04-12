"""JournalEntry repository — implements `JournalDbWriter` Protocol."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

import aiosqlite

from ...journal.store import JournalDbWriter
from ...schema._base import utc_now
from ...schema.journal import JournalEntry
from ._base import BaseRepository, json_dumps, json_loads_or_none

__all__ = ["JournalEntriesRepository"]


class JournalEntriesRepository(BaseRepository, JournalDbWriter):
    async def insert(
        self,
        entry: JournalEntry,
        *,
        conn: aiosqlite.Connection | None = None,
    ) -> None:
        query = """
        INSERT INTO journal_entries (id, run_step_id, tool_call_id, kind, before_json,
                                     after_json, before_storage_ref, after_storage_ref,
                                     reversible, restored_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        params = (
            entry.id,
            entry.run_step_id,
            entry.tool_call_id,
            entry.kind,
            json_dumps(entry.before) if entry.before is not None else None,
            json_dumps(entry.after) if entry.after is not None else None,
            entry.before_storage_ref,
            entry.after_storage_ref,
            int(entry.reversible),
            entry.restored_at.isoformat() if entry.restored_at else None,
            entry.created_at.isoformat(),
        )
        await self._execute(query, params, conn=conn)

    async def update_after(
        self,
        entry_id: str,
        *,
        after: dict[str, Any] | None,
        after_storage_ref: str | None,
        conn: aiosqlite.Connection | None = None,
    ) -> None:
        await self._execute_write(
            """
            UPDATE journal_entries
            SET after_json = ?, after_storage_ref = ?
            WHERE id = ?;
            """,
            (
                json_dumps(after) if after is not None else None,
                after_storage_ref,
                entry_id,
            ),
            expected_rows=1,
            error_message=f"journal_entries.update_after: no row for id={entry_id}",
            conn=conn,
        )

    async def mark_restored(
        self,
        entry_id: str,
        *,
        conn: aiosqlite.Connection | None = None,
    ) -> None:
        await self._execute_write(
            "UPDATE journal_entries SET restored_at = ? WHERE id = ?;",
            (utc_now().isoformat(), entry_id),
            expected_rows=1,
            error_message=f"journal_entries.mark_restored: no row for id={entry_id}",
            conn=conn,
        )

    async def list_for_run(
        self,
        run_id: str,
        *,
        conn: aiosqlite.Connection | None = None,
    ) -> Iterable[JournalEntry]:
        rows = await self._fetch_all(
            """
            SELECT je.* FROM journal_entries je
            JOIN run_steps rs ON je.run_step_id = rs.id
            WHERE rs.run_id = ?
            ORDER BY je.created_at;
            """,
            (run_id,),
            conn=conn,
        )
        return [_row_to_entry(r) for r in rows]

    async def get(
        self,
        entry_id: str,
        *,
        conn: aiosqlite.Connection | None = None,
    ) -> JournalEntry | None:
        row = await self._fetch_one(
            "SELECT * FROM journal_entries WHERE id = ?;", (entry_id,), conn=conn
        )
        return _row_to_entry(row) if row else None


def _row_to_entry(row: aiosqlite.Row) -> JournalEntry:
    return JournalEntry(
        id=str(row["id"]),
        run_step_id=str(row["run_step_id"]),
        tool_call_id=str(row["tool_call_id"]),
        kind=str(row["kind"]),  # type: ignore[arg-type]
        before=json_loads_or_none(row["before_json"]),
        after=json_loads_or_none(row["after_json"]),
        before_storage_ref=(str(row["before_storage_ref"]) if row["before_storage_ref"] else None),
        after_storage_ref=(str(row["after_storage_ref"]) if row["after_storage_ref"] else None),
        reversible=bool(row["reversible"]),
        restored_at=(
            datetime.fromisoformat(str(row["restored_at"])) if row["restored_at"] else None
        ),
        created_at=datetime.fromisoformat(str(row["created_at"])),
    )
