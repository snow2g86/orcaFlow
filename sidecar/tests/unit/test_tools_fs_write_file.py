"""fs.write_file 툴 테스트 — dry_run, atomic write, journal.before."""

from __future__ import annotations

from pathlib import Path

import pytest

from orca_core.schema import Policy, PolicyRule
from orca_core.tools import InMemoryEventEmitter, ToolRuntime
from orca_core.tools.fs import FsWriteFileTool

from ._m3_helpers import (
    InMemoryTransactionFactory,
    make_audit_log_path,
    make_journal_base,
)


@pytest.fixture
def runtime(
    tmp_path: Path,
) -> tuple[ToolRuntime, InMemoryTransactionFactory]:
    factory = InMemoryTransactionFactory()
    rt = ToolRuntime(
        transaction_factory=factory,
        audit_log_path=make_audit_log_path(tmp_path),
        journal_base_dir=make_journal_base(tmp_path),
        events=InMemoryEventEmitter(),
    )
    return rt, factory


# A permissive policy that allows fs.write_file (policy.mode=ask by default would ask)
def _allow_write_policy() -> Policy:
    return Policy(
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
    )


async def test_default_dry_run_stops_before_writing(tmp_path: Path, runtime):
    rt, factory = runtime
    target = tmp_path / "new.txt"
    result = await rt.invoke(
        FsWriteFileTool(),
        args={"path": str(target), "content": "hello"},
        policy=_allow_write_policy(),
        run_id="r1",
        run_step_id="s1",
    )
    assert result.outcome == "dry_run"
    assert not target.exists()
    assert factory.tool_calls.calls[0].dry_run is True


async def test_explicit_dry_run_false_writes_file(tmp_path: Path, runtime):
    rt, factory = runtime
    target = tmp_path / "new.txt"

    # Override default_dry_run by subclassing the tool
    class _AutoRunWrite(FsWriteFileTool):
        default_dry_run: bool = False

    result = await rt.invoke(
        _AutoRunWrite(),
        args={"path": str(target), "content": "hello world"},
        policy=_allow_write_policy(),
        run_id="r1",
        run_step_id="s1",
    )
    assert result.outcome == "succeeded"
    assert target.read_text() == "hello world"
    # Journal entry recorded (reversible=True)
    assert len(factory.journal.entries) == 1
    # Before snapshot should have existed=False
    before = factory.journal.entries[0].before
    assert before is not None
    assert before["existed"] is False


async def test_overwrites_existing_and_records_before(tmp_path: Path, runtime):
    rt, factory = runtime
    target = tmp_path / "exists.txt"
    target.write_text("old content")

    class _AutoRunWrite(FsWriteFileTool):
        default_dry_run: bool = False

    result = await rt.invoke(
        _AutoRunWrite(),
        args={"path": str(target), "content": "new content"},
        policy=_allow_write_policy(),
        run_id="r1",
        run_step_id="s1",
    )
    assert result.outcome == "succeeded"
    assert target.read_text() == "new content"
    # Journal before contains old content
    before = factory.journal.entries[0].before
    assert before is not None
    assert before["existed"] is True
    assert before["content"] == "old content"


async def test_unreadable_existing_file_blocks_execution(tmp_path: Path, runtime):
    """H10 regression: when the existing file cannot be read due to a
    permission/OS error, dry_run must surface a ToolRuntimeError so
    execution is blocked — never silently record `existed=False` and
    destroy the original file.

    We use a stub ToolIo that raises PermissionError to avoid relying on
    platform-specific chmod behaviour.
    """
    from orca_core.audit.sink import AuditSink
    from orca_core.errors import ToolRuntimeError
    from orca_core.journal.store import JournalStore
    from orca_core.policy.engine import PolicyEngine
    from orca_core.tools._base import CancelToken, InMemoryEventEmitter, ToolContext, ToolIo

    class _PermIo(ToolIo):
        async def exists(self, path):  # type: ignore[override]
            return True

        async def stat_size(self, path):  # type: ignore[override]
            return 42

        async def read_bytes(self, path, *, max_bytes):  # type: ignore[override]
            raise PermissionError("simulated: cannot read sealed file")

    ctx = ToolContext(
        run_id="r",
        run_step_id="s",
        tool_call_id="tc",
        policy_engine=PolicyEngine(),
        journal=JournalStore(base_dir=tmp_path / "journal"),
        audit=AuditSink(log_path=tmp_path / "audit.log"),
        events=InMemoryEventEmitter(),
        secret_store=None,
        io=_PermIo(),
        cancel_token=CancelToken(),
        dry_run=True,
    )
    tool = FsWriteFileTool()
    with pytest.raises(ToolRuntimeError, match="unreadable"):
        await tool.dry_run(
            {"path": str(tmp_path / "sealed.txt"), "content": "overwrite"},
            ctx,
        )


async def test_oversize_existing_file_flags_snapshot_incomplete(tmp_path: Path, runtime):
    """H10 regression: when the existing file exceeds the 50 MiB snapshot
    cap, dry_run must record `snapshot_complete=False` and continue. The
    real run still proceeds under the assumption that the user explicitly
    approved after reviewing the preview — but the journal.before carries
    the cap flag so restore can refuse.

    We simulate this without creating a 60 MiB file by injecting a
    ToolIo that raises ValueError (the signal the real read_bytes would
    give when the cap is hit).
    """
    from orca_core.tools import ToolIo
    from orca_core.tools._base import CancelToken
    from orca_core.tools.fs.write_file import FsWriteFileTool

    class _CapTriggerIo(ToolIo):
        async def read_bytes(self, path, *, max_bytes):  # type: ignore[override]
            raise ValueError("file too large: simulated 60 MiB")

        async def sha256_file(self, path, *, chunk_size: int = 65536):  # type: ignore[override]
            return "deadbeef" * 8

        async def stat_size(self, path):  # type: ignore[override]
            return 60 * 1024 * 1024

        async def exists(self, path):  # type: ignore[override]
            return True

    # Directly exercise dry_run with the stub IO — the tool's own logic is
    # what matters here.
    target = tmp_path / "huge.bin"
    tool = FsWriteFileTool()
    from orca_core.audit.sink import AuditSink
    from orca_core.journal.store import JournalStore
    from orca_core.policy.engine import PolicyEngine
    from orca_core.tools._base import InMemoryEventEmitter, ToolContext

    ctx = ToolContext(
        run_id="r",
        run_step_id="s",
        tool_call_id="tc",
        policy_engine=PolicyEngine(),
        journal=JournalStore(base_dir=tmp_path / "journal"),
        audit=AuditSink(log_path=tmp_path / "audit.log"),
        events=InMemoryEventEmitter(),
        secret_store=None,
        io=_CapTriggerIo(),
        cancel_token=CancelToken(),
        dry_run=True,
    )
    result = await tool.dry_run(
        {"path": str(target), "content": "updated"},
        ctx,
    )
    assert result.before_snapshot is not None
    assert result.before_snapshot["existed"] is True
    assert result.before_snapshot["snapshot_complete"] is False
    assert result.before_snapshot["content"] is None
    assert result.before_snapshot["sha256"] == "deadbeef" * 8
    assert result.diff_preview is not None
    assert result.diff_preview["snapshot_complete"] is False


async def test_atomic_write_uses_tmp_file(tmp_path: Path, runtime):
    """Atomic write should leave no .orca-tmp stragglers."""
    rt, _ = runtime
    target = tmp_path / "atomic.txt"

    class _AutoRunWrite(FsWriteFileTool):
        default_dry_run: bool = False

    await rt.invoke(
        _AutoRunWrite(),
        args={"path": str(target), "content": "atomic"},
        policy=_allow_write_policy(),
        run_id="r1",
        run_step_id="s1",
    )
    assert target.read_text() == "atomic"
    # no .orca-tmp leftover
    leftover = list(tmp_path.glob("*.orca-tmp"))
    assert leftover == []
