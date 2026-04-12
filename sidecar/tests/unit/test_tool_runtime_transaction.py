"""ToolRuntime + Database.transaction() 원자성 검증.

성공 경로: Audit / Journal / ToolCall 가 모두 커밋되어 새 커넥션에서 조회됨.
실패 경로: Journal 쓰기가 실패하면 ToolCall / Audit 도 롤백되어 레코드 없음.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from orca_core.errors import ToolRuntimeError
from orca_core.journal.store import JournalWriteError
from orca_core.persistence import (
    AuditLogsRepository,
    Database,
    JournalEntriesRepository,
    ToolCallsRepository,
)
from orca_core.schema import Policy, PolicyRule
from orca_core.tools import InMemoryEventEmitter, ToolRuntime
from orca_core.tools.fs import FsWriteFileTool

from ._m3_helpers import (
    DatabaseBackedTransactionFactory,
    make_audit_log_path,
    make_journal_base,
    seed_run,
)


@pytest.fixture
async def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "tx.sqlite")
    await database.initialize()
    return database


async def test_success_path_commits_all_three_records(tmp_path: Path, db: Database):
    run, step = await seed_run(db)
    factory = DatabaseBackedTransactionFactory(
        db,
        audit_repo=AuditLogsRepository(db),
        journal_repo=JournalEntriesRepository(db),
        tool_calls_repo=ToolCallsRepository(db),
    )

    runtime = ToolRuntime(
        transaction_factory=factory,
        audit_log_path=make_audit_log_path(tmp_path),
        journal_base_dir=make_journal_base(tmp_path),
        events=InMemoryEventEmitter(),
    )

    class _AutoRunWrite(FsWriteFileTool):
        default_dry_run: bool = False

    target = tmp_path / "out.txt"
    result = await runtime.invoke(
        _AutoRunWrite(),
        args={"path": str(target), "content": "atomic"},
        policy=Policy(
            name="allow-write",
            mode="ask",
            rules=[
                PolicyRule(
                    priority=10,
                    scope="tool_id",
                    matcher="fs.write_file",
                    effect="allow",
                ),
            ],
        ),
        run_id=run.id,
        run_step_id=step.id,
    )
    assert result.outcome == "succeeded"

    # Verify all three from a separate connection
    audit_repo = AuditLogsRepository(db)
    tc_repo = ToolCallsRepository(db)
    journal_repo = JournalEntriesRepository(db)

    audits = await audit_repo.list_for_run(run.id)
    assert len(audits) == 1
    assert audits[0].status == "success"

    tcalls = await tc_repo.list_for_step(step.id)
    assert len(tcalls) == 1
    assert tcalls[0].tool_id == "fs.write_file"
    # H3: DB row must reflect result/duration/audit_log_id back-fill.
    assert tcalls[0].result is not None
    assert tcalls[0].duration_ms is not None
    assert tcalls[0].duration_ms >= 0
    assert tcalls[0].audit_log_id == audits[0].id

    jentries = list(await journal_repo.list_for_run(run.id))
    assert len(jentries) == 1
    assert jentries[0].reversible is True


async def test_schema_invariant_db_level_every_destructive_tool_call_has_audit(
    tmp_path: Path, db: Database
):
    """Regression-proof for schema.md §5 #1 + #2 at the DB level:

    - #1: every destructive/sensitive tool_call must have an audit_log_id
      pointing at a committed audit_logs row.
    - #2: if reversible=True, a JournalEntry.before row must exist before
      the tool actually ran.

    We run the full FsWriteFileTool success path, then join tool_calls →
    audit_logs → journal_entries from a fresh connection and verify all
    three rows are committed, and that tool_calls.audit_log_id matches
    audit_logs.id.
    """
    run, step = await seed_run(db)
    factory = DatabaseBackedTransactionFactory(
        db,
        audit_repo=AuditLogsRepository(db),
        journal_repo=JournalEntriesRepository(db),
        tool_calls_repo=ToolCallsRepository(db),
    )
    runtime = ToolRuntime(
        transaction_factory=factory,
        audit_log_path=make_audit_log_path(tmp_path),
        journal_base_dir=make_journal_base(tmp_path),
        events=InMemoryEventEmitter(),
    )

    class _AutoRunWrite(FsWriteFileTool):
        default_dry_run: bool = False

    target = tmp_path / "invariant.txt"
    result = await runtime.invoke(
        _AutoRunWrite(),
        args={"path": str(target), "content": "inv"},
        policy=Policy(
            name="allow-write",
            mode="ask",
            rules=[
                PolicyRule(
                    priority=10,
                    scope="tool_id",
                    matcher="fs.write_file",
                    effect="allow",
                ),
            ],
        ),
        run_id=run.id,
        run_step_id=step.id,
    )
    assert result.outcome == "succeeded"

    tool_calls = await ToolCallsRepository(db).list_for_step(step.id)
    audits = await AuditLogsRepository(db).list_for_run(run.id)
    journal_rows = list(await JournalEntriesRepository(db).list_for_run(run.id))

    # #1: tool_call exists AND audit_log_id is set to a real row.
    assert len(tool_calls) == 1
    tc = tool_calls[0]
    assert tc.audit_log_id is not None
    assert len(audits) == 1
    assert tc.audit_log_id == audits[0].id
    assert audits[0].status == "success"
    # #2: journal.before row exists (reversible=True).
    assert len(journal_rows) == 1
    assert journal_rows[0].tool_call_id == tc.id
    assert journal_rows[0].before is not None
    assert journal_rows[0].reversible is True


async def test_journal_write_failure_records_rescue_audit_and_tool_call(
    tmp_path: Path, db: Database
):
    """H4 regression: when journal.record_before fails and the main
    transaction rolls back, ToolRuntime must open a rescue transaction and
    commit exactly one blocked audit + one blocked tool_call row so that
    schema.md §5 #1 (every destructive tool_call is recorded in AuditLog)
    still holds at the DB level.

    The tool itself must NOT run (fail-closed), the side-effect file must
    not exist, and the journal table must remain empty for the run.
    """
    run, step = await seed_run(db)

    class _FailingJournal(JournalEntriesRepository):
        async def insert(self, entry, *, conn=None):  # type: ignore[override]
            raise JournalWriteError("simulated disk error")

    factory = DatabaseBackedTransactionFactory(
        db,
        audit_repo=AuditLogsRepository(db),
        journal_repo=_FailingJournal(db),
        tool_calls_repo=ToolCallsRepository(db),
    )

    runtime = ToolRuntime(
        transaction_factory=factory,
        audit_log_path=make_audit_log_path(tmp_path),
        journal_base_dir=make_journal_base(tmp_path),
        events=InMemoryEventEmitter(),
    )

    class _AutoRunWrite(FsWriteFileTool):
        default_dry_run: bool = False

    target = tmp_path / "rolled-back.txt"
    with pytest.raises(ToolRuntimeError):
        await runtime.invoke(
            _AutoRunWrite(),
            args={"path": str(target), "content": "should not persist"},
            policy=Policy(
                name="allow",
                mode="ask",
                rules=[
                    PolicyRule(
                        priority=10,
                        scope="tool_id",
                        matcher="fs.write_file",
                        effect="allow",
                    ),
                ],
            ),
            run_id=run.id,
            run_step_id=step.id,
        )

    # H4: rescue transaction must have committed exactly one audit (blocked)
    # and one tool_call row referencing that audit.
    audits = await AuditLogsRepository(db).list_for_run(run.id)
    assert len(audits) == 1
    assert audits[0].status == "blocked"

    tool_calls = await ToolCallsRepository(db).list_for_step(step.id)
    assert len(tool_calls) == 1
    assert tool_calls[0].policy_decision == "allow"
    assert tool_calls[0].audit_log_id == audits[0].id
    assert tool_calls[0].error is not None
    assert tool_calls[0].error["phase"] == "journal_before"

    # The journal table stays empty — no partial entry survived.
    journal_rows = list(await JournalEntriesRepository(db).list_for_run(run.id))
    assert journal_rows == []
    # The target file must NOT exist (fail-closed).
    assert not target.exists()
