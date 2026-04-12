"""os.notify — OS 알림 표시.

플랫폼별 명령: macOS `osascript`, Linux `notify-send`, Windows PowerShell toast.
"""

from __future__ import annotations

import sys
from typing import Any, ClassVar

from ...errors import ToolRuntimeError
from ...schema.tool import Permission, SideEffect, ToolNamespace
from .._base import ToolContext, ToolResult

__all__ = ["OsNotifyTool"]


class OsNotifyTool:
    """OS 알림 표시 툴."""

    id: str = "os.notify"
    namespace: ClassVar[ToolNamespace] = "os"
    name: str = "notify"
    side_effect: ClassVar[SideEffect] = "write"
    reversible: bool = False
    default_dry_run: bool = True
    timeout_ms: int = 10_000
    max_output_bytes: int = 64 * 1024

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["title", "message"],
            "properties": {
                "title": {"type": "string", "minLength": 1, "maxLength": 200},
                "message": {"type": "string", "minLength": 1, "maxLength": 1000},
            },
            "additionalProperties": False,
        }

    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["sent"],
            "properties": {
                "sent": {"type": "boolean"},
                "platform": {"type": "string"},
            },
        }

    def permissions(self) -> list[Permission]:
        return [Permission(kind="os_api", scope="notification", action="write")]

    async def dry_run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        return ToolResult(
            output={
                "dry_run": True,
                "title": args["title"],
                "message": args["message"],
                "platform": sys.platform,
            },
            diff_preview={"preview": f"Would show notification: {args['title']}"},
            side_effects=["would send OS notification"],
        )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        title = args["title"]
        message = args["message"]
        cmd = _build_notify_cmd(title, message)
        result = await ctx.io.run_subprocess(cmd, timeout_seconds=5)
        sent = result["exit_code"] == 0
        return ToolResult(
            output={"sent": sent, "platform": sys.platform},
            side_effects=["sent OS notification" if sent else "notification failed"],
        )


def _build_notify_cmd(title: str, message: str) -> list[str]:
    """플랫폼별 알림 명령 생성."""
    if sys.platform == "darwin":
        script = f'display notification "{message}" with title "{title}"'
        return ["osascript", "-e", script]
    if sys.platform == "linux":
        return ["notify-send", title, message]
    if sys.platform == "win32":
        ps_script = (
            f'[System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms");'
            f"$n=New-Object System.Windows.Forms.NotifyIcon;"
            f"$n.Icon=[System.Drawing.SystemIcons]::Information;"
            f"$n.Visible=$true;"
            f'$n.ShowBalloonTip(3000,"{title}","{message}",'
            f"[System.Windows.Forms.ToolTipIcon]::Info)"
        )
        return ["powershell", "-Command", ps_script]
    raise ToolRuntimeError(
        f"unsupported platform for notifications: {sys.platform}",
        details={"platform": sys.platform},
    )
