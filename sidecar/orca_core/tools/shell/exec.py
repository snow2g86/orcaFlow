"""shell.exec — 셸 명령 실행 (destructive, non-reversible, dry_run=True).

conventions.md §8.3: `subprocess.run(shell=False)` + `shlex.split(cmd)`.
시크릿 키가 env 에 포함되면 거부한다. 타임아웃은 기본 30초, 최대 300초.
"""

from __future__ import annotations

from pathlib import Path
import re
import shlex
from typing import Any, ClassVar

from ...errors import ToolRuntimeError
from ...schema.tool import Permission, SideEffect, ToolNamespace
from .._base import ToolContext, ToolResult

__all__ = ["ShellExecTool"]

_DEFAULT_TIMEOUT = 30
_MAX_TIMEOUT = 300
_MAX_OUTPUT_BYTES = 1 * 1024 * 1024

# Secret key patterns to reject in env
_SECRET_PATTERNS = re.compile(
    r"(api[_-]?key|secret|token|password|credential|auth)",
    re.IGNORECASE,
)


class ShellExecTool:
    """셸 명령 실행 툴."""

    id: str = "shell.exec"
    namespace: ClassVar[ToolNamespace] = "shell"
    name: str = "exec"
    side_effect: ClassVar[SideEffect] = "destructive"
    reversible: bool = False
    default_dry_run: bool = True
    timeout_ms: int = _DEFAULT_TIMEOUT * 1000
    max_output_bytes: int = _MAX_OUTPUT_BYTES

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["cmd"],
            "properties": {
                "cmd": {"type": "string", "minLength": 1},
                "cwd": {"type": ["string", "null"]},
                "env": {"type": ["object", "null"]},
                "timeout_seconds": {
                    "type": ["integer", "null"],
                    "minimum": 1,
                    "maximum": _MAX_TIMEOUT,
                },
            },
            "additionalProperties": False,
        }

    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["stdout", "stderr", "exit_code", "timed_out"],
            "properties": {
                "stdout": {"type": "string"},
                "stderr": {"type": "string"},
                "exit_code": {"type": "integer"},
                "timed_out": {"type": "boolean"},
                "truncated": {"type": "boolean"},
            },
        }

    def permissions(self) -> list[Permission]:
        return [Permission(kind="shell_command", scope="*", action="execute")]

    async def dry_run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        cmd_str: str = args["cmd"]
        parsed = shlex.split(cmd_str)
        cwd = args.get("cwd")
        env = args.get("env")
        timeout = min(args.get("timeout_seconds") or _DEFAULT_TIMEOUT, _MAX_TIMEOUT)

        _check_secret_env(env)

        resolved_cwd = str(Path(cwd).expanduser().resolve()) if cwd else None

        return ToolResult(
            output={
                "parsed_cmd": parsed,
                "cwd": resolved_cwd,
                "timeout_seconds": timeout,
                "env_keys": sorted(env.keys()) if env else [],
                "dry_run": True,
            },
            diff_preview={
                "preview": f"Would execute: {parsed}",
                "cwd": resolved_cwd,
                "timeout_seconds": timeout,
            },
            side_effects=["would execute shell command"],
        )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        cmd_str: str = args["cmd"]
        parsed = shlex.split(cmd_str)
        cwd_raw = args.get("cwd")
        env = args.get("env")
        timeout = min(args.get("timeout_seconds") or _DEFAULT_TIMEOUT, _MAX_TIMEOUT)

        _check_secret_env(env)

        cwd = Path(cwd_raw).expanduser().resolve() if cwd_raw else None

        result = await ctx.io.run_subprocess(
            parsed,
            cwd=cwd,
            env=env,
            timeout_seconds=timeout,
            max_output_bytes=self.max_output_bytes,
        )

        return ToolResult(
            output={
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "exit_code": result["exit_code"],
                "timed_out": result["timed_out"],
                "truncated": result.get("truncated", False),
            },
            side_effects=["executed shell command"],
        )


def _check_secret_env(env: dict[str, str] | None) -> None:
    """env 딕셔너리에 시크릿 키 패턴이 있으면 ToolRuntimeError raise."""
    if not env:
        return
    for key in env:
        if _SECRET_PATTERNS.search(key):
            raise ToolRuntimeError(
                f"env key '{key}' matches secret pattern — use secret store instead",
                details={"rejected_key": key},
            )
