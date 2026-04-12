"""fs.delete 툴 테스트 — 휴지통 경유, 복구, 체크섬."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from orca_core.schema import Policy, PolicyRule
from orca_core.tools import InMemoryEventEmitter, ToolIo, ToolRuntime
from orca_core.tools.fs import FsDeleteTool

from ._m3_helpers import (
    InMemoryTransactionFactory,
    make_audit_log_path,
    make_journal_base,
)


@pytest.fixture
def runtime(tmp_path: Path):
    factory = InMemoryTransactionFactory()
    trash_root = tmp_path / "trash"
    rt = ToolRuntime(
        transaction_factory=factory,
        audit_log_path=make_audit_log_path(tmp_path),
        journal_base_dir=make_journal_base(tmp_path),
        events=InMemoryEventEmitter(),
        io=ToolIo(trash_root=trash_root),
    )
    return rt, factory, trash_root


def _allow_delete() -> Policy:
    return Policy(
        name="allow-delete",
        mode="ask",
        rules=[
            PolicyRule(priority=10, scope="tool_id", matcher="fs.delete", effect="allow"),
        ],
    )


async def test_default_dry_run_does_not_touch_file(tmp_path: Path, runtime):
    rt, _factory, _ = runtime
    target = tmp_path / "victim.txt"
    target.write_text("please don't delete me")

    result = await rt.invoke(
        FsDeleteTool(),
        args={"path": str(target)},
        policy=_allow_delete(),
        run_id="r1",
        run_step_id="s1",
    )
    assert result.outcome == "dry_run"
    assert target.exists()


async def test_real_delete_moves_file_to_trash_and_records_journal(tmp_path: Path, runtime):
    rt, factory, _trash_root = runtime
    target = tmp_path / "data.txt"
    target.write_text("trash me")

    class _AutoDelete(FsDeleteTool):
        default_dry_run: bool = False

    result = await rt.invoke(
        _AutoDelete(),
        args={"path": str(target)},
        policy=_allow_delete(),
        run_id="run-1",
        run_step_id="step-1",
    )
    assert result.outcome == "succeeded"
    assert not target.exists()
    # Trash has it
    trashed = result.result.output["trashed_to"]
    assert Path(trashed).exists()
    assert Path(trashed).read_text() == "trash me"
    # Journal recorded
    assert len(factory.journal.entries) == 1
    # Checksum sha256 matches
    expected = hashlib.sha256(b"trash me").hexdigest()
    assert result.result.output["checksum"] == expected


async def test_delete_large_file_over_1mib_still_succeeds(tmp_path: Path, runtime):
    """H2 regression: fs.delete previously loaded the entire file into
    memory via `read_bytes(max_bytes=1MiB)` which blocked deletion of any
    file larger than 1 MiB. After fix, sha256 is computed via chunked
    streaming so arbitrarily large files can be sent to trash and restored.
    """
    import hashlib as _hashlib

    rt, _factory, _trash_root = runtime
    target = tmp_path / "big.bin"
    # 2 MiB payload — 1 MiB + 1 MiB with a distinct marker so we can
    # detect corruption on restore.
    payload = (b"A" * (1024 * 1024)) + (b"B" * (1024 * 1024))
    target.write_bytes(payload)
    expected_sha = _hashlib.sha256(payload).hexdigest()

    class _AutoDelete(FsDeleteTool):
        default_dry_run: bool = False

    result = await rt.invoke(
        _AutoDelete(),
        args={"path": str(target)},
        policy=_allow_delete(),
        run_id="run-big",
        run_step_id="step-big",
    )
    assert result.outcome == "succeeded"
    assert not target.exists()
    trashed = Path(result.result.output["trashed_to"])
    assert trashed.exists()
    assert result.result.output["size_bytes"] == len(payload)
    assert result.result.output["checksum"] == expected_sha

    # Restore and verify sha256 still matches (end-to-end integrity).
    io = rt._io  # type: ignore[attr-defined]
    await io.restore_from_trash(trashed, target)
    assert target.exists()
    assert _hashlib.sha256(target.read_bytes()).hexdigest() == expected_sha


async def test_restore_from_trash_recovers_file(tmp_path: Path, runtime):
    rt, _factory, _trash_root = runtime
    target = tmp_path / "recover.txt"
    target.write_text("original content")

    class _AutoDelete(FsDeleteTool):
        default_dry_run: bool = False

    result = await rt.invoke(
        _AutoDelete(),
        args={"path": str(target)},
        policy=_allow_delete(),
        run_id="run-x",
        run_step_id="step-x",
    )
    trashed_path = Path(result.result.output["trashed_to"])
    assert not target.exists()
    assert trashed_path.exists()

    # Restore using the ToolIo helper directly (what undo flow would do)
    io = rt._io  # type: ignore[attr-defined]
    await io.restore_from_trash(trashed_path, target)

    assert target.exists()
    assert target.read_text() == "original content"
    # Checksum still matches
    assert hashlib.sha256(target.read_bytes()).hexdigest() == result.result.output["checksum"]
