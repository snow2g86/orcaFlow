"""ProviderSecretStore — InMemory 구현 테스트."""

from __future__ import annotations

import pytest

from orca_core.providers import InMemorySecretStore, ProviderSecretNotFoundError


async def test_set_and_get():
    store = InMemorySecretStore()
    store.set("k1", "value")
    assert await store.get("k1") == "value"


async def test_get_missing_raises():
    store = InMemorySecretStore()
    with pytest.raises(ProviderSecretNotFoundError):
        await store.get("missing")


async def test_init_with_dict():
    store = InMemorySecretStore({"k2": "v2"})
    assert await store.get("k2") == "v2"
