"""os.clipboard_read / os.clipboard_write — 클립보드 읽기/쓰기.

macOS: pbpaste/pbcopy, Linux: xclip, Windows: PowerShell.
"""

from __future__ import annotations

import sys
from typing import Any, ClassVar

from ...errors import ToolRuntimeError
from ...schema.tool import Permission, SideEffect, ToolNamespace
from .._base import ToolContext, ToolResult

__all__ = ["OsClipboardReadTool", "OsClipboardWriteTool"]


class OsClipboardReadTool:
    """클립보드 읽기."""

    id: str = "os.clipboard_read"
    namespace: ClassVar[ToolNamespace] = "os"
    name: str = "clipboard_read"
    side_effect: ClassVar[SideEffect] = "read"
    reversible: bool = False
    default_dry_run: bool = False
    timeout_ms: int = 5_000
    max_output_bytes: int = 1 * 1024 * 1024

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        }

    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["content"],
            "properties": {
                "content": {"type": "string"},
            },
        }

    def permissions(self) -> list[Permission]:
        return [Permission(kind="clipboard", scope="*", action="read")]

    async def dry_run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        return ToolResult(
            output={"dry_run": True, "platform": sys.platform},
            diff_preview={"preview": "Would read clipboard"},
        )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        cmd = _read_cmd()
        result = await ctx.io.run_subprocess(cmd, timeout_seconds=3)
        if result["exit_code"] != 0:
            raise ToolRuntimeError(
                "clipboard read failed",
                details={"stderr": result["stderr"], "platform": sys.platform},
            )
        return ToolResult(
            output={"content": result["stdout"]},
        )


class OsClipboardWriteTool:
    """클립보드 쓰기."""

    id: str = "os.clipboard_write"
    namespace: ClassVar[ToolNamespace] = "os"
    name: str = "clipboard_write"
    side_effect: ClassVar[SideEffect] = "write"
    reversible: bool = True
    default_dry_run: bool = True
    timeout_ms: int = 5_000
    max_output_bytes: int = 64 * 1024

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["content"],
            "properties": {
                "content": {"type": "string", "minLength": 1},
            },
            "additionalProperties": False,
        }

    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["written"],
            "properties": {
                "written": {"type": "boolean"},
                "length": {"type": "integer"},
            },
        }

    def permissions(self) -> list[Permission]:
        return [Permission(kind="clipboard", scope="*", action="write")]

    async def dry_run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        content = args["content"]
        # Read current clipboard for before_snapshot
        try:
            read_result = await ctx.io.run_subprocess(_read_cmd(), timeout_seconds=3)
            old_content = read_result["stdout"] if read_result["exit_code"] == 0 else None
        except Exception:
            old_content = None

        return ToolResult(
            output={
                "dry_run": True,
                "length": len(content),
                "platform": sys.platform,
            },
            diff_preview={"preview": f"Would write {len(content)} chars to clipboard"},
            before_snapshot={"old_content": old_content},
            side_effects=["would write to clipboard"],
        )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        content = args["content"]

        # For write, we need to pipe stdin. Use a special approach via echo | cmd.
        # Since ToolIo.run_subprocess doesn't support stdin, use platform-specific
        # workarounds.
        if sys.platform == "darwin":
            # Use shell=False with printf piped approach via osascript
            write_cmd = [
                "osascript",
                "-e",
                f'set the clipboard to "{_escape_applescript(content)}"',
            ]
        elif sys.platform == "linux":
            write_cmd = ["xclip", "-selection", "clipboard"]
            # Fallback: use xclip with xdotool or xsel
            write_cmd = [
                "bash",
                "-c",
                f"echo -n {_shell_quote(content)} | xclip -selection clipboard",
            ]
        elif sys.platform == "win32":
            write_cmd = [
                "powershell",
                "-Command",
                f"Set-Clipboard -Value '{_escape_powershell(content)}'",
            ]
        else:
            raise ToolRuntimeError(
                f"unsupported platform: {sys.platform}",
                details={"platform": sys.platform},
            )

        result = await ctx.io.run_subprocess(write_cmd, timeout_seconds=3)
        written = result["exit_code"] == 0
        return ToolResult(
            output={"written": written, "length": len(content)},
            side_effects=["wrote to clipboard" if written else "clipboard write failed"],
        )


def _read_cmd() -> list[str]:
    if sys.platform == "darwin":
        return ["pbpaste"]
    if sys.platform == "linux":
        return ["xclip", "-selection", "clipboard", "-o"]
    if sys.platform == "win32":
        return ["powershell", "-Command", "Get-Clipboard"]
    raise ToolRuntimeError(
        f"unsupported platform for clipboard: {sys.platform}",
        details={"platform": sys.platform},
    )


def _write_cmd() -> list[str]:
    if sys.platform == "darwin":
        return ["pbcopy"]
    if sys.platform == "linux":
        return ["xclip", "-selection", "clipboard"]
    if sys.platform == "win32":
        return ["powershell", "-Command", "Set-Clipboard"]
    raise ToolRuntimeError(
        f"unsupported platform for clipboard: {sys.platform}",
        details={"platform": sys.platform},
    )


def _escape_applescript(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _escape_powershell(s: str) -> str:
    return s.replace("'", "''")


def _shell_quote(s: str) -> str:
    import shlex  # noqa: PLC0415

    return shlex.quote(s)
