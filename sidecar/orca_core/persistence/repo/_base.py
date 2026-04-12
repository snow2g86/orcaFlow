"""BaseRepository — row ↔ Pydantic 변환 공통."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import json
from typing import Any

import aiosqlite

from ...errors import OrcaError
from ..db import Database

__all__ = [
    "BaseRepository",
    "RepositoryError",
    "json_dumps",
    "json_loads_or_none",
]


def json_dumps(value: Any) -> str:
    """JSON 직렬화 (UTF-8, non-ASCII 보존, 소형)."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def json_loads_or_none(raw: str | None) -> Any | None:
    if raw is None or raw == "":
        return None
    return json.loads(raw)


class RepositoryError(OrcaError):
    """Repository 레벨의 데이터 무결성/쓰기 오류."""

    code = "repo.write_failed"
    http_status = 500


class BaseRepository:
    """Repository 공통 베이스.

    - `self._db` 로 커넥션 획득.
    - row → Pydantic 변환은 각 repo 가 `_row_to_model` 로 구현.
    - 모든 read/write 메서드는 optional `conn` 인자를 받을 수 있어
      `Database.transaction()` 으로 원자적 시퀀스를 구성 가능하다 (M4).
    """

    def __init__(self, db: Database) -> None:
        self._db = db

    @asynccontextmanager
    async def _use_conn(
        self, conn: aiosqlite.Connection | None
    ) -> AsyncIterator[tuple[aiosqlite.Connection, bool]]:
        """전달된 conn 이 있으면 재사용, 없으면 새로 연다.

        두 번째 플래그는 "호출 측이 commit 을 책임져야 하는가" 를 나타낸다.
        외부에서 주입된 경우(트랜잭션 블록) 호출자가 commit/rollback 한다.
        """
        if conn is not None:
            yield conn, False
            return
        async with self._db.connect() as owned:
            yield owned, True

    async def _fetch_one(
        self,
        query: str,
        params: tuple[Any, ...] = (),
        *,
        conn: aiosqlite.Connection | None = None,
    ) -> aiosqlite.Row | None:
        async with self._use_conn(conn) as (c, _owned), c.execute(query, params) as cursor:
            return await cursor.fetchone()

    async def _fetch_all(
        self,
        query: str,
        params: tuple[Any, ...] = (),
        *,
        conn: aiosqlite.Connection | None = None,
    ) -> list[aiosqlite.Row]:
        async with self._use_conn(conn) as (c, _owned), c.execute(query, params) as cursor:
            return list(await cursor.fetchall())

    async def _execute(
        self,
        query: str,
        params: tuple[Any, ...] = (),
        *,
        conn: aiosqlite.Connection | None = None,
    ) -> None:
        async with self._use_conn(conn) as (c, owned):
            await c.execute(query, params)
            if owned:
                await c.commit()

    async def _execute_write(
        self,
        query: str,
        params: tuple[Any, ...] = (),
        *,
        expected_rows: int = 1,
        error_message: str = "expected row not found",
        conn: aiosqlite.Connection | None = None,
    ) -> None:
        """write 쿼리 실행 후 `rowcount` 를 검증한다.

        `expected_rows` 와 다르면 `RepositoryError` raise. 트랜잭션 주입시
        호출자가 rollback 을 책임진다.
        """
        async with self._use_conn(conn) as (c, owned):
            cursor = await c.execute(query, params)
            rowcount = cursor.rowcount
            await cursor.close()
            if rowcount != expected_rows:
                raise RepositoryError(
                    error_message,
                    details={
                        "query": query.strip().splitlines()[0] if query else "",
                        "expected_rows": expected_rows,
                        "actual_rows": rowcount,
                    },
                )
            if owned:
                await c.commit()
