"""Tools 패키지 (M3).

conventions.md §4.3 의 `Tool` Protocol 과 `ToolRuntime` (design.md §6.2)
를 제공한다. 툴 구현체는 fs/shell/browser/os/web 네임스페이스 하위에
위치한다. M3 에서는 fs.* 만 실구현되고 나머지는 M7 이후 확장.
"""

from __future__ import annotations

from ._base import (
    CancelToken,
    DirEntry,
    EventEmitter,
    InMemoryEventEmitter,
    Tool,
    ToolCallWriter,
    ToolContext,
    ToolIo,
    ToolResult,
    TransactionFactory,
    TransactionScope,
    default_tool_io,
)
from .registry import ToolRegistry
from .runtime import ToolInvocationResult, ToolRuntime

__all__ = [
    "CancelToken",
    "DirEntry",
    "EventEmitter",
    "InMemoryEventEmitter",
    "Tool",
    "ToolCallWriter",
    "ToolContext",
    "ToolInvocationResult",
    "ToolIo",
    "ToolRegistry",
    "ToolResult",
    "ToolRuntime",
    "TransactionFactory",
    "TransactionScope",
    "default_tool_io",
]
