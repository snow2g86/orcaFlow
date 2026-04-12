"""LLMProfile repository."""

from __future__ import annotations

from typing import Any

import aiosqlite

from ...schema.llm import LLMProfile
from ._base import BaseRepository, json_dumps, json_loads_or_none

__all__ = ["LLMProfilesRepository"]


class LLMProfilesRepository(BaseRepository):
    async def upsert(self, profile: LLMProfile) -> None:
        query = """
        INSERT INTO llm_profiles (id, name, provider_id, model, params_json,
                                  context_window, is_tool_capable, is_planner, is_default)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            provider_id=excluded.provider_id,
            model=excluded.model,
            params_json=excluded.params_json,
            context_window=excluded.context_window,
            is_tool_capable=excluded.is_tool_capable,
            is_planner=excluded.is_planner,
            is_default=excluded.is_default;
        """
        params: tuple[Any, ...] = (
            profile.id,
            profile.name,
            profile.provider_id,
            profile.model,
            json_dumps(profile.params),
            profile.context_window,
            int(profile.is_tool_capable),
            int(profile.is_planner),
            int(profile.is_default),
        )
        await self._execute(query, params)

    async def get(self, profile_id: str) -> LLMProfile | None:
        row = await self._fetch_one("SELECT * FROM llm_profiles WHERE id = ?;", (profile_id,))
        return _row_to_profile(row) if row else None

    async def list_all(self) -> list[LLMProfile]:
        rows = await self._fetch_all("SELECT * FROM llm_profiles ORDER BY name;")
        return [_row_to_profile(r) for r in rows]


def _row_to_profile(row: aiosqlite.Row) -> LLMProfile:
    return LLMProfile(
        id=str(row["id"]),
        name=str(row["name"]),
        provider_id=str(row["provider_id"]),
        model=str(row["model"]),
        params=json_loads_or_none(row["params_json"]) or {},
        context_window=(int(row["context_window"]) if row["context_window"] else None),
        is_tool_capable=bool(row["is_tool_capable"]),
        is_planner=bool(row["is_planner"]),
        is_default=bool(row["is_default"]),
    )
