"""os.applescript — macOS AppleScript 실행 (destructive, dry_run=True).

macOS 전용. 다른 플랫폼에서는 ToolRuntimeError.
"""

from __future__ import annotations

import sys
from typing import Any, ClassVar

from ...errors import ToolRuntimeError
from ...schema.tool import Permission, SideEffect, ToolNamespace
from .._base import ToolContext, ToolResult

__all__ = ["OsAppleScriptTool"]


class OsAppleScriptTool:
    """macOS AppleScript 실행 툴."""

    id: str = "os.applescript"
    namespace: ClassVar[ToolNamespace] = "os"
    name: str = "applescript"
    side_effect: ClassVar[SideEffect] = "destructive"
    reversible: bool = False
    default_dry_run: bool = True
    timeout_ms: int = 30_000
    max_output_bytes: int = 1 * 1024 * 1024

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["script"],
            "properties": {
                "script": {"type": "string", "minLength": 1},
            },
            "additionalProperties": False,
        }

    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["stdout", "stderr", "exit_code"],
            "properties": {
                "stdout": {"type": "string"},
                "stderr": {"type": "string"},
                "exit_code": {"type": "integer"},
            },
        }

    def permissions(self) -> list[Permission]:
        return [Permission(kind="os_api", scope="applescript", action="execute")]

    async def dry_run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        _check_platform()
        script = args["script"]
        return ToolResult(
            output={"dry_run": True, "script_length": len(script)},
            diff_preview={"preview": f"Would execute AppleScript ({len(script)} chars)"},
            side_effects=["would execute AppleScript"],
        )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        _check_platform()
        script = args["script"]
        result = await ctx.io.run_subprocess(
            ["osascript", "-e", script],
            timeout_seconds=30,
            max_output_bytes=self.max_output_bytes,
        )
        return ToolResult(
            output={
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "exit_code": result["exit_code"],
            },
            side_effects=["executed AppleScript"],
        )


def _check_platform() -> None:
    if sys.platform != "darwin":
        raise ToolRuntimeError(
            "os.applescript is macOS only",
            details={"platform": sys.platform},
        )
