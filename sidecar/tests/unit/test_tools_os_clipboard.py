"""os.clipboard_read / os.clipboard_write 툴 테스트."""

from __future__ import annotations

from pathlib import Path
import sys
from unittest.mock import patch

import pytest

from orca_core.schema import Policy
from orca_core.tools import InMemoryEventEmitter, ToolIo, ToolRuntime
from orca_core.tools.os import OsClipboardReadTool, OsClipboardWriteTool
from orca_core.tools.os.clipboard import _read_cmd

from ._m3_helpers import InMemoryTransactionFactory, make_audit_log_path, make_journal_base


@pytest.fixture
def runtime(tmp_path: Path) -> tuple[ToolRuntime, InMemoryTransactionFactory]:
    factory = InMemoryTransactionFactory()
    # Use a mock ToolIo that intercepts subprocess calls
    io = ToolIo()
    rt = ToolRuntime(
        transaction_factory=factory,
        audit_log_path=make_audit_log_path(tmp_path),
        journal_base_dir=make_journal_base(tmp_path),
        events=InMemoryEventEmitter(),
        io=io,
    )
    return rt, factory


def test_read_cmd_macos():
    with patch.object(sys, "platform", "darwin"):
        cmd = _read_cmd()
        assert cmd == ["pbpaste"]


def test_read_cmd_linux():
    with patch.object(sys, "platform", "linux"):
        cmd = _read_cmd()
        assert "xclip" in cmd


def test_read_cmd_windows():
    with patch.object(sys, "platform", "win32"):
        cmd = _read_cmd()
        assert cmd[0] == "powershell"


async def test_clipboard_read_dry_run(tmp_path: Path, runtime):
    rt, _ = runtime
    result = await rt.invoke(
        OsClipboardReadTool(),
        args={},
        policy=Policy(name="t", mode="trusted"),
        run_id="r1",
        run_step_id="s1",
        dry_run=True,
    )
    assert result.outcome == "dry_run"


async def test_clipboard_write_dry_run(tmp_path: Path, runtime):
    rt, _ = runtime
    result = await rt.invoke(
        OsClipboardWriteTool(),
        args={"content": "test data"},
        policy=Policy(name="t", mode="trusted"),
        run_id="r1",
        run_step_id="s1",
        dry_run=True,
    )
    assert result.outcome == "dry_run"


async def test_clipboard_read_with_mock(tmp_path: Path, runtime):
    """subprocess mock 으로 클립보드 읽기 테스트."""
    rt, _ = runtime
    io = rt._io

    original_run = io.run_subprocess

    async def mock_subprocess(cmd, **kwargs):
        if cmd == ["pbpaste"] or "xclip" in cmd or "Get-Clipboard" in str(cmd):
            return {
                "stdout": "clipboard content",
                "stderr": "",
                "exit_code": 0,
                "timed_out": False,
                "truncated": False,
            }
        return await original_run(cmd, **kwargs)

    with patch.object(io, "run_subprocess", side_effect=mock_subprocess):
        result = await rt.invoke(
            OsClipboardReadTool(),
            args={},
            policy=Policy(name="t", mode="trusted"),
            run_id="r1",
            run_step_id="s1",
        )
        assert result.outcome == "succeeded"
        assert result.result.output["content"] == "clipboard content"
