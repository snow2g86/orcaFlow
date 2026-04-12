"""Integration test fixtures — FastAPI TestClient + AppServices wired with
FakeProviderAdapter and in-memory ToolRuntime."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from orca_core.config import Config
from orca_core.ipc.dependencies import AppServices
from orca_core.ipc.http_app import create_app
from orca_core.orchestrator import EventBus, GraphRunner
from orca_core.providers.fake import FakeProviderAdapter
from orca_core.providers.registry import ProviderRegistry
from orca_core.schema.llm import LLMProfile, Provider
from orca_core.schema.policy import Policy
from orca_core.tools.registry import ToolRegistry
from orca_core.tools.runtime import ToolRuntime
from tests.unit._m3_helpers import InMemoryTransactionFactory


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Path:
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "journal").mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def fake_adapter() -> FakeProviderAdapter:
    return FakeProviderAdapter(strict=False)


@pytest.fixture
def app_services(tmp_workspace: Path, fake_adapter: FakeProviderAdapter) -> AppServices:
    provider = Provider(
        id="prov-1",
        name="fake",
        kind="openai_compatible",
        base_url="http://x",
    )
    registry = ProviderRegistry()
    registry.register(provider, fake_adapter)

    profile = LLMProfile(
        id="profile-1",
        name="profile-1",
        provider_id=provider.id,
        model="fake-model",
        is_tool_capable=True,
        is_planner=True,
        is_default=True,
    )

    txn = InMemoryTransactionFactory()
    runtime = ToolRuntime(
        transaction_factory=txn,
        audit_log_path=tmp_workspace / "logs" / "audit.log",
        journal_base_dir=tmp_workspace / "journal",
    )

    services = AppServices(
        tool_registry=ToolRegistry(),
        provider_registry=registry,
        tool_runtime=runtime,
        event_bus=EventBus(),
        runner=GraphRunner(),
    )
    services.llm_profiles[profile.id] = profile
    policy = Policy(name="trusted", mode="trusted", rules=[])
    services.policies[policy.id] = policy
    services.default_policy_id = policy.id
    return services


@pytest.fixture
def app(app_services: AppServices) -> Iterator[TestClient]:
    config = Config()
    test_token = "test-token"
    fastapi_app = create_app(config=config, token=test_token, services=app_services)
    with TestClient(fastapi_app, headers={"x-orca-token": test_token}) as client:
        yield client
