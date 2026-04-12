"""ToolRegistry — tool id ↔ 구현 인스턴스 매핑."""

from __future__ import annotations

from collections.abc import Iterable

from ..errors import NotFoundError
from ._base import Tool

__all__ = ["ToolRegistry"]


class ToolRegistry:
    """Tool instance registry.

    사용 예::

        registry = ToolRegistry()
        registry.register(FsReadFileTool())
        registry.get("fs.read_file")
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.id] = tool

    def get(self, tool_id: str) -> Tool:
        tool = self._tools.get(tool_id)
        if tool is None:
            raise NotFoundError(
                f"tool not registered: {tool_id}",
                details={"tool_id": tool_id},
            )
        return tool

    def list_ids(self) -> list[str]:
        return sorted(self._tools.keys())

    def __contains__(self, tool_id: object) -> bool:
        return isinstance(tool_id, str) and tool_id in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    def values(self) -> Iterable[Tool]:
        return list(self._tools.values())
