"""fs.delete — 파일/디렉토리 삭제 (destructive, reversible via trash).

휴지통 전략:
- stdlib 만 사용. `send2trash` 같은 외부 라이브러리 의존 금지.
- `~/.orcaflow/trash/<run_id>/<entry_id>/<filename>` 경로로 이동(rename)해
  OS 네이티브 휴지통을 흉내낸다. 복구는 동일 경로에서 원위치로 rename.
- 체크섬 SHA256 을 journal.before 에 함께 저장해 복구 시점의 무결성 검증
  을 가능하게 한다.

디렉토리 재귀 삭제 (`recursive=True`) 의 휴지통 처리는 디렉토리 자체를
trash 디렉토리로 이동해 수행한다. 충돌(같은 이름) 은 상대적으로 드물며,
trash 디렉토리는 run/entry 로 유일성이 보장된다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from ...schema.tool import Permission, SideEffect, ToolNamespace
from .._base import ToolContext, ToolResult

__all__ = ["FsDeleteTool"]


class FsDeleteTool:
    id: str = "fs.delete"
    namespace: ClassVar[ToolNamespace] = "fs"
    name: str = "delete"
    side_effect: ClassVar[SideEffect] = "destructive"
    reversible: bool = True
    default_dry_run: bool = True
    timeout_ms: int = 30_000
    max_output_bytes: int = 1 * 1024 * 1024

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["path"],
            "properties": {
                "path": {"type": "string", "minLength": 1},
                "recursive": {"type": "boolean"},
            },
            "additionalProperties": False,
        }

    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["path", "trashed_to"],
            "properties": {
                "path": {"type": "string"},
                "trashed_to": {"type": "string"},
                "size_bytes": {"type": "integer"},
                "checksum": {"type": "string"},
            },
        }

    def permissions(self) -> list[Permission]:
        return [Permission(kind="fs_path", scope="**", action="delete")]

    async def dry_run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        path = Path(args["path"]).expanduser()
        exists = await ctx.io.exists(path)
        size = 0
        file_count = 0
        entries: list[dict[str, Any]] = []
        if exists:
            if path.is_file():
                size = await ctx.io.stat_size(path)
                file_count = 1
                entries.append({"path": str(path), "size_bytes": size})
            elif path.is_dir():
                # M3: 스레드 풀에서 일괄 stat — async 함수 안의 sync loop 제거.
                pairs = await ctx.io.walk_files_with_size(path)
                file_count = len(pairs)
                size = sum(s for _, s in pairs)
                entries = [{"path": str(p), "size_bytes": s} for p, s in pairs]

        before_snapshot = {
            "path": str(path),
            "exists": exists,
            "size_bytes": size,
            "file_count": file_count,
            "entries": entries,
        }
        return ToolResult(
            output={
                "path": str(path),
                "exists": exists,
                "size_bytes": size,
                "file_count": file_count,
                "dry_run": True,
            },
            diff_preview=before_snapshot,
            before_snapshot=before_snapshot,
            side_effects=[f"would move {file_count} entries to trash"],
        )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        path = Path(args["path"]).expanduser()
        checksum: str | None = None
        size = 0
        # H2: 전체 파일을 한 번에 메모리에 올리지 않고 chunk 스트리밍으로
        # sha256 계산 → 1 MiB 초과 파일도 삭제 가능.
        if path.is_file():
            size = await ctx.io.stat_size(path)
            checksum = await ctx.io.sha256_file(path)
        trashed = await ctx.io.move_to_trash(path, run_id=ctx.run_id, entry_id=ctx.tool_call_id)
        return ToolResult(
            output={
                "path": str(path),
                "trashed_to": str(trashed),
                "size_bytes": size,
                "checksum": checksum,
            },
            side_effects=["moved to trash"],
        )
