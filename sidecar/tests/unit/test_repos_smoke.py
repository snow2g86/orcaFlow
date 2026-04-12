"""Repository CRUD 스모크 테스트."""

from __future__ import annotations

from pathlib import Path

import pytest

from orca_core.audit import AuditSink
from orca_core.persistence import (
    AgentRolesRepository,
    ApprovalsRepository,
    AuditLogsRepository,
    Database,
    JournalEntriesRepository,
    LLMProfilesRepository,
    PoliciesRepository,
    ProvidersRepository,
    RunsRepository,
    RunStepsRepository,
    ToolCallsRepository,
    WorkflowsRepository,
)
from orca_core.schema import (
    AgentNode,
    AgentRole,
    ApprovalRequest,
    Edge,
    LLMProfile,
    Policy,
    PolicyRule,
    Position,
    Provider,
    Run,
    RunStep,
    ToolCall,
    Workflow,
)


@pytest.fixture
async def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "repo.sqlite")
    await database.initialize()
    return database


async def test_workflow_repository_upsert_and_get(db: Database):
    repo = WorkflowsRepository(db)
    wf = Workflow(
        name="doc cleanup",
        nodes=[AgentNode(id="a", role="worker", position=Position(x=0, y=0))],
        edges=[],
        entrypoint="a",
    )
    await repo.upsert(wf, yaml="version: 1\nname: doc cleanup")
    row = await repo.get(wf.id)
    assert row is not None
    assert row.name == "doc cleanup"
    assert "version" in row.yaml

    rows = await repo.list_all()
    assert len(rows) == 1


async def test_provider_llm_profile_agent_role_chain(db: Database):
    providers = ProvidersRepository(db)
    profiles = LLMProfilesRepository(db)
    roles = AgentRolesRepository(db)

    provider = Provider(name="ollama", kind="ollama", base_url="http://localhost:11434")
    await providers.upsert(provider)

    profile = LLMProfile(
        name="ollama-qwen2.5-14b",
        provider_id=provider.id,
        model="qwen2.5:14b",
        params={"temperature": 0.2},
    )
    await profiles.upsert(profile)

    role = AgentRole(
        name="file-organizer",
        role_type="worker",
        system_prompt="organize files",
        tools=["fs.read_file", "fs.move"],
        llm_profile_id=profile.id,
    )
    await roles.upsert(role)

    got_provider = await providers.get(provider.id)
    assert got_provider is not None
    assert got_provider.name == "ollama"

    got_profile = await profiles.get(profile.id)
    assert got_profile is not None
    assert got_profile.params["temperature"] == 0.2

    got_role = await roles.get(role.id)
    assert got_role is not None
    assert "fs.read_file" in got_role.tools


async def test_policy_round_trip(db: Database):
    repo = PoliciesRepository(db)
    pol = Policy(
        name="default",
        mode="ask",
        rules=[
            PolicyRule(priority=10, scope="tool_id", matcher="fs.*", effect="allow"),
            PolicyRule(
                priority=20,
                scope="shell_command",
                matcher=r"^rm -rf /",
                effect="deny",
            ),
        ],
    )
    await repo.upsert(pol, yaml="policy: default")
    got = await repo.get(pol.id)
    assert got is not None
    assert got.name == "default"
    assert len(got.rules) == 2
    assert got.rules[0].priority == 10


async def test_run_step_tool_call_audit_chain(db: Database, tmp_path: Path):
    # We need workflows row first because runs references it.
    workflows_repo = WorkflowsRepository(db)
    wf = Workflow(
        name="t",
        nodes=[AgentNode(id="a", role="w", position=Position(x=0, y=0))],
        edges=[],
        entrypoint="a",
    )
    await workflows_repo.upsert(wf, yaml="version: 1")

    runs_repo = RunsRepository(db)
    run = Run(
        workflow_id=wf.id,
        workflow_snapshot="version: 1\nname: t",
        trigger="manual",
        status="running",
    )
    await runs_repo.insert(run)

    steps_repo = RunStepsRepository(db)
    step = RunStep(run_id=run.id, kind="tool_call", payload={}, status="running")
    await steps_repo.insert(step)
    steps = await steps_repo.list_for_run(run.id)
    assert len(steps) == 1

    calls_repo = ToolCallsRepository(db)
    call = ToolCall(
        run_step_id=step.id,
        tool_id="fs.delete",
        args={"path": "/tmp/x"},
        policy_decision="allow",
    )
    await calls_repo.insert(call)
    got_call = await calls_repo.get(call.id)
    assert got_call is not None
    assert got_call.tool_id == "fs.delete"

    audit_repo = AuditLogsRepository(db)
    sink = AuditSink(
        log_path=tmp_path / "audit.log",
        db_writer=audit_repo,
        hash_prev_provider=audit_repo.latest_hash,
    )
    first = await sink.record(
        actor="user",
        action="fs.delete",
        target="/tmp/x",
        status="success",
        policy_decision="allow",
        run_id=run.id,
        run_step_id=step.id,
    )
    got = await audit_repo.get(first.id)
    assert got is not None
    assert got.hash_self == first.hash_self

    # Second record should chain
    second = await sink.record(
        actor="user",
        action="fs.delete",
        target="/tmp/y",
        status="success",
        policy_decision="allow",
        run_id=run.id,
        run_step_id=step.id,
    )
    assert second.hash_prev == first.hash_self

    # audit_logs repo has no update/delete methods (append-only)
    assert not hasattr(audit_repo, "update")
    assert not hasattr(audit_repo, "delete")


async def test_journal_entries_repo_round_trip(db: Database, tmp_path: Path):
    # Need: workflow → run → run_step → tool_call → journal
    workflows_repo = WorkflowsRepository(db)
    wf = Workflow(
        name="t",
        nodes=[AgentNode(id="a", role="w", position=Position(x=0, y=0))],
        edges=[],
        entrypoint="a",
    )
    await workflows_repo.upsert(wf, yaml="version: 1")

    runs = RunsRepository(db)
    run = Run(
        workflow_id=wf.id,
        workflow_snapshot="version: 1\nname: t",
        trigger="manual",
        status="running",
    )
    await runs.insert(run)

    steps_repo = RunStepsRepository(db)
    step = RunStep(run_id=run.id, kind="tool_call", payload={}, status="running")
    await steps_repo.insert(step)

    calls_repo = ToolCallsRepository(db)
    call = ToolCall(
        run_step_id=step.id,
        tool_id="fs.write_file",
        args={"path": "/tmp/x"},
        policy_decision="allow",
    )
    await calls_repo.insert(call)

    from orca_core.journal import JournalStore

    journal_repo = JournalEntriesRepository(db)
    store = JournalStore(base_dir=tmp_path / "journal", db_writer=journal_repo)
    entry = await store.record_before(
        run_id=run.id,
        run_step_id=step.id,
        tool_call_id=call.id,
        kind="fs_write",
        before={"content": "old"},
        reversible=True,
    )
    got = await journal_repo.get(entry.id)
    assert got is not None
    assert got.before == {"content": "old"}

    updated = await store.record_after(entry, run_id=run.id, after={"content": "new"})
    # Verify the update_after path via DB query
    got2 = await journal_repo.get(updated.id)
    assert got2 is not None
    assert got2.after == {"content": "new"}


async def test_approval_request_state_update(db: Database):
    workflows_repo = WorkflowsRepository(db)
    wf = Workflow(
        name="t",
        nodes=[AgentNode(id="a", role="w", position=Position(x=0, y=0))],
        edges=[],
        entrypoint="a",
    )
    await workflows_repo.upsert(wf, yaml="version: 1")
    runs = RunsRepository(db)
    run = Run(
        workflow_id=wf.id,
        workflow_snapshot="version: 1",
        trigger="manual",
        status="awaiting_approval",
    )
    await runs.insert(run)
    steps_repo = RunStepsRepository(db)
    step = RunStep(run_id=run.id, kind="approval", payload={}, status="running")
    await steps_repo.insert(step)

    repo = ApprovalsRepository(db)
    req = ApprovalRequest(
        run_step_id=step.id,
        reason="destructive",
    )
    await repo.insert(req)
    got = await repo.get(req.id)
    assert got is not None
    assert got.state == "pending"


async def test_edge_roundtrip_via_workflow_model():
    """Edge uses alias='from' — ensure validator accepts both forms."""
    wf = Workflow(
        name="t",
        nodes=[
            AgentNode(id="a", role="w", position=Position(x=0, y=0)),
            AgentNode(id="b", role="w", position=Position(x=1, y=0)),
        ],
        edges=[Edge(**{"from": "a", "to": "b"})],
        entrypoint="a",
    )
    assert wf.edges[0].from_ == "a"


# ---------------------------------------------------------------------------
# H5 regression: Repository rowcount validation
# ---------------------------------------------------------------------------


async def test_journal_update_after_missing_id_raises(db: Database):
    from orca_core.persistence.repo._base import RepositoryError

    repo = JournalEntriesRepository(db)
    with pytest.raises(RepositoryError, match="no row"):
        await repo.update_after(
            "nonexistent-id",
            after={"x": 1},
            after_storage_ref=None,
        )


async def test_journal_mark_restored_missing_id_raises(db: Database):
    from orca_core.persistence.repo._base import RepositoryError

    repo = JournalEntriesRepository(db)
    with pytest.raises(RepositoryError, match="no row"):
        await repo.mark_restored("nonexistent-id")


async def test_approval_update_state_missing_or_decided_raises(db: Database):
    from datetime import UTC, datetime

    from orca_core.persistence.repo._base import RepositoryError

    workflows_repo = WorkflowsRepository(db)
    wf = Workflow(
        name="t",
        nodes=[AgentNode(id="a", role="w", position=Position(x=0, y=0))],
        edges=[],
        entrypoint="a",
    )
    await workflows_repo.upsert(wf, yaml="version: 1")
    runs = RunsRepository(db)
    run = Run(
        workflow_id=wf.id,
        workflow_snapshot="version: 1",
        trigger="manual",
        status="awaiting_approval",
    )
    await runs.insert(run)
    steps_repo = RunStepsRepository(db)
    step = RunStep(run_id=run.id, kind="approval", payload={}, status="running")
    await steps_repo.insert(step)

    repo = ApprovalsRepository(db)
    req = ApprovalRequest(run_step_id=step.id, reason="destructive")
    await repo.insert(req)

    # First approval transitions OK
    await repo.update_state(
        req.id, state="approved", decided_at=datetime.now(tz=UTC), decided_by="user"
    )
    # Second attempt: already approved, no pending row — must raise.
    with pytest.raises(RepositoryError, match="no pending"):
        await repo.update_state(
            req.id,
            state="rejected",
            decided_at=datetime.now(tz=UTC),
            decided_by="user",
        )
    # Unknown id → raise
    with pytest.raises(RepositoryError, match="no pending"):
        await repo.update_state(
            "unknown",
            state="approved",
            decided_at=datetime.now(tz=UTC),
            decided_by="user",
        )


# ---------------------------------------------------------------------------
# H6 regression: Database.transaction() commits on success, rolls back on error
# ---------------------------------------------------------------------------


async def test_transaction_commits_multiple_repo_writes(db: Database):
    workflows_repo = WorkflowsRepository(db)
    runs_repo = RunsRepository(db)

    wf = Workflow(
        name="tx",
        nodes=[AgentNode(id="a", role="w", position=Position(x=0, y=0))],
        edges=[],
        entrypoint="a",
    )
    await workflows_repo.upsert(wf, yaml="version: 1")

    run = Run(
        workflow_id=wf.id,
        workflow_snapshot="version: 1",
        trigger="manual",
        status="running",
    )
    async with db.transaction() as conn:
        await runs_repo.insert(run, conn=conn)
        # visible within transaction
        row = await runs_repo.get(run.id, conn=conn)
        assert row is not None

    # committed — visible from a separate connection
    assert await runs_repo.get(run.id) is not None


async def test_transaction_rolls_back_on_error(db: Database):
    workflows_repo = WorkflowsRepository(db)
    runs_repo = RunsRepository(db)

    wf = Workflow(
        name="tx2",
        nodes=[AgentNode(id="a", role="w", position=Position(x=0, y=0))],
        edges=[],
        entrypoint="a",
    )
    await workflows_repo.upsert(wf, yaml="version: 1")

    run = Run(
        workflow_id=wf.id,
        workflow_snapshot="version: 1",
        trigger="manual",
        status="running",
    )

    class BoomError(RuntimeError):
        pass

    async def _do_tx() -> None:
        async with db.transaction() as conn:
            await runs_repo.insert(run, conn=conn)
            raise BoomError("forced rollback")

    with pytest.raises(BoomError):
        await _do_tx()

    # Not committed — not visible from new connection
    assert await runs_repo.get(run.id) is None


# ---------------------------------------------------------------------------
# M5 regression: AuditLogsRepository.latest_hash raises on corrupted empty hash
# ---------------------------------------------------------------------------


async def test_audit_latest_hash_raises_on_empty_hash(db: Database, tmp_path: Path):
    """Write a corrupted row with empty hash_self directly, then call
    latest_hash(). Must raise AuditIntegrityError instead of returning None.
    """
    workflows_repo = WorkflowsRepository(db)
    wf = Workflow(
        name="t",
        nodes=[AgentNode(id="a", role="w", position=Position(x=0, y=0))],
        edges=[],
        entrypoint="a",
    )
    await workflows_repo.upsert(wf, yaml="version: 1")
    runs = RunsRepository(db)
    run = Run(
        workflow_id=wf.id,
        workflow_snapshot="version: 1",
        trigger="manual",
        status="running",
    )
    await runs.insert(run)
    steps_repo = RunStepsRepository(db)
    step = RunStep(run_id=run.id, kind="tool_call", payload={}, status="running")
    await steps_repo.insert(step)

    # Bypass AuditSink and write a deliberately-corrupted row.
    from datetime import UTC, datetime

    async with db.connect() as conn:
        await conn.execute(
            """
            INSERT INTO audit_logs (id, at, actor, action, target, status,
                                    policy_decision, run_id, run_step_id,
                                    hash_prev, hash_self)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                "corrupted",
                datetime.now(tz=UTC).isoformat(),
                "user",
                "fs.delete",
                "/tmp/x",
                "success",
                "allow",
                run.id,
                step.id,
                None,
                "",  # corrupted empty hash_self
            ),
        )
        await conn.commit()

    from orca_core.persistence.repo.audit_logs import AuditIntegrityError

    repo = AuditLogsRepository(db)
    with pytest.raises(AuditIntegrityError, match="corrupted"):
        await repo.latest_hash()
