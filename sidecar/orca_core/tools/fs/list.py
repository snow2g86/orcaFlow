"""fs.list — 디렉토리 나열 (read side-effect)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from ...schema.tool import Permission, SideEffect, ToolNamespace
from .._base import ToolContext, ToolResult

__all__ = ["FsListTool"]

_DEFAULT_MAX_ENTRIES = 1000


class FsListTool:
    """디렉토리 나열.

    Args schema::
        { "path": "<dir>", "glob": "<optional>", "max_entries": 1000 }
    """

    id: str = "fs.list"
    namespace: ClassVar[ToolNamespace] = "fs"
    name: str = "list"
    side_effect: ClassVar[SideEffect] = "read"
    reversible: bool = False
    default_dry_run: bool = False
    timeout_ms: int = 15_000
    max_output_bytes: int = 1 * 1024 * 1024

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["path"],
            "properties": {
                "path": {"type": "string", "minLength": 1},
                "glob": {"type": "string"},
                "max_entries": {"type": "integer", "minimum": 1, "maximum": 100000},
            },
            "additionalProperties": False,
        }

    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["entries", "truncated"],
            "properties": {
                "entries": {"type": "array"},
                "truncated": {"type": "boolean"},
            },
        }

    def permissions(self) -> list[Permission]:
        return [Permission(kind="fs_path", scope="**", action="read")]

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        path = Path(args["path"]).expanduser()
        glob = args.get("glob")
        max_entries = int(args.get("max_entries") or _DEFAULT_MAX_ENTRIES)
        entries, truncated = await ctx.io.list_dir(path, glob=glob, max_entries=max_entries)
        return ToolResult(
            output={
                "entries": [
                    {
                        "name": e.name,
                        "path": e.path,
                        "kind": e.kind,
                        "size_bytes": e.size_bytes,
                    }
                    for e in entries
                ],
                "truncated": truncated,
                "path": str(path),
            }
        )

    async def dry_run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        path = Path(args["path"]).expanduser()
        exists = await ctx.io.exists(path)
        return ToolResult(
            output={"exists": exists, "path": str(path)},
            diff_preview={"preview": "read-only tool — no changes"},
        )
