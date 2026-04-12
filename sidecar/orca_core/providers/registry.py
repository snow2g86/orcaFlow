"""ProviderRegistry — provider id ↔ adapter 매핑.

`register(provider, adapter)` 로 provider 엔티티와 어댑터 인스턴스를
등록하고, `get(provider_id)` 로 조회한다. 프로덕션에서는 App 시작 시 설정
파일 기반으로 주입하고, 테스트에서는 FakeProviderAdapter 를 등록한다.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..errors import NotFoundError
from ..schema.llm import Provider
from ._base import ProviderAdapter, ProviderHealth

__all__ = ["ProviderRegistry", "ProviderRegistryEntry"]


class ProviderRegistryEntry:
    """Provider 엔트리 (엔티티 + 어댑터 인스턴스 페어)."""

    def __init__(self, provider: Provider, adapter: ProviderAdapter) -> None:
        self.provider = provider
        self.adapter = adapter


class ProviderRegistry:
    """Provider 매핑 레지스트리."""

    def __init__(self) -> None:
        self._entries: dict[str, ProviderRegistryEntry] = {}

    def register(self, provider: Provider, adapter: ProviderAdapter) -> None:
        self._entries[provider.id] = ProviderRegistryEntry(provider, adapter)

    def get(self, provider_id: str) -> ProviderAdapter:
        entry = self._entries.get(provider_id)
        if entry is None:
            raise NotFoundError(
                f"provider not registered: {provider_id}",
                details={"provider_id": provider_id},
            )
        return entry.adapter

    def get_entry(self, provider_id: str) -> ProviderRegistryEntry:
        entry = self._entries.get(provider_id)
        if entry is None:
            raise NotFoundError(
                f"provider not registered: {provider_id}",
                details={"provider_id": provider_id},
            )
        return entry

    def list_providers(self) -> list[Provider]:
        return [e.provider for e in self._entries.values()]

    def __contains__(self, provider_id: object) -> bool:
        return isinstance(provider_id, str) and provider_id in self._entries

    def __len__(self) -> int:
        return len(self._entries)

    async def health_check_all(self) -> dict[str, ProviderHealth]:
        results: dict[str, ProviderHealth] = {}
        for pid, entry in self._entries.items():
            try:
                results[pid] = await entry.adapter.health()
            except Exception as exc:
                results[pid] = ProviderHealth(ok=False, message=type(exc).__name__)
        return results

    def entries(self) -> Iterable[ProviderRegistryEntry]:
        return list(self._entries.values())
