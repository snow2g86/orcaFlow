"""shell.exec 툴 테스트."""

from __future__ import annotations

from pathlib import Path

import pytest

from orca_core.errors import ToolRuntimeError
from orca_core.schema import Policy
from orca_core.tools import InMemoryEventEmitter, ToolRuntime
from orca_core.tools.shell import ShellExecTool

from ._m3_helpers import InMemoryTransactionFactory, make_audit_log_path, make_journal_base


def _exec_tool(*, dry_run_default: bool = False) -> ShellExecTool:
    """테스트용 ShellExecTool — default_dry_run 을 낮출 수 있다."""
    tool = ShellExecTool()
    tool.default_dry_run = dry_run_default
    return tool


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


async def test_dry_run_parses_command(tmp_path: Path, runtime):
    rt, _ = runtime
    result = await rt.invoke(
        ShellExecTool(),
        args={"cmd": "echo hello world"},
        policy=Policy(name="t", mode="trusted"),
        run_id="r1",
        run_step_id="s1",
        dry_run=True,
    )
    assert result.outcome == "dry_run"
    out = result.result.output
    assert out["parsed_cmd"] == ["echo", "hello", "world"]
    assert out["dry_run"] is True


async def test_default_dry_run_honored(tmp_path: Path, runtime):
    """default_dry_run=True 이면 approval_override 없이도 dry_run 결과."""
    rt, _ = runtime
    result = await rt.invoke(
        ShellExecTool(),  # default_dry_run=True
        args={"cmd": "echo hello"},
        policy=Policy(name="t", mode="trusted"),
        run_id="r1",
        run_step_id="s1",
    )
    assert result.outcome == "dry_run"


async def test_runs_echo_command(tmp_path: Path, runtime):
    rt, _ = runtime
    result = await rt.invoke(
        _exec_tool(),
        args={"cmd": "echo hello"},
        policy=Policy(name="t", mode="trusted"),
        run_id="r1",
        run_step_id="s1",
    )
    assert result.outcome == "succeeded"
    assert "hello" in result.result.output["stdout"]
    assert result.result.output["exit_code"] == 0
    assert result.result.output["timed_out"] is False


async def test_captures_exit_code(tmp_path: Path, runtime):
    rt, _ = runtime
    result = await rt.invoke(
        _exec_tool(),
        args={"cmd": "false"},
        policy=Policy(name="t", mode="trusted"),
        run_id="r1",
        run_step_id="s1",
    )
    assert result.outcome == "succeeded"
    assert result.result.output["exit_code"] != 0


async def test_rejects_secret_env_keys(tmp_path: Path, runtime):
    rt, _ = runtime
    result = await rt.invoke(
        _exec_tool(),
        args={"cmd": "echo test", "env": {"MY_API_KEY": "secret123"}},
        policy=Policy(name="t", mode="trusted"),
        run_id="r1",
        run_step_id="s1",
    )
    # ToolRuntimeError from secret env -> "failed"
    assert result.outcome == "failed"


async def test_timeout_enforcement(tmp_path: Path, runtime):
    rt, _ = runtime
    result = await rt.invoke(
        _exec_tool(),
        args={"cmd": "sleep 10", "timeout_seconds": 1},
        policy=Policy(name="t", mode="trusted"),
        run_id="r1",
        run_step_id="s1",
    )
    assert result.outcome == "succeeded"
    assert result.result.output["timed_out"] is True


async def test_cwd_expansion(tmp_path: Path, runtime):
    rt, _ = runtime
    result = await rt.invoke(
        _exec_tool(),
        args={"cmd": "pwd", "cwd": str(tmp_path)},
        policy=Policy(name="t", mode="trusted"),
        run_id="r1",
        run_step_id="s1",
    )
    assert result.outcome == "succeeded"
    assert str(tmp_path) in result.result.output["stdout"]


async def test_stdout_truncation(tmp_path: Path, runtime):
    rt, _ = runtime
    tool = _exec_tool()
    tool.max_output_bytes = 100
    result = await rt.invoke(
        tool,
        args={"cmd": "python3 -c \"print('x' * 1000)\""},
        policy=Policy(name="t", mode="trusted"),
        run_id="r1",
        run_step_id="s1",
    )
    assert result.outcome == "succeeded"
    assert result.result.output["truncated"] is True
    assert len(result.result.output["stdout"]) <= 200  # approximate


async def test_secret_pattern_variations():
    """다양한 시크릿 키 패턴이 거부되는지 확인."""
    from orca_core.tools.shell.exec import _check_secret_env

    with pytest.raises(ToolRuntimeError):
        _check_secret_env({"API_KEY": "val"})
    with pytest.raises(ToolRuntimeError):
        _check_secret_env({"auth_token": "val"})
    with pytest.raises(ToolRuntimeError):
        _check_secret_env({"MY_SECRET": "val"})
    with pytest.raises(ToolRuntimeError):
        _check_secret_env({"password": "val"})

    # Should not raise
    _check_secret_env({"PATH": "/usr/bin"})
    _check_secret_env({"HOME": "/home/user"})
    _check_secret_env(None)
