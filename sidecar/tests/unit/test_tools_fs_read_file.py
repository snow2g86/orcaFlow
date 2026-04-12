"""fs.read_file 툴 테스트."""

from __future__ import annotations

from pathlib import Path

import pytest

from orca_core.schema import Policy
from orca_core.tools import InMemoryEventEmitter, ToolRuntime
from orca_core.tools.fs import FsReadFileTool

from ._m3_helpers import (
    InMemoryTransactionFactory,
    make_audit_log_path,
    make_journal_base,
)


@pytest.fixture
def runtime(tmp_path: Path) -> tuple[ToolRuntime, InMemoryTransactionFactory]:
    factory = InMemoryTransactionFactory()
    rt = ToolRuntime(
        transaction_factory=factory,
        audit_log_path=make_audit_log_path(tmp_path),
        journal_base_dir=make_journal_base(tmp_path),
        events=InMemoryEventEmitter(),
    )
    return rt, factory


async def test_reads_utf8_text_file(tmp_path: Path, runtime):
    rt, _ = runtime
    target = tmp_path / "hello.txt"
    target.write_text("hello world", encoding="utf-8")
    result = await rt.invoke(
        FsReadFileTool(),
        args={"path": str(target)},
        policy=Policy(name="t", mode="trusted"),
        run_id="r1",
        run_step_id="s1",
    )
    assert result.outcome == "succeeded"
    out = result.result.output
    assert out["content"] == "hello world"
    assert out["encoding"] == "utf-8"
    assert out["size_bytes"] == 11


async def test_reads_binary_as_base64(tmp_path: Path, runtime):
    rt, _ = runtime
    target = tmp_path / "bin.dat"
    target.write_bytes(b"\xff\xfe\x00\x01")
    result = await rt.invoke(
        FsReadFileTool(),
        args={"path": str(target)},
        policy=Policy(name="t", mode="trusted"),
        run_id="r1",
        run_step_id="s1",
    )
    assert result.outcome == "succeeded"
    assert result.result.output["encoding"] == "base64"


async def test_raises_when_file_too_large(tmp_path: Path, runtime):
    rt, _ = runtime
    target = tmp_path / "big.bin"
    target.write_bytes(b"x" * 200)
    result = await rt.invoke(
        FsReadFileTool(),
        args={"path": str(target), "max_bytes": 10},
        policy=Policy(name="t", mode="trusted"),
        run_id="r1",
        run_step_id="s1",
    )
    # max_bytes exceeded → underlying ValueError → failed
    assert result.outcome == "failed"
