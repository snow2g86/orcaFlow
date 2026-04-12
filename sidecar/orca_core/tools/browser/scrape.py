"""browser.scrape — 페이지 텍스트/HTML 추출."""

from __future__ import annotations

from typing import Any, ClassVar

from ...schema.tool import Permission, SideEffect, ToolNamespace
from .._base import ToolContext, ToolResult
from ._session import BrowserSessionManager, require_playwright

__all__ = ["BrowserScrapeTool"]


class BrowserScrapeTool:
    """페이지에서 텍스트 또는 HTML 추출."""

    id: str = "browser.scrape"
    namespace: ClassVar[ToolNamespace] = "browser"
    name: str = "scrape"
    side_effect: ClassVar[SideEffect] = "read"
    reversible: bool = False
    default_dry_run: bool = False
    timeout_ms: int = 30_000
    max_output_bytes: int = 1 * 1024 * 1024

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["session_id"],
            "properties": {
                "session_id": {"type": "string", "minLength": 1},
                "selector": {"type": ["string", "null"]},
                "extract": {"enum": ["text", "html"]},
            },
            "additionalProperties": False,
        }

    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["content", "url"],
            "properties": {
                "content": {"type": "string"},
                "url": {"type": "string"},
            },
        }

    def permissions(self) -> list[Permission]:
        return [Permission(kind="network_host", scope="*", action="read")]

    async def dry_run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        require_playwright()
        selector = args.get("selector")
        extract = args.get("extract", "text")
        return ToolResult(
            output={"dry_run": True, "selector": selector, "extract": extract},
            diff_preview={"preview": f"Would scrape {extract} from page"},
        )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        require_playwright()
        session_id = args["session_id"]
        selector = args.get("selector")
        extract = args.get("extract", "text")
        manager = BrowserSessionManager.get_instance()
        page = manager.get_page(session_id)

        if selector:
            element = await page.query_selector(selector)
            if element is None:
                return ToolResult(
                    output={"content": "", "url": page.url},
                    side_effects=["selector not found"],
                )
            if extract == "html":
                content = await element.inner_html()
            else:
                content = await element.inner_text()
        elif extract == "html":
            content = await page.content()
        else:
            content = await page.inner_text("body")

        # Truncate if exceeds max
        if len(content) > self.max_output_bytes:
            content = content[: self.max_output_bytes]

        return ToolResult(
            output={"content": content, "url": page.url},
            side_effects=["scraped page content"],
        )
