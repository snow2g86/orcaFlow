"""ProviderRegistry 커버리지 보강."""

from __future__ import annotations

import pytest

from orca_core.errors import NotFoundError
from orca_core.providers import FakeProviderAdapter, ProviderHealth, ProviderRegistry
from orca_core.schema import Provider


def _provider(name: str = "p1") -> Provider:
    return Provider(name=name, kind="openai_compatible", base_url="http://x")


def test_register_get_entry_and_list_providers():
    reg = ProviderRegistry()
    prov = _provider()
    adapter = FakeProviderAdapter()
    reg.register(prov, adapter)

    assert reg.get(prov.id) is adapter
    assert reg.get_entry(prov.id).provider.name == "p1"
    assert reg.list_providers()[0].id == prov.id
    assert len(reg) == 1
    assert prov.id in reg
    assert (42 in reg) is False
    assert len(list(reg.entries())) == 1


def test_get_missing_raises():
    reg = ProviderRegistry()
    with pytest.raises(NotFoundError):
        reg.get("nope")
    with pytest.raises(NotFoundError):
        reg.get_entry("nope")


async def test_health_check_all_handles_adapter_errors():
    class _Broken:
        kind = "ollama"

        async def health(self) -> ProviderHealth:
            raise RuntimeError("down")

        async def chat(self, req):  # pragma: no cover
            raise NotImplementedError

        async def stream_chat(self, req):  # pragma: no cover
            raise NotImplementedError

    reg = ProviderRegistry()
    prov = _provider("bad")
    reg.register(prov, _Broken())
    results = await reg.health_check_all()
    assert results[prov.id].ok is False
    assert results[prov.id].message == "RuntimeError"
