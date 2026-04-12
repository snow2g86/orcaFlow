"""browser.click — 요소 클릭."""

from __future__ import annotations

from typing import Any, ClassVar

from ...schema.tool import Permission, SideEffect, ToolNamespace
from .._base import ToolContext, ToolResult
from ._session import BrowserSessionManager, require_playwright

__all__ = ["BrowserClickTool"]


class BrowserClickTool:
    """브라우저 페이지 요소 클릭."""

    id: str = "browser.click"
    namespace: ClassVar[ToolNamespace] = "browser"
    name: str = "click"
    side_effect: ClassVar[SideEffect] = "write"
    reversible: bool = False
    default_dry_run: bool = True
    timeout_ms: int = 15_000
    max_output_bytes: int = 1 * 1024 * 1024

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["session_id", "selector"],
            "properties": {
                "session_id": {"type": "string", "minLength": 1},
                "selector": {"type": "string", "minLength": 1},
            },
            "additionalProperties": False,
        }

    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["clicked", "url"],
            "properties": {
                "clicked": {"type": "boolean"},
                "url": {"type": "string"},
            },
        }

    def permissions(self) -> list[Permission]:
        return [Permission(kind="network_host", scope="*", action="execute")]

    async def dry_run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        require_playwright()
        selector = args["selector"]
        return ToolResult(
            output={"dry_run": True, "selector": selector},
            diff_preview={"preview": f"Would click element: {selector}"},
            side_effects=["would click element"],
        )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        require_playwright()
        session_id = args["session_id"]
        selector = args["selector"]
        manager = BrowserSessionManager.get_instance()
        page = manager.get_page(session_id)

        element = await page.query_selector(selector)
        if element is None:
            return ToolResult(
                output={"clicked": False, "url": page.url},
                side_effects=["element not found"],
            )

        await element.click()
        return ToolResult(
            output={"clicked": True, "url": page.url},
            side_effects=["clicked element"],
        )
