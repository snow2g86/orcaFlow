"""browser.open — Playwright 브라우저 세션 시작.

Playwright 가 설치되어 있지 않으면 graceful ToolRuntimeError.
"""

from __future__ import annotations

from typing import Any, ClassVar

from ...schema.tool import Permission, SideEffect, ToolNamespace
from .._base import ToolContext, ToolResult
from ._session import BrowserSessionManager, require_playwright

__all__ = ["BrowserOpenTool"]


class BrowserOpenTool:
    """브라우저 세션 시작."""

    id: str = "browser.open"
    namespace: ClassVar[ToolNamespace] = "browser"
    name: str = "open"
    side_effect: ClassVar[SideEffect] = "network"
    reversible: bool = False
    default_dry_run: bool = False
    timeout_ms: int = 30_000
    max_output_bytes: int = 1 * 1024 * 1024

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "headless": {"type": "boolean"},
            },
            "additionalProperties": False,
        }

    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["session_id"],
            "properties": {
                "session_id": {"type": "string"},
            },
        }

    def permissions(self) -> list[Permission]:
        return [Permission(kind="network_host", scope="*", action="read")]

    async def dry_run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        require_playwright()
        headless = args.get("headless", True)
        return ToolResult(
            output={"dry_run": True, "headless": headless},
            diff_preview={"preview": "Would open browser session"},
        )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        require_playwright()
        headless = args.get("headless", True)
        manager = BrowserSessionManager.get_instance()
        session_id = await manager.create_session(headless=headless)
        return ToolResult(
            output={"session_id": session_id},
            side_effects=["opened browser session"],
        )
