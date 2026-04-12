"""fs.list 툴 테스트."""

from __future__ import annotations

from pathlib import Path

import pytest

from orca_core.schema import Policy
from orca_core.tools import InMemoryEventEmitter, ToolRuntime
from orca_core.tools.fs import FsListTool

from ._m3_helpers import (
    InMemoryTransactionFactory,
    make_audit_log_path,
    make_journal_base,
)


@pytest.fixture
def runtime(tmp_path: Path) -> ToolRuntime:
    factory = InMemoryTransactionFactory()
    return ToolRuntime(
        transaction_factory=factory,
        audit_log_path=make_audit_log_path(tmp_path),
        journal_base_dir=make_journal_base(tmp_path),
        events=InMemoryEventEmitter(),
    )


async def test_lists_files_and_dirs(tmp_path: Path, runtime: ToolRuntime):
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / "b.log").write_text("y")
    (tmp_path / "sub").mkdir()

    result = await runtime.invoke(
        FsListTool(),
        args={"path": str(tmp_path)},
        policy=Policy(name="t", mode="trusted"),
        run_id="r1",
        run_step_id="s1",
    )
    assert result.outcome == "succeeded"
    entries = result.result.output["entries"]
    names = {e["name"] for e in entries}
    assert names == {"a.txt", "b.log", "sub"}
    # check kinds
    kinds = {e["name"]: e["kind"] for e in entries}
    assert kinds["sub"] == "dir"
    assert kinds["a.txt"] == "file"


async def test_glob_filter(tmp_path: Path, runtime: ToolRuntime):
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / "b.log").write_text("y")
    result = await runtime.invoke(
        FsListTool(),
        args={"path": str(tmp_path), "glob": "*.txt"},
        policy=Policy(name="t", mode="trusted"),
        run_id="r1",
        run_step_id="s1",
    )
    names = {e["name"] for e in result.result.output["entries"]}
    assert names == {"a.txt"}


async def test_explicit_dry_run_reports_exists(tmp_path: Path, runtime: ToolRuntime):
    result = await runtime.invoke(
        FsListTool(),
        args={"path": str(tmp_path)},
        policy=Policy(name="t", mode="trusted"),
        run_id="r1",
        run_step_id="s1",
        dry_run=True,
    )
    assert result.outcome == "dry_run"
    assert result.result.output["exists"] is True


async def test_max_entries_truncates(tmp_path: Path, runtime: ToolRuntime):
    for i in range(10):
        (tmp_path / f"f{i}.txt").write_text(str(i))
    result = await runtime.invoke(
        FsListTool(),
        args={"path": str(tmp_path), "max_entries": 3},
        policy=Policy(name="t", mode="trusted"),
        run_id="r1",
        run_step_id="s1",
    )
    assert result.result.output["truncated"] is True
    assert len(result.result.output["entries"]) == 3
