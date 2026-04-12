"""Provider repository."""

from __future__ import annotations

from typing import Any

import aiosqlite

from ...schema.llm import Provider
from ._base import BaseRepository, json_dumps, json_loads_or_none

__all__ = ["ProvidersRepository"]


class ProvidersRepository(BaseRepository):
    async def upsert(self, provider: Provider) -> None:
        query = """
        INSERT INTO providers (id, name, kind, base_url, api_key_ref, headers_json,
                               timeout_ms, health_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            kind=excluded.kind,
            base_url=excluded.base_url,
            api_key_ref=excluded.api_key_ref,
            headers_json=excluded.headers_json,
            timeout_ms=excluded.timeout_ms,
            health_url=excluded.health_url;
        """
        params: tuple[Any, ...] = (
            provider.id,
            provider.name,
            provider.kind,
            provider.base_url,
            provider.api_key_ref,
            json_dumps(provider.headers) if provider.headers else None,
            provider.timeout_ms,
            provider.health_url,
        )
        await self._execute(query, params)

    async def get(self, provider_id: str) -> Provider | None:
        row = await self._fetch_one("SELECT * FROM providers WHERE id = ?;", (provider_id,))
        return _row_to_provider(row) if row else None

    async def list_all(self) -> list[Provider]:
        rows = await self._fetch_all("SELECT * FROM providers ORDER BY name;")
        return [_row_to_provider(r) for r in rows]

    async def delete(self, provider_id: str) -> None:
        await self._execute("DELETE FROM providers WHERE id = ?;", (provider_id,))


def _row_to_provider(row: aiosqlite.Row) -> Provider:
    return Provider(
        id=str(row["id"]),
        name=str(row["name"]),
        kind=str(row["kind"]),  # type: ignore[arg-type]  # Literal validated by Pydantic
        base_url=str(row["base_url"]),
        api_key_ref=(str(row["api_key_ref"]) if row["api_key_ref"] else None),
        headers=json_loads_or_none(row["headers_json"]) or {},
        timeout_ms=int(row["timeout_ms"]) if row["timeout_ms"] is not None else 30000,
        health_url=(str(row["health_url"]) if row["health_url"] else None),
    )
