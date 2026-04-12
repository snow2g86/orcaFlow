"""fs.move — 파일/디렉토리 이동 (write, reversible=True).

정책 평가 시 PolicyEngine 은 `src` 와 `dst` 를 **둘 다** path 로 인식해
multi-path 매칭을 수행한다 (H7). 따라서 본 툴은 자체적으로 경로 검증을
수행하지 않는다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from ...schema.tool import Permission, SideEffect, ToolNamespace
from .._base import ToolContext, ToolResult

__all__ = ["FsMoveTool"]


class FsMoveTool:
    """이동/이름 변경."""

    id: str = "fs.move"
    namespace: ClassVar[ToolNamespace] = "fs"
    name: str = "move"
    side_effect: ClassVar[SideEffect] = "write"
    reversible: bool = True
    default_dry_run: bool = True
    timeout_ms: int = 30_000
    max_output_bytes: int = 1 * 1024 * 1024

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["src", "dst"],
            "properties": {
                "src": {"type": "string", "minLength": 1},
                "dst": {"type": "string", "minLength": 1},
                "overwrite": {"type": "boolean"},
            },
            "additionalProperties": False,
        }

    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["src", "dst", "dst_existed"],
            "properties": {
                "src": {"type": "string"},
                "dst": {"type": "string"},
                "dst_existed": {"type": "boolean"},
                "dst_trash_ref": {"type": ["string", "null"]},
                "dst_sha256": {"type": ["string", "null"]},
            },
        }

    def permissions(self) -> list[Permission]:
        return [
            Permission(kind="fs_path", scope="**", action="read"),
            Permission(kind="fs_path", scope="**", action="write"),
        ]

    async def dry_run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        src = Path(args["src"]).expanduser()
        dst = Path(args["dst"]).expanduser()
        src_exists = await ctx.io.exists(src)
        dst_exists = await ctx.io.exists(dst)
        overwrite = bool(args.get("overwrite", False))
        conflict = dst_exists and not overwrite
        dst_sha256: str | None = None
        # H9: overwrite 모드에서 dst 파일이 있으면 미리 체크섬을 계산해
        # journal.before 에 싣는다. 복구 시 trash 에서 dst 를 되돌린 뒤
        # 무결성 검증에 쓴다.
        if dst_exists and overwrite and dst.is_file():
            try:
                dst_sha256 = await ctx.io.sha256_file(dst)
            except OSError:
                dst_sha256 = None
        before_snapshot: dict[str, Any] = {
            "src": str(src),
            "dst": str(dst),
            "dst_existed": dst_exists,
            "overwrite": overwrite,
            "dst_sha256": dst_sha256,
        }
        return ToolResult(
            output={
                "src": str(src),
                "dst": str(dst),
                "src_exists": src_exists,
                "dst_existed": dst_exists,
                "dry_run": True,
            },
            diff_preview={
                "conflict": conflict,
                "overwrite": overwrite,
                "src_exists": src_exists,
                "dst_existed": dst_exists,
                "dst_sha256": dst_sha256,
            },
            before_snapshot=before_snapshot,
            side_effects=["would move" if not conflict else "would fail (conflict)"],
        )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        src = Path(args["src"]).expanduser()
        dst = Path(args["dst"]).expanduser()
        overwrite = bool(args.get("overwrite", False))
        dst_existed = await ctx.io.exists(dst)
        dst_trash_ref: str | None = None
        dst_sha256: str | None = None
        # H9: overwrite 모드에서 dst 가 이미 존재하면 먼저 trash 로 백업.
        # 그 후 src → dst 이동. 복구 시: dst → src 로 되돌리고 trash → dst 로 복원.
        if dst_existed and overwrite:
            if dst.is_file():
                try:
                    dst_sha256 = await ctx.io.sha256_file(dst)
                except OSError:
                    dst_sha256 = None
            trashed = await ctx.io.move_to_trash(dst, run_id=ctx.run_id, entry_id=ctx.tool_call_id)
            dst_trash_ref = str(trashed)
        # trash 가 성공했으면 dst 는 이제 비어 있으므로 overwrite 플래그를
        # 굳이 켜지 않아도 되지만, 계약 일관성을 위해 그대로 전달.
        await ctx.io.move(src, dst, overwrite=overwrite)
        return ToolResult(
            output={
                "src": str(src),
                "dst": str(dst),
                "dst_existed": dst_existed,
                "dst_trash_ref": dst_trash_ref,
                "dst_sha256": dst_sha256,
            },
            before_snapshot={
                "src": str(src),
                "dst": str(dst),
                "dst_existed": dst_existed,
                "overwrite": overwrite,
                "dst_trash_ref": dst_trash_ref,
                "dst_sha256": dst_sha256,
            },
            side_effects=["moved"],
        )
