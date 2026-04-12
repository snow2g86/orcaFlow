"""Tool Protocol, ToolContext, ToolResult, ToolIo, EventEmitter.

conventions.md §4.3 의 `Tool` Protocol 을 공식 시그니처로 사용한다.

- `ToolContext` : 툴 호출에 필요한 모든 협력자(정책, 감사, 저널, I/O, 이벤트,
  취소 토큰, 시크릿 스토어, dry_run 플래그) 주입 컨테이너.
- `ToolIo` : 파일/프로세스 접근 래퍼. 툴은 직접 `open()` / `shutil` / `Path.write_bytes`
  를 사용하지 않고 이 래퍼를 경유해야 한다.
- `EventEmitter` : M4 에서 SSE 확장 예정. M3 은 `InMemoryEventEmitter` 로 충분.
- `CancelToken` : `asyncio.Event` 래퍼.
- `TransactionScope` / `TransactionFactory` : ToolRuntime 이 Audit/Journal/ToolCall
  을 원자적으로 커밋하기 위해 의존성 역전으로 주입받는 Protocol.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import contextlib
from dataclasses import dataclass, field
import fnmatch
import hashlib
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

import anyio

from ..audit.sink import AuditDbWriter, AuditSink
from ..errors import ToolCancelledError
from ..journal.store import JournalDbWriter, JournalStore
from ..policy.engine import PolicyEngine
from ..schema.run import ToolCall
from ..schema.tool import Permission, SideEffect, ToolNamespace

__all__ = [
    "CancelToken",
    "DirEntry",
    "EventEmitter",
    "InMemoryEventEmitter",
    "SecretStoreLike",
    "Tool",
    "ToolCallWriter",
    "ToolContext",
    "ToolIo",
    "ToolResult",
    "TransactionFactory",
    "TransactionScope",
    "default_tool_io",
]


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


class EventEmitter(Protocol):
    """Event emitter Protocol (M4 에서 SSE 로 확장)."""

    async def emit(self, event: str, payload: dict[str, Any]) -> None: ...


class InMemoryEventEmitter:
    """테스트/개발용 인메모리 emitter. 발생 이벤트를 리스트에 기록."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    async def emit(self, event: str, payload: dict[str, Any]) -> None:
        self.events.append((event, dict(payload)))


# ---------------------------------------------------------------------------
# Cancel token
# ---------------------------------------------------------------------------


class CancelToken:
    """`asyncio.Event` 래퍼. 호출자가 `cancel()` 하면 `is_cancelled()==True`."""

    def __init__(self) -> None:
        self._event = asyncio.Event()

    def cancel(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> None:
        await self._event.wait()


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ToolResult:
    """단일 툴 실행 결과.

    Parameters:
        output : 직렬화 가능한 결과 페이로드 (input/output schema 에 맞춤).
        diff_preview : dry_run 결과 미리보기 (사용자 승인 UI 표시용).
        stored_ref : output 이 `max_output_bytes` 초과로 spill 됐을 때의 경로.
        side_effects : 사용자 표시용 부작용 요약 (예: `["wrote file"]`).
        before_snapshot : reversible 툴이 journal.before 에 기록할 페이로드.
    """

    output: dict[str, Any] = field(default_factory=dict)
    diff_preview: dict[str, Any] | None = None
    stored_ref: str | None = None
    side_effects: list[str] = field(default_factory=list)
    before_snapshot: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# I/O wrapper
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DirEntry:
    name: str
    path: str
    kind: Literal["file", "dir", "symlink"]
    size_bytes: int


class ToolIo:
    """파일/프로세스 접근 래퍼 — 툴은 반드시 이 래퍼를 경유.

    모든 blocking I/O 는 `anyio.to_thread.run_sync` 로 스레드풀에 위임한다.
    트래시 경로 루트는 `trash_root` (기본 `~/.orcaflow/trash/`).
    """

    def __init__(self, *, trash_root: Path | None = None) -> None:
        self._trash_root = trash_root or (Path.home() / ".orcaflow" / "trash")

    @property
    def trash_root(self) -> Path:
        return self._trash_root

    async def read_bytes(self, path: Path, *, max_bytes: int) -> bytes:
        return await anyio.to_thread.run_sync(self._read_bytes_sync, path, max_bytes)

    @staticmethod
    def _read_bytes_sync(path: Path, max_bytes: int) -> bytes:
        with path.open("rb") as fp:
            data = fp.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError(f"file too large: {path} > {max_bytes} bytes")
        return data

    async def write_bytes_atomic(
        self,
        path: Path,
        data: bytes,
        *,
        create_parents: bool,
    ) -> None:
        await anyio.to_thread.run_sync(self._write_bytes_atomic_sync, path, data, create_parents)

    @staticmethod
    def _write_bytes_atomic_sync(path: Path, data: bytes, create_parents: bool) -> None:
        if create_parents:
            path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".orca-tmp")
        try:
            with tmp.open("wb") as fp:
                fp.write(data)
                fp.flush()
            tmp.replace(path)
        except Exception:
            if tmp.exists():
                with contextlib.suppress(OSError):
                    tmp.unlink()
            raise

    async def list_dir(
        self,
        path: Path,
        *,
        glob: str | None,
        max_entries: int,
    ) -> tuple[list[DirEntry], bool]:
        return await anyio.to_thread.run_sync(self._list_dir_sync, path, glob, max_entries)

    @staticmethod
    def _list_dir_sync(
        path: Path,
        glob: str | None,
        max_entries: int,
    ) -> tuple[list[DirEntry], bool]:
        if not path.exists() or not path.is_dir():
            raise FileNotFoundError(f"not a directory: {path}")
        results: list[DirEntry] = []
        truncated = False
        for child in sorted(path.iterdir(), key=lambda p: p.name):
            if glob and not fnmatch.fnmatch(child.name, glob):
                continue
            if len(results) >= max_entries:
                truncated = True
                break
            try:
                if child.is_symlink():
                    kind: Literal["file", "dir", "symlink"] = "symlink"
                    size = 0
                elif child.is_dir():
                    kind = "dir"
                    size = 0
                else:
                    kind = "file"
                    size = child.stat().st_size
            except OSError:
                kind = "file"
                size = 0
            results.append(DirEntry(name=child.name, path=str(child), kind=kind, size_bytes=size))
        return results, truncated

    async def move(self, src: Path, dst: Path, *, overwrite: bool) -> None:
        await anyio.to_thread.run_sync(self._move_sync, src, dst, overwrite)

    @staticmethod
    def _move_sync(src: Path, dst: Path, overwrite: bool) -> None:
        if not src.exists():
            raise FileNotFoundError(f"source does not exist: {src}")
        if dst.exists() and not overwrite:
            raise FileExistsError(f"destination exists: {dst}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.replace(dst)

    async def move_to_trash(self, path: Path, *, run_id: str, entry_id: str) -> Path:
        return await anyio.to_thread.run_sync(self._move_to_trash_sync, path, run_id, entry_id)

    def _move_to_trash_sync(self, path: Path, run_id: str, entry_id: str) -> Path:
        if not path.exists():
            raise FileNotFoundError(f"target does not exist: {path}")
        trash_dir = self._trash_root / run_id / entry_id
        trash_dir.mkdir(parents=True, exist_ok=True)
        dst = trash_dir / path.name
        path.replace(dst)
        return dst

    async def restore_from_trash(self, trashed_path: Path, original_path: Path) -> None:
        await anyio.to_thread.run_sync(self._restore_from_trash_sync, trashed_path, original_path)

    @staticmethod
    def _restore_from_trash_sync(trashed_path: Path, original_path: Path) -> None:
        if not trashed_path.exists():
            raise FileNotFoundError(f"trashed file missing: {trashed_path}")
        original_path.parent.mkdir(parents=True, exist_ok=True)
        trashed_path.replace(original_path)

    async def exists(self, path: Path) -> bool:
        return await anyio.to_thread.run_sync(path.exists)

    async def stat_size(self, path: Path) -> int:
        return await anyio.to_thread.run_sync(self._stat_size_sync, path)

    @staticmethod
    def _stat_size_sync(path: Path) -> int:
        return path.stat().st_size

    async def walk_files(self, path: Path) -> list[Path]:
        return await anyio.to_thread.run_sync(self._walk_files_sync, path)

    @staticmethod
    def _walk_files_sync(path: Path) -> list[Path]:
        results: list[Path] = []
        if path.is_file():
            return [path]
        for child in path.rglob("*"):
            if child.is_file():
                results.append(child)
        return results

    async def walk_files_with_size(self, path: Path) -> list[tuple[Path, int]]:
        """`walk_files` 의 변형. stat 을 worker thread 에서 일괄 수행한다 (M3)."""
        return await anyio.to_thread.run_sync(self._walk_files_with_size_sync, path)

    @staticmethod
    def _walk_files_with_size_sync(path: Path) -> list[tuple[Path, int]]:
        results: list[tuple[Path, int]] = []
        if path.is_file():
            try:
                size = path.stat().st_size
            except OSError:
                size = 0
            return [(path, size)]
        for child in path.rglob("*"):
            if not child.is_file():
                continue
            try:
                size = child.stat().st_size
            except OSError:
                size = 0
            results.append((child, size))
        return results

    async def run_subprocess(
        self,
        cmd: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout_seconds: int = 30,
        max_output_bytes: int = 1 * 1024 * 1024,
    ) -> dict[str, Any]:
        """Blocking subprocess 실행을 worker thread 에 위임.

        Returns dict with keys: stdout, stderr, exit_code, timed_out, truncated.
        """
        return await anyio.to_thread.run_sync(
            lambda: self._run_subprocess_sync(
                cmd,
                cwd=cwd,
                env=env,
                timeout_seconds=timeout_seconds,
                max_output_bytes=max_output_bytes,
            )
        )

    @staticmethod
    def _run_subprocess_sync(
        cmd: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout_seconds: int = 30,
        max_output_bytes: int = 1 * 1024 * 1024,
    ) -> dict[str, Any]:
        import os  # noqa: PLC0415
        import subprocess  # noqa: PLC0415

        merged_env = {**os.environ, **(env or {})}
        timed_out = False
        try:
            proc = subprocess.run(  # noqa: S603
                cmd,
                cwd=str(cwd) if cwd else None,
                env=merged_env,
                capture_output=True,
                timeout=timeout_seconds,
                shell=False,
                check=False,
            )
            stdout = proc.stdout
            stderr = proc.stderr
            exit_code = proc.returncode
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or b""
            stderr = exc.stderr or b""
            exit_code = -1
            timed_out = True

        truncated = False
        if len(stdout) > max_output_bytes:
            stdout = stdout[:max_output_bytes]
            truncated = True
        if len(stderr) > max_output_bytes:
            stderr = stderr[:max_output_bytes]
            truncated = True

        return {
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "exit_code": exit_code,
            "timed_out": timed_out,
            "truncated": truncated,
        }

    async def sha256_file(self, path: Path, *, chunk_size: int = 65536) -> str:
        """파일 전체를 chunk 단위로 읽어 SHA-256 해시를 계산한다.

        H2 regression — `read_bytes(max_bytes=1 MiB)` 로 한번에 읽어
        1 MiB 초과 파일 삭제가 차단되던 문제를 해결한다. 파일 크기 제한
        없음 — 대용량 파일도 chunk 단위 update 로 처리한다.
        """
        return await anyio.to_thread.run_sync(self._sha256_file_sync, path, chunk_size)

    @staticmethod
    def _sha256_file_sync(path: Path, chunk_size: int) -> str:
        hasher = hashlib.sha256()
        with path.open("rb") as fp:
            while True:
                chunk = fp.read(chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()


def default_tool_io() -> ToolIo:
    return ToolIo()


# ---------------------------------------------------------------------------
# Transaction scope (dependency inversion)
# ---------------------------------------------------------------------------


class ToolCallWriter(Protocol):
    """ToolCall 엔티티 insert + result back-fill 경로.

    H3 regression — 기존에는 `insert` 한 뒤 result/audit_log_id/duration_ms
    back-fill 을 model 레벨에서만 수행해 DB 에 반영되지 않았다. 본 Protocol
    의 `update_result` 로 최종 Step 6 이후 DB 레코드를 갱신한다.
    """

    async def insert(self, call: ToolCall) -> None: ...

    async def update_result(
        self,
        tool_call_id: str,
        *,
        result_json: dict[str, Any] | None,
        error_json: dict[str, Any] | None,
        duration_ms: int | None,
        audit_log_id: str | None,
        policy_decision: str | None = None,
    ) -> None: ...


class SecretStoreLike(Protocol):
    """`ProviderSecretStore` 와 구조적으로 동일한 Protocol (import 경계 회피).

    `orca_core.tools` 는 import-linter 레이어 규칙상 `orca_core.providers`
    를 import 할 수 없기 때문에, 동일 구조의 Protocol 을 로컬에서 재선언해
    duck-typing 으로 받는다.
    """

    async def get(self, api_key_ref: str) -> str: ...


@dataclass(frozen=True, slots=True)
class TransactionScope:
    """한 번의 ToolRuntime.invoke() 동안 공유되는 쓰기 보드들.

    `audit_db_writer` / `journal_db_writer` / `tool_call_writer` 는 모두
    동일한 DB 트랜잭션(또는 in-memory mock) 을 공유해야 한다.
    """

    audit_db_writer: AuditDbWriter | None
    journal_db_writer: JournalDbWriter | None
    tool_call_writer: ToolCallWriter


TransactionFactory = Callable[[], "AbstractTransactionContext"]
"""호출 때마다 새 `TransactionScope` 를 async context 로 제공하는 팩토리."""


class AbstractTransactionContext(Protocol):
    """`async with factory() as scope:` 패턴의 async context manager."""

    async def __aenter__(self) -> TransactionScope: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any,
    ) -> None: ...


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ToolContext:
    """툴 실행 컨텍스트.

    `journal` / `audit` / `tool_call_writer` 는 **트랜잭션 내부에서 ToolRuntime
    이 재조립한 인스턴스**가 주입된다 — 외부에서 바로 넘긴 글로벌 sink 는
    원자성 보장이 어렵다.
    """

    run_id: str
    run_step_id: str
    tool_call_id: str
    policy_engine: PolicyEngine
    journal: JournalStore
    audit: AuditSink
    events: EventEmitter
    secret_store: SecretStoreLike | None
    io: ToolIo
    cancel_token: CancelToken
    dry_run: bool

    def check_cancel(self) -> None:
        if self.cancel_token.is_cancelled():
            # H8: distinct exception class so callers can tell user-initiated
            # cancel from generic asyncio.CancelledError propagating from
            # unrelated task cancellation.
            raise ToolCancelledError("tool call cancelled by caller")


# ---------------------------------------------------------------------------
# Tool Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class Tool(Protocol):
    """툴 공통 인터페이스 (conventions.md §4.3)."""

    id: str
    namespace: ToolNamespace
    side_effect: SideEffect
    reversible: bool
    default_dry_run: bool
    timeout_ms: int
    max_output_bytes: int

    def input_schema(self) -> dict[str, Any]: ...

    def output_schema(self) -> dict[str, Any]: ...

    def permissions(self) -> list[Permission]: ...

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult: ...

    async def dry_run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult: ...
