"""web.search — DuckDuckGo instant answer API (network side-effect).

외부 API 키 불필요. httpx 로 호출.
"""

from __future__ import annotations

from typing import Any, ClassVar

import httpx

from ...errors import ToolRuntimeError
from ...schema.tool import Permission, SideEffect, ToolNamespace
from .._base import ToolContext, ToolResult

__all__ = ["WebSearchTool"]

_DDG_API = "https://api.duckduckgo.com/"


class WebSearchTool:
    """DuckDuckGo 검색 툴."""

    id: str = "web.search"
    namespace: ClassVar[ToolNamespace] = "web"
    name: str = "search"
    side_effect: ClassVar[SideEffect] = "network"
    reversible: bool = False
    default_dry_run: bool = False
    timeout_ms: int = 15_000
    max_output_bytes: int = 1 * 1024 * 1024

    # 테스트용 client 주입
    _client_factory: type[httpx.AsyncClient] | None = None

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string", "minLength": 1, "maxLength": 500},
            },
            "additionalProperties": False,
        }

    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["abstract", "source", "url", "results"],
            "properties": {
                "abstract": {"type": "string"},
                "source": {"type": "string"},
                "url": {"type": "string"},
                "results": {"type": "array"},
            },
        }

    def permissions(self) -> list[Permission]:
        return [Permission(kind="network_host", scope="api.duckduckgo.com", action="read")]

    async def dry_run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        query = args["query"]
        return ToolResult(
            output={"dry_run": True, "query": query},
            diff_preview={"preview": f"Would search: {query}"},
        )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        query = args["query"]

        try:
            client_cls = self._client_factory or httpx.AsyncClient
            async with client_cls() as client:
                response = await client.get(
                    _DDG_API,
                    params={"q": query, "format": "json", "no_html": "1"},
                    timeout=10,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ToolRuntimeError(
                f"DuckDuckGo search failed: {exc}",
                details={"query": query},
            ) from exc

        data = response.json()

        # Extract related topics as results
        results: list[dict[str, str]] = []
        for topic in data.get("RelatedTopics", [])[:10]:
            if "Text" in topic:
                results.append(
                    {
                        "text": topic["Text"],
                        "url": topic.get("FirstURL", ""),
                    }
                )

        return ToolResult(
            output={
                "abstract": data.get("Abstract", ""),
                "source": data.get("AbstractSource", ""),
                "url": data.get("AbstractURL", ""),
                "results": results,
            },
            side_effects=["searched DuckDuckGo"],
        )
