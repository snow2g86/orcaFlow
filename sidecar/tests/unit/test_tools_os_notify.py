"""os.notify 툴 테스트."""

from __future__ import annotations

from pathlib import Path
import sys
from unittest.mock import patch

import pytest

from orca_core.schema import Policy
from orca_core.tools import InMemoryEventEmitter, ToolRuntime
from orca_core.tools.os import OsNotifyTool
from orca_core.tools.os.notify import _build_notify_cmd

from ._m3_helpers import InMemoryTransactionFactory, make_audit_log_path, make_journal_base


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


def test_macos_notify_cmd():
    with patch.object(sys, "platform", "darwin"):
        cmd = _build_notify_cmd("Test", "Hello")
        assert cmd[0] == "osascript"
        assert "-e" in cmd


def test_linux_notify_cmd():
    with patch.object(sys, "platform", "linux"):
        cmd = _build_notify_cmd("Test", "Hello")
        assert cmd[0] == "notify-send"


def test_windows_notify_cmd():
    with patch.object(sys, "platform", "win32"):
        cmd = _build_notify_cmd("Test", "Hello")
        assert cmd[0] == "powershell"


def test_unsupported_platform_raises():
    from orca_core.errors import ToolRuntimeError

    with patch.object(sys, "platform", "freebsd"):
        with pytest.raises(ToolRuntimeError, match="unsupported platform"):
            _build_notify_cmd("Test", "Hello")


async def test_dry_run(tmp_path: Path, runtime):
    rt, _ = runtime
    result = await rt.invoke(
        OsNotifyTool(),
        args={"title": "Test", "message": "Hello World"},
        policy=Policy(name="t", mode="trusted"),
        run_id="r1",
        run_step_id="s1",
        dry_run=True,
    )
    assert result.outcome == "dry_run"
    assert result.result.output["title"] == "Test"
