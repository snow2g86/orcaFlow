"""모든 내장 툴을 ToolRegistry 에 일괄 등록.

17종: fs(5) + shell(1) + browser(4) + os(5) + web(2).

mypy 참고: 각 Tool 구현체가 `namespace`/`side_effect` 를 `ClassVar` 로
선언해 Protocol 의 instance-variable 기대와 충돌한다. 런타임에는 문제없으며,
기존 fs.* 와 동일한 패턴이므로 `type: ignore[arg-type]` 로 억제한다.
"""

from __future__ import annotations

from .browser import BrowserClickTool, BrowserNavigateTool, BrowserOpenTool, BrowserScrapeTool
from .fs import FsDeleteTool, FsListTool, FsMoveTool, FsReadFileTool, FsWriteFileTool
from .os import (
    OsAppleScriptTool,
    OsClipboardReadTool,
    OsClipboardWriteTool,
    OsNotifyTool,
    OsPowerShellTool,
)
from .registry import ToolRegistry
from .shell import ShellExecTool
from .web import WebHttpRequestTool, WebSearchTool

__all__ = ["create_default_registry"]


def create_default_registry() -> ToolRegistry:
    """모든 내장 툴이 등록된 ToolRegistry 를 반환."""
    registry = ToolRegistry()

    # fs (5)
    registry.register(FsReadFileTool())  # type: ignore[arg-type]
    registry.register(FsWriteFileTool())  # type: ignore[arg-type]
    registry.register(FsListTool())  # type: ignore[arg-type]
    registry.register(FsMoveTool())  # type: ignore[arg-type]
    registry.register(FsDeleteTool())  # type: ignore[arg-type]

    # shell (1)
    registry.register(ShellExecTool())  # type: ignore[arg-type]

    # browser (4)
    registry.register(BrowserOpenTool())  # type: ignore[arg-type]
    registry.register(BrowserNavigateTool())  # type: ignore[arg-type]
    registry.register(BrowserScrapeTool())  # type: ignore[arg-type]
    registry.register(BrowserClickTool())  # type: ignore[arg-type]

    # os (5)
    registry.register(OsNotifyTool())  # type: ignore[arg-type]
    registry.register(OsClipboardReadTool())  # type: ignore[arg-type]
    registry.register(OsClipboardWriteTool())  # type: ignore[arg-type]
    registry.register(OsAppleScriptTool())  # type: ignore[arg-type]
    registry.register(OsPowerShellTool())  # type: ignore[arg-type]

    # web (2)
    registry.register(WebHttpRequestTool())  # type: ignore[arg-type]
    registry.register(WebSearchTool())  # type: ignore[arg-type]

    return registry
