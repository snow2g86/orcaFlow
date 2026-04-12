"""M3 테스트 공통 헬퍼.

- `InMemoryTransactionFactory` : Database 없이 ToolRuntime 을 테스트할 수
  있도록 in-memory 쓰기 버퍼를 제공하는 TransactionFactory 구현.
- `DatabaseBackedTransactionFactory` : 실제 `Database.transaction()` 으로
  감싼 구현 — 원자성 검증용.
"""

from __future__ import annotations

from pathlib import Path
from types import TracebackType
from typing import Any

import aiosqlite

from orca_core.journal.store import JournalDbWriter
from orca_core.persistence import (
    AuditLogsRepository,
    Database,
    JournalEntriesRepository,
    RunsRepository,
    RunStepsRepository,
    ToolCallsRepository,
    WorkflowsRepository,
)
from orca_core.schema import (
    AgentNode,
    Position,
    Run,
    RunStep,
    Workflow,
)
from orca_core.schema.audit import AuditLog
from orca_core.schema.journal import JournalEntry
from orca_core.schema.run import ToolCall
from orca_core.tools import TransactionScope

# ---------------------------------------------------------------------------
# In-memory writers (no Database dependency)
# ---------------------------------------------------------------------------


class InMemoryAuditWriter:
    def __init__(self) -> None:
        self.records: list[AuditLog] = []

    async def insert(self, record: AuditLog) -> None:
        self.records.append(record)


class InMemoryJournalWriter(JournalDbWriter):
    def __init__(self) -> None:
        self.entries: list[JournalEntry] = []

    async def insert(self, entry: JournalEntry) -> None:
        self.entries.append(entry)

    async def update_after(
        self,
        entry_id: str,
        *,
        after: dict[str, Any] | None,
        after_storage_ref: str | None,
    ) -> None:
        for i, e in enumerate(self.entries):
            if e.id == entry_id:
                self.entries[i] = e.model_copy(
                    update={"after": after, "after_storage_ref": after_storage_ref}
                )
                return

    async def mark_restored(self, entry_id: str) -> None:
        from datetime import UTC, datetime

        for i, e in enumerate(self.entries):
            if e.id == entry_id:
                self.entries[i] = e.model_copy(update={"restored_at": datetime.now(tz=UTC)})
                return

    async def list_for_run(self, run_id: str) -> list[JournalEntry]:
        return list(self.entries)


class InMemoryToolCallWriter:
    def __init__(self) -> None:
        self.calls: list[ToolCall] = []

    async def insert(self, call: ToolCall) -> None:
        self.calls.append(call)

    async def update_result(
        self,
        tool_call_id: str,
        *,
        result_json: dict[str, Any] | None,
        error_json: dict[str, Any] | None,
        duration_ms: int | None,
        audit_log_id: str | None,
        policy_decision: str | None = None,
    ) -> None:
        for i, call in enumerate(self.calls):
            if call.id == tool_call_id:
                updates: dict[str, Any] = {
                    "result": result_json,
                    "error": error_json,
                    "duration_ms": duration_ms,
                    "audit_log_id": audit_log_id,
                }
                if policy_decision is not None:
                    updates["policy_decision"] = policy_decision
                self.calls[i] = call.model_copy(update=updates)
                return


class InMemoryTransactionFactory:
    """재사용 가능한 in-memory 쓰기 버퍼를 감싸는 async context factory."""

    def __init__(self) -> None:
        self.audit = InMemoryAuditWriter()
        self.journal = InMemoryJournalWriter()
        self.tool_calls = InMemoryToolCallWriter()
        self.commit_count = 0
        self.rollback_count = 0

    def __call__(self) -> _InMemoryTxContext:
        return _InMemoryTxContext(self)


class _InMemoryTxContext:
    def __init__(self, parent: InMemoryTransactionFactory) -> None:
        self._parent = parent
        # snapshot counts for rollback
        self._audit_mark = len(parent.audit.records)
        self._journal_mark = len(parent.journal.entries)
        self._tc_mark = len(parent.tool_calls.calls)

    async def __aenter__(self) -> TransactionScope:
        return TransactionScope(
            audit_db_writer=self._parent.audit,
            journal_db_writer=self._parent.journal,
            tool_call_writer=self._parent.tool_calls,
        )

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc is None:
            self._parent.commit_count += 1
            return
        # rollback: truncate the buffers to snapshot marks
        self._parent.audit.records[self._audit_mark :] = []
        self._parent.journal.entries[self._journal_mark :] = []
        self._parent.tool_calls.calls[self._tc_mark :] = []
        self._parent.rollback_count += 1


# ---------------------------------------------------------------------------
# Database-backed factory (for real tx atomicity tests)
# ---------------------------------------------------------------------------


class _ConnBoundAuditWriter:
    def __init__(self, repo: AuditLogsRepository, conn: aiosqlite.Connection) -> None:
        self._repo = repo
        self._conn = conn

    async def insert(self, record: AuditLog) -> None:
        await self._repo.insert(record, conn=self._conn)


class _ConnBoundJournalWriter:
    def __init__(self, repo: JournalEntriesRepository, conn: aiosqlite.Connection) -> None:
        self._repo = repo
        self._conn = conn

    async def insert(self, entry: JournalEntry) -> None:
        await self._repo.insert(entry, conn=self._conn)

    async def update_after(
        self,
        entry_id: str,
        *,
        after: dict[str, Any] | None,
        after_storage_ref: str | None,
    ) -> None:
        await self._repo.update_after(
            entry_id,
            after=after,
            after_storage_ref=after_storage_ref,
            conn=self._conn,
        )

    async def mark_restored(self, entry_id: str) -> None:
        await self._repo.mark_restored(entry_id, conn=self._conn)

    async def list_for_run(self, run_id: str) -> list[JournalEntry]:
        result = await self._repo.list_for_run(run_id, conn=self._conn)
        return list(result)


class _ConnBoundToolCallWriter:
    def __init__(self, repo: ToolCallsRepository, conn: aiosqlite.Connection) -> None:
        self._repo = repo
        self._conn = conn

    async def insert(self, call: ToolCall) -> None:
        await self._repo.insert(call, conn=self._conn)

    async def update_result(
        self,
        tool_call_id: str,
        *,
        result_json: dict[str, Any] | None,
        error_json: dict[str, Any] | None,
        duration_ms: int | None,
        audit_log_id: str | None,
        policy_decision: str | None = None,
    ) -> None:
        await self._repo.update_result(
            tool_call_id,
            result_json=result_json,
            error_json=error_json,
            duration_ms=duration_ms,
            audit_log_id=audit_log_id,
            policy_decision=policy_decision,
            conn=self._conn,
        )


class DatabaseBackedTransactionFactory:
    """`Database.transaction()` 을 감싸는 TransactionFactory."""

    def __init__(
        self,
        db: Database,
        *,
        audit_repo: AuditLogsRepository,
        journal_repo: JournalEntriesRepository,
        tool_calls_repo: ToolCallsRepository,
    ) -> None:
        self._db = db
        self._audit_repo = audit_repo
        self._journal_repo = journal_repo
        self._tool_calls_repo = tool_calls_repo

    def __call__(self) -> _DbTxContext:
        return _DbTxContext(self)


class _DbTxContext:
    def __init__(self, parent: DatabaseBackedTransactionFactory) -> None:
        self._parent = parent
        self._cm = None
        self._conn: aiosqlite.Connection | None = None

    async def __aenter__(self) -> TransactionScope:
        self._cm = self._parent._db.transaction()
        self._conn = await self._cm.__aenter__()
        return TransactionScope(
            audit_db_writer=_ConnBoundAuditWriter(self._parent._audit_repo, self._conn),
            journal_db_writer=_ConnBoundJournalWriter(self._parent._journal_repo, self._conn),
            tool_call_writer=_ConnBoundToolCallWriter(self._parent._tool_calls_repo, self._conn),
        )

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._cm is not None:
            await self._cm.__aexit__(exc_type, exc, tb)


# ---------------------------------------------------------------------------
# DB fixture helpers
# ---------------------------------------------------------------------------


async def seed_run(db: Database) -> tuple[Run, RunStep]:
    """workflow → run → run_step 1건씩 생성해 반환."""
    workflows = WorkflowsRepository(db)
    wf = Workflow(
        name="m3-test",
        nodes=[AgentNode(id="a", role="worker", position=Position(x=0, y=0))],
        edges=[],
        entrypoint="a",
    )
    await workflows.upsert(wf, yaml="version: 1\nname: m3-test")

    runs = RunsRepository(db)
    run = Run(
        workflow_id=wf.id,
        workflow_snapshot="version: 1\nname: m3-test",
        trigger="manual",
        status="running",
    )
    await runs.insert(run)

    steps = RunStepsRepository(db)
    step = RunStep(run_id=run.id, kind="tool_call", payload={}, status="running")
    await steps.insert(step)

    return run, step


def make_audit_log_path(tmp_path: Path) -> Path:
    return tmp_path / "logs" / "audit.log"


def make_journal_base(tmp_path: Path) -> Path:
    return tmp_path / "journal"
