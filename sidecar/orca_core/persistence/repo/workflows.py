"""Workflow repository.

YAML 원본은 `workflows.yaml` 컬럼에 보관한다 (design.md §3.1.1).
Repository 는 원본 YAML 과 메타데이터(row) 만 보존한다. Pydantic 복원은
YAML 파서(M3 범위) 가 담당한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import aiosqlite

from ...schema.workflow import Workflow
from ._base import BaseRepository

__all__ = ["WorkflowRow", "WorkflowsRepository"]


@dataclass(frozen=True, slots=True)
class WorkflowRow:
    """workflows 테이블 1 row 의 얕은 뷰."""

    id: str
    name: str
    version: int
    yaml: str
    policy_id: str | None
    default_llm_profile_id: str | None
    created_at: datetime
    updated_at: datetime


class WorkflowsRepository(BaseRepository):
    """workflows 테이블."""

    async def upsert(self, workflow: Workflow, *, yaml: str) -> None:
        query = """
        INSERT INTO workflows (id, name, version, yaml, policy_id, default_llm_profile_id,
                               created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            version=excluded.version,
            yaml=excluded.yaml,
            policy_id=excluded.policy_id,
            default_llm_profile_id=excluded.default_llm_profile_id,
            updated_at=excluded.updated_at;
        """
        params: tuple[Any, ...] = (
            workflow.id,
            workflow.name,
            workflow.version,
            yaml,
            workflow.policy_id,
            workflow.default_llm_profile_id,
            workflow.created_at.isoformat(),
            workflow.updated_at.isoformat(),
        )
        await self._execute(query, params)

    async def get(self, workflow_id: str) -> WorkflowRow | None:
        row = await self._fetch_one("SELECT * FROM workflows WHERE id = ?;", (workflow_id,))
        if row is None:
            return None
        return _row_to_workflow(row)

    async def list_all(self) -> list[WorkflowRow]:
        rows = await self._fetch_all("SELECT * FROM workflows ORDER BY updated_at DESC;")
        return [_row_to_workflow(r) for r in rows]

    async def delete(self, workflow_id: str) -> None:
        await self._execute("DELETE FROM workflows WHERE id = ?;", (workflow_id,))


def _row_to_workflow(row: aiosqlite.Row) -> WorkflowRow:
    return WorkflowRow(
        id=str(row["id"]),
        name=str(row["name"]),
        version=int(row["version"]),
        yaml=str(row["yaml"]),
        policy_id=(str(row["policy_id"]) if row["policy_id"] else None),
        default_llm_profile_id=(
            str(row["default_llm_profile_id"]) if row["default_llm_profile_id"] else None
        ),
        created_at=datetime.fromisoformat(str(row["created_at"])),
        updated_at=datetime.fromisoformat(str(row["updated_at"])),
    )
