"""Persistence v0 → v1 마이그레이션 및 PRAGMA 설정."""

from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

from orca_core.persistence import CURRENT_VERSION, Database


@pytest.fixture
async def db(tmp_path: Path) -> Database:
    path = tmp_path / "test.sqlite"
    database = Database(path)
    await database.initialize()
    return database


async def test_migration_sets_user_version(db: Database):
    async with db.connect() as conn, conn.execute("PRAGMA user_version;") as cursor:
        row = await cursor.fetchone()
    assert row is not None
    assert int(row[0]) == CURRENT_VERSION


async def test_migration_is_idempotent(tmp_path: Path):
    database = Database(tmp_path / "t.sqlite")
    await database.initialize()
    await database.initialize()  # second call should be a no-op
    async with database.connect() as conn, conn.execute("PRAGMA user_version;") as cursor:
        row = await cursor.fetchone()
    assert row is not None
    assert int(row[0]) == 1


async def test_expected_tables_exist(db: Database):
    expected = {
        "workflows",
        "providers",
        "llm_profiles",
        "agent_roles",
        "policies",
        "policy_rules",
        "runs",
        "run_steps",
        "tool_calls",
        "approval_requests",
        "audit_logs",
        "journal_entries",
    }
    async with db.connect() as conn:
        async with conn.execute("SELECT name FROM sqlite_master WHERE type='table';") as cursor:
            rows = await cursor.fetchall()
    found = {str(r["name"]) for r in rows}
    missing = expected - found
    assert not missing, f"Missing tables: {missing}"


async def test_foreign_keys_enabled(db: Database):
    async with db.connect() as conn, conn.execute("PRAGMA foreign_keys;") as cursor:
        row = await cursor.fetchone()
    assert row is not None
    assert int(row[0]) == 1


async def test_wal_journal_mode(db: Database):
    async with aiosqlite.connect(db.path) as conn:
        async with conn.execute("PRAGMA journal_mode;") as cursor:
            row = await cursor.fetchone()
    assert row is not None
    assert str(row[0]).lower() == "wal"
