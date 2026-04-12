"""fs.write_file — 파일 쓰기 (write side-effect, reversible=True).

dry_run 시 현재 파일 여부와 사이즈, diff 미리보기(최대 1KB) 를 반환한다.
run 시 before_snapshot 에 기존 내용(있으면) 을 담아 journal 기록. 신규
파일이면 before=None → 복구 시 파일 삭제.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, ClassVar

from ...errors import ToolRuntimeError
from ...schema.tool import Permission, SideEffect, ToolNamespace
from .._base import ToolContext, ToolResult

__all__ = ["FsWriteFileTool"]

_DIFF_PREVIEW_BYTES = 1024
_DEFAULT_MAX_OUTPUT = 10 * 1024 * 1024  # 10 MiB
_READ_CAP = 50 * 1024 * 1024  # 50 MiB cap for before snapshot


class FsWriteFileTool:
    """파일 쓰기 툴 (atomic rename).

    Args::
        { "path": "<string>", "content": "<utf-8 string>",
          "encoding": "utf-8", "create_parents": true }
    """

    id: str = "fs.write_file"
    namespace: ClassVar[ToolNamespace] = "fs"
    name: str = "write_file"
    side_effect: ClassVar[SideEffect] = "write"
    reversible: bool = True
    default_dry_run: bool = True
    timeout_ms: int = 30_000
    max_output_bytes: int = _DEFAULT_MAX_OUTPUT

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["path", "content"],
            "properties": {
                "path": {"type": "string", "minLength": 1},
                "content": {"type": "string"},
                "encoding": {"enum": ["utf-8"]},
                "create_parents": {"type": "boolean"},
            },
            "additionalProperties": False,
        }

    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["path", "bytes_written", "existed"],
            "properties": {
                "path": {"type": "string"},
                "bytes_written": {"type": "integer"},
                "existed": {"type": "boolean"},
            },
        }

    def permissions(self) -> list[Permission]:
        return [Permission(kind="fs_path", scope="**", action="write")]

    async def dry_run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        path = Path(args["path"]).expanduser()
        content: str = args["content"]
        data = content.encode("utf-8")
        existed = await ctx.io.exists(path)
        old_size = await ctx.io.stat_size(path) if existed else 0
        old_preview: str | None = None
        old_bytes: bytes | None = None
        snapshot_complete = True
        old_sha256: str | None = None
        if existed:
            # H10: 기존 파일 읽기 실패를 조용히 swallow 하지 않는다.
            # - 권한/OS 에러 → dry_run 자체를 실패시켜 실행 차단.
            # - 크기 초과 (>_READ_CAP) → snapshot_complete=False 로 기록해
            #   복구 엔진이 복구 불가로 분기하도록 한다. 실행은 계속 진행
            #   (사용자가 dry_run 리뷰 후 명시적으로 승인했다는 가정).
            try:
                old_bytes = await ctx.io.read_bytes(path, max_bytes=_READ_CAP)
                old_preview = old_bytes[:_DIFF_PREVIEW_BYTES].decode("utf-8", errors="replace")
            except ValueError:
                # read_bytes 는 cap 초과 시 ValueError.
                snapshot_complete = False
                old_bytes = None
                old_preview = None
                # 크기/sha256 은 별도 경로로 수집.
                old_sha256 = await ctx.io.sha256_file(path)
            except OSError as exc:
                raise ToolRuntimeError(
                    "existing file unreadable — execution blocked",
                    details={
                        "path": str(path),
                        "cause": type(exc).__name__,
                        "message": str(exc),
                    },
                ) from exc

        new_preview = data[:_DIFF_PREVIEW_BYTES].decode("utf-8", errors="replace")
        diff_preview: dict[str, Any] = {
            "existed": existed,
            "old_size": old_size,
            "new_size": len(data),
            "old_preview": old_preview,
            "new_preview": new_preview,
            "snapshot_complete": snapshot_complete,
        }
        before_snapshot: dict[str, Any] | None
        if existed and old_bytes is not None:
            # Content stored as utf-8 if decodable, else b64
            try:
                before_snapshot = {
                    "existed": True,
                    "path": str(path),
                    "encoding": "utf-8",
                    "content": old_bytes.decode("utf-8"),
                    "size_bytes": old_size,
                    "snapshot_complete": True,
                }
            except UnicodeDecodeError:
                before_snapshot = {
                    "existed": True,
                    "path": str(path),
                    "encoding": "base64",
                    "content": base64.b64encode(old_bytes).decode("ascii"),
                    "size_bytes": old_size,
                    "snapshot_complete": True,
                }
        elif existed and not snapshot_complete:
            # M4/H10: 크기 초과 → 내용은 null, 복구 불가 플래그 기록.
            before_snapshot = {
                "existed": True,
                "path": str(path),
                "encoding": None,
                "content": None,
                "size_bytes": old_size,
                "sha256": old_sha256,
                "snapshot_complete": False,
            }
        else:
            before_snapshot = {
                "existed": False,
                "path": str(path),
                "snapshot_complete": True,
            }

        return ToolResult(
            output={
                "path": str(path),
                "bytes_written": len(data),
                "existed": existed,
                "dry_run": True,
            },
            diff_preview=diff_preview,
            before_snapshot=before_snapshot,
            side_effects=["would write file"],
        )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        path = Path(args["path"]).expanduser()
        content: str = args["content"]
        create_parents = bool(args.get("create_parents", True))
        data = content.encode("utf-8")
        existed = await ctx.io.exists(path)
        await ctx.io.write_bytes_atomic(path, data, create_parents=create_parents)
        return ToolResult(
            output={
                "path": str(path),
                "bytes_written": len(data),
                "existed": existed,
            },
            side_effects=["wrote file"],
        )
