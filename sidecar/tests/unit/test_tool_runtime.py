"""ToolRuntime 7단계 플로우 커버.

각 단계의 성공/실패/우회 경로를 명시적으로 테스트한다 (design.md §6.2).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import pytest

from orca_core.errors import PolicyViolationError, ToolRuntimeError, ValidationError
from orca_core.journal.store import JournalWriteError
from orca_core.schema import Permission, Policy, PolicyRule
from orca_core.schema.tool import SideEffect, ToolNamespace
from orca_core.tools import (
    InMemoryEventEmitter,
    ToolContext,
    ToolResult,
    ToolRuntime,
)

from ._m3_helpers import (
    InMemoryTransactionFactory,
    make_audit_log_path,
    make_journal_base,
)

# ---------------------------------------------------------------------------
# Test double tools
# ---------------------------------------------------------------------------


class _FakeRun:
    """Minimal tool used to drive the runtime (read side-effect)."""

    id: str = "fs.read_file"
    namespace: ClassVar[ToolNamespace] = "fs"
    name: str = "read_file"
    side_effect: ClassVar[SideEffect] = "read"
    reversible: bool = False
    default_dry_run: bool = False
    timeout_ms: int = 5_000
    max_output_bytes: int = 1024

    def __init__(self) -> None:
        self.run_calls = 0
        self.dry_calls = 0

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["path"],
            "properties": {"path": {"type": "string"}},
            "additionalProperties": False,
        }

    def output_schema(self) -> dict[str, Any]:
        return {"type": "object"}

    def permissions(self) -> list[Permission]:
        return []

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        self.run_calls += 1
        return ToolResult(output={"content": "x"})

    async def dry_run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        self.dry_calls += 1
        return ToolResult(
            output={"content": "preview"},
            diff_preview={"preview": "ok"},
        )


class _ReversibleWriteTool(_FakeRun):
    """Tool that is reversible+write and records before snapshot in dry_run."""

    id: str = "fs.write_file"
    name: str = "write_file"
    side_effect: ClassVar[SideEffect] = "write"
    reversible: bool = True
    default_dry_run: bool = True

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["path", "content"],
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "additionalProperties": False,
        }

    async def dry_run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        self.dry_calls += 1
        return ToolResult(
            output={"path": args["path"], "bytes_written": 3},
            diff_preview={"existed": False, "new_size": 3},
            before_snapshot={"existed": False, "path": args["path"]},
        )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        self.run_calls += 1
        return ToolResult(output={"path": args["path"], "bytes_written": 3})


class _FailingRun(_ReversibleWriteTool):
    """run() raises."""

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        raise RuntimeError("disk full")


class _FailingDry(_ReversibleWriteTool):
    async def dry_run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        raise RuntimeError("dry preview failed")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def factory() -> InMemoryTransactionFactory:
    return InMemoryTransactionFactory()


@pytest.fixture
def events() -> InMemoryEventEmitter:
    return InMemoryEventEmitter()


@pytest.fixture
def runtime(
    factory: InMemoryTransactionFactory,
    events: InMemoryEventEmitter,
    tmp_path: Path,
) -> ToolRuntime:
    return ToolRuntime(
        transaction_factory=factory,
        audit_log_path=make_audit_log_path(tmp_path),
        journal_base_dir=make_journal_base(tmp_path),
        events=events,
    )


def _trusted_policy() -> Policy:
    return Policy(name="trusted", mode="trusted")


def _deny_policy(tool_id: str = "fs.read_file") -> Policy:
    return Policy(
        name="strict",
        mode="strict",
        rules=[
            PolicyRule(priority=10, scope="tool_id", matcher=tool_id, effect="deny"),
        ],
    )


def _ask_policy(tool_id: str) -> Policy:
    return Policy(
        name="ask",
        mode="ask",
        rules=[
            PolicyRule(priority=10, scope="tool_id", matcher=tool_id, effect="ask"),
        ],
    )


def _dry_only_policy(tool_id: str) -> Policy:
    return Policy(
        name="dry",
        mode="ask",
        rules=[
            PolicyRule(priority=10, scope="tool_id", matcher=tool_id, effect="dry_run_only"),
        ],
    )


# ---------------------------------------------------------------------------
# Step 1: input_schema validation
# ---------------------------------------------------------------------------


async def test_step1_input_schema_failure_raises_validation_error(
    runtime: ToolRuntime, events: InMemoryEventEmitter, factory
):
    tool = _FakeRun()
    with pytest.raises(ValidationError):
        await runtime.invoke(
            tool,
            args={"wrong": "no path"},
            policy=_trusted_policy(),
            run_id="r1",
            run_step_id="s1",
        )
    # No DB writes should have occurred (transaction never entered)
    assert factory.commit_count == 0
    assert factory.rollback_count == 0
    assert len(factory.audit.records) == 0
    assert tool.run_calls == 0
    # Event emitted for tool_call.failed
    assert any(e[0] == "tool_call.failed" for e in events.events)


# ---------------------------------------------------------------------------
# Step 2: Policy evaluation
# ---------------------------------------------------------------------------


async def test_step2_deny_raises_and_records_audit_blocked(
    runtime: ToolRuntime, events: InMemoryEventEmitter, factory
):
    tool = _FakeRun()
    with pytest.raises(PolicyViolationError):
        await runtime.invoke(
            tool,
            args={"path": "/tmp/x"},
            policy=_deny_policy(),
            run_id="r1",
            run_step_id="s1",
        )
    # Audit committed (deferred-error pattern)
    assert factory.commit_count == 1
    assert factory.rollback_count == 0
    assert len(factory.audit.records) == 1
    rec = factory.audit.records[0]
    assert rec.status == "blocked"
    assert rec.policy_decision == "denied"
    # ToolCall recorded as denied
    assert len(factory.tool_calls.calls) == 1
    assert factory.tool_calls.calls[0].policy_decision == "denied"
    # Event emitted
    assert any(e[0] == "tool_call.denied" for e in events.events)
    # Tool run never invoked
    assert tool.run_calls == 0


async def test_step2_ask_produces_approval_pending(
    runtime: ToolRuntime, events: InMemoryEventEmitter, factory
):
    tool = _ReversibleWriteTool()
    result = await runtime.invoke(
        tool,
        args={"path": "/tmp/x", "content": "abc"},
        policy=_ask_policy(tool.id),
        run_id="r1",
        run_step_id="s1",
    )
    assert result.outcome == "approval_pending"
    assert result.approval is not None
    assert factory.commit_count == 1
    assert any(e[0] == "approval.requested" for e in events.events)
    # Tool run NOT invoked (dry preview may or may not be)
    assert tool.run_calls == 0


# ---------------------------------------------------------------------------
# H5: _do_ask dry_run exception classification
# ---------------------------------------------------------------------------


class _AskTimeoutDry(_ReversibleWriteTool):
    """Dry_run raises TimeoutError synchronously."""

    async def dry_run(self, args, ctx):  # type: ignore[override]
        raise TimeoutError("preview took too long")


class _AskOrcaErrorDry(_ReversibleWriteTool):
    """Dry_run raises an OrcaError subclass."""

    async def dry_run(self, args, ctx):  # type: ignore[override]
        from orca_core.errors import ToolRuntimeError

        raise ToolRuntimeError("preview rejected by tool", details={"kind": "preview"})


class _AskGenericDry(_ReversibleWriteTool):
    """Dry_run raises a generic RuntimeError."""

    async def dry_run(self, args, ctx):  # type: ignore[override]
        raise RuntimeError("boom")


async def test_ask_preview_timeout_records_error_in_diff_preview(
    runtime: ToolRuntime, events: InMemoryEventEmitter
):
    """H5 regression: a TimeoutError in dry_run must be surfaced as a
    structured `{preview_error: {kind, message}}` in approval.diff_preview
    rather than silently set to None.
    """
    tool = _AskTimeoutDry()
    result = await runtime.invoke(
        tool,
        args={"path": "/tmp/x", "content": "abc"},
        policy=_ask_policy(tool.id),
        run_id="r1",
        run_step_id="s1",
    )
    assert result.outcome == "approval_pending"
    approval = result.approval
    assert approval is not None
    assert approval.diff_preview is not None
    preview_err = approval.diff_preview.get("preview_error")
    assert preview_err is not None
    assert preview_err["kind"] == "timeout"


async def test_ask_preview_orca_error_recorded_as_tool_error(runtime: ToolRuntime):
    tool = _AskOrcaErrorDry()
    result = await runtime.invoke(
        tool,
        args={"path": "/tmp/x", "content": "abc"},
        policy=_ask_policy(tool.id),
        run_id="r1",
        run_step_id="s1",
    )
    assert result.outcome == "approval_pending"
    assert result.approval is not None
    preview_err = (result.approval.diff_preview or {}).get("preview_error")
    assert preview_err is not None
    assert preview_err["kind"] == "tool_error"
    assert preview_err["code"] == "tool.runtime_error"


async def test_ask_preview_generic_exception_recorded_as_unknown(runtime: ToolRuntime):
    tool = _AskGenericDry()
    result = await runtime.invoke(
        tool,
        args={"path": "/tmp/x", "content": "abc"},
        policy=_ask_policy(tool.id),
        run_id="r1",
        run_step_id="s1",
    )
    assert result.outcome == "approval_pending"
    assert result.approval is not None
    preview_err = (result.approval.diff_preview or {}).get("preview_error")
    assert preview_err is not None
    assert preview_err["kind"] == "unknown"


# ---------------------------------------------------------------------------
# H8: CancelToken mid-run interrupt
# ---------------------------------------------------------------------------


async def test_cancel_token_mid_run_interrupts_long_sleeping_tool():
    """H8 regression: setting cancel_token WHILE a tool is awaiting must
    interrupt it immediately, without waiting for the tool to cooperatively
    call ctx.check_cancel() or the full timeout to elapse.
    """
    import asyncio as _aio
    import time as _time

    from orca_core.errors import ToolCancelledError
    from orca_core.tools import CancelToken

    class _SleepyTool(_ReversibleWriteTool):
        default_dry_run: bool = False
        timeout_ms: int = 30_000  # 30 s — we must not wait this long

        async def dry_run(self, args, ctx):  # type: ignore[override]
            return ToolResult(
                output={"path": args["path"], "bytes_written": 3},
                diff_preview={"existed": False, "new_size": 3},
                before_snapshot={"existed": False, "path": args["path"]},
            )

        async def run(self, args, ctx):  # type: ignore[override]
            # Never calls check_cancel() — the runtime must still interrupt.
            await _aio.sleep(30)
            return ToolResult(output={"path": args["path"], "bytes_written": 3})

    factory = InMemoryTransactionFactory()
    runtime = ToolRuntime(
        transaction_factory=factory,
        audit_log_path=Path("/tmp/_m3_tc_mid/audit.log"),
        journal_base_dir=Path("/tmp/_m3_tc_mid/journal"),
    )
    tool = _SleepyTool()
    token = CancelToken()

    async def _cancel_soon() -> None:
        await _aio.sleep(0.05)
        token.cancel()

    started = _time.monotonic()
    cancel_task = _aio.create_task(_cancel_soon())
    with pytest.raises(ToolCancelledError):
        await runtime.invoke(
            tool,
            args={"path": "/tmp/y", "content": "abc"},
            policy=_trusted_policy(),
            run_id="r1",
            run_step_id="s1",
            cancel_token=token,
        )
    elapsed = _time.monotonic() - started
    await cancel_task
    # Should finish well under 1 second (not 30s timeout).
    assert elapsed < 2.0, f"cancel took too long: {elapsed:.2f}s"
    # Audit row records the failed/cancelled tool call.
    assert any(rec.status == "failed" for rec in factory.audit.records)


async def test_step2_dry_run_only_skips_real_run(
    runtime: ToolRuntime, events: InMemoryEventEmitter, factory
):
    tool = _ReversibleWriteTool()
    result = await runtime.invoke(
        tool,
        args={"path": "/tmp/x", "content": "abc"},
        policy=_dry_only_policy(tool.id),
        run_id="r1",
        run_step_id="s1",
    )
    assert result.outcome == "dry_run"
    assert tool.run_calls == 0
    assert tool.dry_calls == 1
    # Audit recorded with dry_run_only
    assert factory.audit.records[0].policy_decision == "dry_run_only"


# ---------------------------------------------------------------------------
# Step 3: explicit dry_run flag
# ---------------------------------------------------------------------------


async def test_step3_explicit_dry_run_flag_stops_at_preview(runtime: ToolRuntime, factory):
    tool = _FakeRun()
    result = await runtime.invoke(
        tool,
        args={"path": "/tmp/x"},
        policy=_trusted_policy(),
        run_id="r1",
        run_step_id="s1",
        dry_run=True,
    )
    assert result.outcome == "dry_run"
    assert tool.run_calls == 0
    assert tool.dry_calls == 1
    assert factory.tool_calls.calls[0].dry_run is True


async def test_step3_write_tool_runs_dry_preview_before_real_run(runtime: ToolRuntime, factory):
    tool = _ReversibleWriteTool()
    # Caller does not ask for dry_run explicitly, policy is trusted.
    # default_dry_run=True means it's a dry_run flow.
    result = await runtime.invoke(
        tool,
        args={"path": "/tmp/y", "content": "abc"},
        policy=_trusted_policy(),
        run_id="r1",
        run_step_id="s1",
        dry_run=False,  # caller didn't force, but default_dry_run=True
    )
    # default_dry_run True → this is treated as dry_run
    assert result.outcome == "dry_run"
    assert tool.run_calls == 0
    assert tool.dry_calls == 1


async def test_step3_dry_run_failure_records_failed_audit(
    runtime: ToolRuntime, factory, events: InMemoryEventEmitter
):
    # default_dry_run=True; dry_run raises
    tool = _FailingDry()
    result = await runtime.invoke(
        tool,
        args={"path": "/tmp/x", "content": "abc"},
        policy=_trusted_policy(),
        run_id="r1",
        run_step_id="s1",
    )
    assert result.outcome == "failed"
    assert factory.audit.records[0].status == "failed"
    assert tool.run_calls == 0


# ---------------------------------------------------------------------------
# Step 4: Journal record_before (reversible only)
# ---------------------------------------------------------------------------


async def test_step4_journal_before_recorded_for_reversible(runtime: ToolRuntime, factory):
    tool = _ReversibleWriteTool()
    # Force real run by disabling default_dry_run via caller flag override.
    # The easiest: pass dry_run=False AND use a tool that has default_dry_run=True
    # would still produce dry_run. We need to use a custom tool that sets
    # default_dry_run=False but is reversible. Build one inline.

    class _ReversibleAutoRun(_ReversibleWriteTool):
        default_dry_run: bool = False

    tool = _ReversibleAutoRun()
    result = await runtime.invoke(
        tool,
        args={"path": "/tmp/y", "content": "abc"},
        policy=_trusted_policy(),
        run_id="r1",
        run_step_id="s1",
    )
    assert result.outcome == "succeeded"
    assert tool.run_calls == 1
    # Journal recorded before snapshot
    assert len(factory.journal.entries) == 1
    entry = factory.journal.entries[0]
    assert entry.tool_call_id == result.tool_call.id
    assert entry.reversible is True
    assert entry.before is not None


async def test_step4_journal_before_failure_blocks_real_run(
    runtime: ToolRuntime, factory, events: InMemoryEventEmitter
):
    """H4 regression (in-memory variant).

    When journal.record_before raises, the first transaction is rolled
    back (tool.run is not invoked). A second rescue transaction then
    records the blocked audit + tool_call rows so the §5 #1 invariant is
    DB-visible.
    """

    class _ReversibleAutoRun(_ReversibleWriteTool):
        default_dry_run: bool = False

    # Make journal writer raise on insert
    async def failing_insert(entry):
        raise JournalWriteError("simulated disk error")

    factory.journal.insert = failing_insert  # type: ignore[method-assign]

    tool = _ReversibleAutoRun()
    with pytest.raises(ToolRuntimeError, match="journal record_before failed"):
        await runtime.invoke(
            tool,
            args={"path": "/tmp/y", "content": "abc"},
            policy=_trusted_policy(),
            run_id="r1",
            run_step_id="s1",
        )
    # Tool run was NOT invoked (fail-closed)
    assert tool.run_calls == 0
    # Rescue transaction committed: one blocked audit + one blocked tool_call.
    assert len(factory.audit.records) == 1
    assert factory.audit.records[0].status == "blocked"
    assert len(factory.tool_calls.calls) == 1
    assert factory.tool_calls.calls[0].error is not None
    assert factory.tool_calls.calls[0].error["phase"] == "journal_before"
    assert factory.tool_calls.calls[0].audit_log_id == factory.audit.records[0].id
    # Event emitted for failure
    assert any(e[0] == "tool_call.failed" for e in events.events)


# ---------------------------------------------------------------------------
# Step 5: Tool.run() failure
# ---------------------------------------------------------------------------


async def test_step5_run_failure_records_audit_failed(
    runtime: ToolRuntime, factory, events: InMemoryEventEmitter
):
    class _FailingAutoRun(_FailingRun):
        default_dry_run: bool = False

    tool = _FailingAutoRun()
    result = await runtime.invoke(
        tool,
        args={"path": "/tmp/y", "content": "abc"},
        policy=_trusted_policy(),
        run_id="r1",
        run_step_id="s1",
    )
    assert result.outcome == "failed"
    assert factory.audit.records[-1].status == "failed"
    assert any(e[0] == "tool_call.failed" for e in events.events)


# ---------------------------------------------------------------------------
# Step 6+7: Success path and audit + events
# ---------------------------------------------------------------------------


async def test_full_success_path_commits_audit_journal_tool_call_and_emits(
    runtime: ToolRuntime, factory, events: InMemoryEventEmitter
):
    class _ReversibleAutoRun(_ReversibleWriteTool):
        default_dry_run: bool = False

    tool = _ReversibleAutoRun()
    result = await runtime.invoke(
        tool,
        args={"path": "/tmp/y", "content": "abc"},
        policy=_trusted_policy(),
        run_id="r1",
        run_step_id="s1",
    )
    assert result.outcome == "succeeded"
    assert tool.run_calls == 1
    # All three: audit / journal / tool_call
    assert len(factory.audit.records) == 1
    assert len(factory.journal.entries) == 1
    assert len(factory.tool_calls.calls) == 1
    assert factory.audit.records[0].status == "success"
    # H3: ToolCall row has result/duration/audit_log_id back-filled.
    stored = factory.tool_calls.calls[0]
    assert stored.result is not None
    assert stored.duration_ms is not None
    assert stored.audit_log_id == factory.audit.records[0].id
    # Event emitted post-commit
    assert events.events[-1][0] == "tool_call.succeeded"


# ---------------------------------------------------------------------------
# Non-reversible read success
# ---------------------------------------------------------------------------


async def test_read_only_tool_succeeds_without_journal(
    runtime: ToolRuntime, factory, events: InMemoryEventEmitter
):
    tool = _FakeRun()
    result = await runtime.invoke(
        tool,
        args={"path": "/tmp/x"},
        policy=_trusted_policy(),
        run_id="r1",
        run_step_id="s1",
    )
    assert result.outcome == "succeeded"
    assert len(factory.journal.entries) == 0
    assert len(factory.audit.records) == 1


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------


async def test_cancel_token_cancels_before_run():
    """H8: cancel_token set before invoke must prevent tool.run() from
    running. The runtime raises `ToolCancelledError` (not plain
    CancelledError) so callers can distinguish user-initiated cancel from
    generic asyncio cancellation.
    """
    from orca_core.errors import ToolCancelledError
    from orca_core.tools import CancelToken

    factory = InMemoryTransactionFactory()
    runtime = ToolRuntime(
        transaction_factory=factory,
        audit_log_path=Path("/tmp/_m3_tc/audit.log"),
        journal_base_dir=Path("/tmp/_m3_tc/journal"),
    )

    class _ReversibleAutoRun(_ReversibleWriteTool):
        default_dry_run: bool = False

    tool = _ReversibleAutoRun()
    token = CancelToken()
    token.cancel()

    with pytest.raises(ToolCancelledError):
        await runtime.invoke(
            tool,
            args={"path": "/tmp/y", "content": "abc"},
            policy=_trusted_policy(),
            run_id="r1",
            run_step_id="s1",
            cancel_token=token,
        )
    # tool never ran
    assert tool.run_calls == 0


async def test_approval_override_emits_policy_downgrade_event(
    runtime: ToolRuntime, events: InMemoryEventEmitter
):
    """H15: `approval_override=True` must emit `policy.downgraded_by_approval`
    as an audit trail, with the original rule_id + reason. The event is
    emitted after transaction commit regardless of dry vs real execution.
    """
    tool = _ReversibleWriteTool()
    result = await runtime.invoke(
        tool,
        args={"path": "/tmp/x", "content": "abc"},
        policy=_ask_policy(tool.id),
        run_id="r1",
        run_step_id="s1",
        approval_override=True,
    )
    # Default_dry_run=True on _ReversibleWriteTool so outcome is dry_run,
    # but the policy downgrade must still be audited.
    assert result.outcome in ("succeeded", "dry_run")
    downgrade = [e for e in events.events if e[0] == "policy.downgraded_by_approval"]
    assert len(downgrade) == 1
    payload = downgrade[0][1]
    assert payload["tool_id"] == tool.id
    assert payload["run_id"] == "r1"
    assert payload["run_step_id"] == "s1"
    assert "original_rule_id" in payload
    assert "original_reason" in payload
