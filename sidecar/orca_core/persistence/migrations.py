"""SQLite 마이그레이션 (v0 → v1).

design.md §3.3: Alembic 비사용, `PRAGMA user_version` 기반 분기.
"""

from __future__ import annotations

from importlib import resources

import aiosqlite

__all__ = ["CURRENT_VERSION", "run_migrations"]

CURRENT_VERSION = 1


def _load_schema_v1_sql() -> str:
    # 패키지 내 schema_v1.sql 을 로드
    return resources.files("orca_core.persistence").joinpath("schema_v1.sql").read_text("utf-8")


async def _get_user_version(conn: aiosqlite.Connection) -> int:
    async with conn.execute("PRAGMA user_version;") as cursor:
        row = await cursor.fetchone()
    return int(row[0]) if row is not None else 0


async def _set_user_version(conn: aiosqlite.Connection, version: int) -> None:
    # PRAGMA 는 파라미터 바인딩을 받지 않음 — int 이므로 문자열 조립 안전.
    await conn.execute(f"PRAGMA user_version = {int(version)};")


async def run_migrations(conn: aiosqlite.Connection) -> int:
    """현재 user_version 을 읽어 필요한 마이그레이션을 적용.

    반환값: 마이그레이션 후의 user_version.
    """
    version = await _get_user_version(conn)
    if version >= CURRENT_VERSION:
        return version

    if version == 0:
        sql = _load_schema_v1_sql()
        await conn.executescript(sql)
        await _set_user_version(conn, 1)
        version = 1

    return version
