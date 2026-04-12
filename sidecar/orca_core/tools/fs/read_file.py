"""fs.read_file — 파일 읽기 (read side-effect, non-reversible)."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, ClassVar

from ...schema.tool import Permission, SideEffect, ToolNamespace
from .._base import ToolContext, ToolResult

__all__ = ["FsReadFileTool"]

_DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10 MiB


class FsReadFileTool:
    """파일 읽기 툴.

    Args schema::
        { "path": "<string>", "max_bytes": <int optional> }

    Result::
        { "content": "<utf8 or base64>", "encoding": "utf-8|base64",
          "size_bytes": <int>, "path": "<normalized>" }
    """

    id: str = "fs.read_file"
    namespace: ClassVar[ToolNamespace] = "fs"
    name: str = "read_file"
    side_effect: ClassVar[SideEffect] = "read"
    reversible: bool = False
    default_dry_run: bool = False
    timeout_ms: int = 15_000
    max_output_bytes: int = _DEFAULT_MAX_BYTES

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["path"],
            "properties": {
                "path": {"type": "string", "minLength": 1},
                "max_bytes": {"type": "integer", "minimum": 1},
            },
            "additionalProperties": False,
        }

    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["content", "encoding", "size_bytes", "path"],
            "properties": {
                "content": {"type": "string"},
                "encoding": {"enum": ["utf-8", "base64"]},
                "size_bytes": {"type": "integer"},
                "path": {"type": "string"},
            },
        }

    def permissions(self) -> list[Permission]:
        return [Permission(kind="fs_path", scope="**", action="read")]

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        path = Path(args["path"]).expanduser()
        max_bytes = int(args.get("max_bytes") or _DEFAULT_MAX_BYTES)
        data = await ctx.io.read_bytes(path, max_bytes=max_bytes)
        try:
            content = data.decode("utf-8")
            encoding = "utf-8"
        except UnicodeDecodeError:
            content = base64.b64encode(data).decode("ascii")
            encoding = "base64"
        return ToolResult(
            output={
                "content": content,
                "encoding": encoding,
                "size_bytes": len(data),
                "path": str(path),
            }
        )

    async def dry_run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        """read 툴이지만 Protocol 규격상 dry_run 도 제공 — 파일 존재 여부만 확인."""
        path = Path(args["path"]).expanduser()
        exists = await ctx.io.exists(path)
        size = await ctx.io.stat_size(path) if exists else 0
        return ToolResult(
            output={"exists": exists, "size_bytes": size, "path": str(path)},
            diff_preview={"preview": "read-only tool — no changes"},
        )
