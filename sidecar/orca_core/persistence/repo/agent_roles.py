"""AgentRole repository."""

from __future__ import annotations

from typing import Any

import aiosqlite

from ...schema.agent import AgentRole
from ._base import BaseRepository, json_dumps, json_loads_or_none

__all__ = ["AgentRolesRepository"]


class AgentRolesRepository(BaseRepository):
    async def upsert(self, role: AgentRole) -> None:
        query = """
        INSERT INTO agent_roles (id, name, display_name, role_type, system_prompt, goal,
                                 tools_json, llm_profile_id, max_steps,
                                 temperature_override, tags_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            display_name=excluded.display_name,
            role_type=excluded.role_type,
            system_prompt=excluded.system_prompt,
            goal=excluded.goal,
            tools_json=excluded.tools_json,
            llm_profile_id=excluded.llm_profile_id,
            max_steps=excluded.max_steps,
            temperature_override=excluded.temperature_override,
            tags_json=excluded.tags_json;
        """
        params: tuple[Any, ...] = (
            role.id,
            role.name,
            role.display_name,
            role.role_type,
            role.system_prompt,
            role.goal,
            json_dumps(role.tools),
            role.llm_profile_id,
            role.max_steps,
            role.temperature_override,
            json_dumps(role.tags),
        )
        await self._execute(query, params)

    async def get(self, role_id: str) -> AgentRole | None:
        row = await self._fetch_one("SELECT * FROM agent_roles WHERE id = ?;", (role_id,))
        return _row_to_role(row) if row else None

    async def list_all(self) -> list[AgentRole]:
        rows = await self._fetch_all("SELECT * FROM agent_roles ORDER BY name;")
        return [_row_to_role(r) for r in rows]


def _row_to_role(row: aiosqlite.Row) -> AgentRole:
    return AgentRole(
        id=str(row["id"]),
        name=str(row["name"]),
        display_name=(str(row["display_name"]) if row["display_name"] else None),
        role_type=str(row["role_type"]),  # type: ignore[arg-type]
        system_prompt=str(row["system_prompt"]),
        goal=(str(row["goal"]) if row["goal"] else None),
        tools=json_loads_or_none(row["tools_json"]) or [],
        llm_profile_id=str(row["llm_profile_id"]),
        max_steps=int(row["max_steps"]) if row["max_steps"] is not None else 10,
        temperature_override=(
            float(row["temperature_override"]) if row["temperature_override"] is not None else None
        ),
        tags=json_loads_or_none(row["tags_json"]) or [],
    )
