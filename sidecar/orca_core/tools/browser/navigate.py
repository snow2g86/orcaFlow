"""browser.navigate — URL 이동."""

from __future__ import annotations

from typing import Any, ClassVar

from ...schema.tool import Permission, SideEffect, ToolNamespace
from .._base import ToolContext, ToolResult
from ._session import BrowserSessionManager, require_playwright, validate_url_host

__all__ = ["BrowserNavigateTool"]


class BrowserNavigateTool:
    """브라우저 세션에서 URL 이동."""

    id: str = "browser.navigate"
    namespace: ClassVar[ToolNamespace] = "browser"
    name: str = "navigate"
    side_effect: ClassVar[SideEffect] = "network"
    reversible: bool = False
    default_dry_run: bool = False
    timeout_ms: int = 30_000
    max_output_bytes: int = 1 * 1024 * 1024

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["session_id", "url"],
            "properties": {
                "session_id": {"type": "string", "minLength": 1},
                "url": {"type": "string", "minLength": 1},
            },
            "additionalProperties": False,
        }

    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["title", "url"],
            "properties": {
                "title": {"type": "string"},
                "url": {"type": "string"},
            },
        }

    def permissions(self) -> list[Permission]:
        return [Permission(kind="network_host", scope="*", action="read")]

    async def dry_run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        require_playwright()
        url = args["url"]
        validate_url_host(url)
        return ToolResult(
            output={"dry_run": True, "url": url},
            diff_preview={"preview": f"Would navigate to {url}"},
        )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        require_playwright()
        session_id = args["session_id"]
        url = args["url"]
        validate_url_host(url)
        manager = BrowserSessionManager.get_instance()
        page = manager.get_page(session_id)
        await page.goto(url)
        title = await page.title()
        return ToolResult(
            output={"title": title, "url": page.url},
            side_effects=["navigated to URL"],
        )
