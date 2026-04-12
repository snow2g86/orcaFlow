"""aiosqlite 커넥션 래퍼 (design.md §3.3).

PRAGMA 설정:
- `journal_mode=WAL` — 동시 읽기
- `synchronous=NORMAL` — 성능
- `foreign_keys=ON` — 제약 강제
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

from .migrations import run_migrations

__all__ = ["Database"]


class Database:
    """단일 SQLite 파일을 감싸는 커넥션 매니저.

    Notes:
        - aiosqlite 의 `Connection` 은 내부적으로 thread pool 을 사용한다.
        - 테스트에서 `:memory:` 사용 시 단일 커넥션을 공유해야 한다.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = str(path) if not isinstance(path, str) else path
        self._ready = False

    @property
    def path(self) -> str:
        return self._path

    async def initialize(self) -> None:
        """PRAGMA 적용 + 마이그레이션 실행 (idempotent)."""
        async with self.connect() as conn:
            await conn.execute("PRAGMA journal_mode=WAL;")
            await conn.execute("PRAGMA synchronous=NORMAL;")
            await conn.execute("PRAGMA foreign_keys=ON;")
            await run_migrations(conn)
            await conn.commit()
        self._ready = True

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[aiosqlite.Connection]:
        """커넥션 컨텍스트 매니저. 호출자는 직접 commit 해야 한다."""
        conn = await aiosqlite.connect(self._path)
        try:
            await conn.execute("PRAGMA foreign_keys=ON;")
            conn.row_factory = aiosqlite.Row
            yield conn
        finally:
            await conn.close()

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[aiosqlite.Connection]:
        """원자적 트랜잭션 컨텍스트 매니저.

        여러 repository 쓰기를 하나의 트랜잭션으로 묶을 때 사용한다.
        블록 내에서 예외가 발생하면 rollback, 정상 종료시 commit.

        사용 예::

            async with db.transaction() as conn:
                await runs_repo.insert(run, conn=conn)
                await audit_repo.insert(log, conn=conn)
        """
        conn = await aiosqlite.connect(self._path)
        try:
            await conn.execute("PRAGMA foreign_keys=ON;")
            conn.row_factory = aiosqlite.Row
            try:
                yield conn
                await conn.commit()
            except Exception:
                await conn.rollback()
                raise
        finally:
            await conn.close()
