"""OrchestratorServices / RunContext / RunCancellation."""

from __future__ import annotations

import pytest

from orca_core.orchestrator import (
    EventBus,
    OrchestratorServices,
    RunCancellation,
    RunState,
)
from orca_core.providers.fake import FakeProviderAdapter
from orca_core.providers.registry import ProviderRegistry
from orca_core.schema.llm import LLMProfile, Provider
from orca_core.tools.registry import ToolRegistry

from ._m4_helpers import build_services, make_profile


def _provider() -> Provider:
    return Provider(id="p1", name="x", kind="openai_compatible", base_url="x")


def test_resolve_provider_for_profile():
    fake = FakeProviderAdapter()
    reg = ProviderRegistry()
    p = _provider()
    reg.register(p, fake)
    services = OrchestratorServices(
        tool_runtime=None,  # type: ignore[arg-type]
        tool_registry=ToolRegistry(),
        provider_registry=reg,
        event_bus=EventBus(),
        llm_profiles={},
    )
    profile = LLMProfile(
        id="lp1",
        name="lp1",
        provider_id="p1",
        model="x",
    )
    assert services.resolve_provider_for_profile(profile) is fake


def test_select_planner_profile_priority():
    services = OrchestratorServices(
        tool_runtime=None,  # type: ignore[arg-type]
        tool_registry=ToolRegistry(),
        provider_registry=ProviderRegistry(),
        event_bus=EventBus(),
        llm_profiles={
            "default": make_profile(profile_id="default", is_planner=False, is_default=True),
            "planner": make_profile(profile_id="planner", is_planner=True, is_default=False),
        },
    )
    sel = services.select_planner_profile()
    assert sel is not None
    assert sel.id == "planner"


def test_select_default_when_no_planner():
    services = OrchestratorServices(
        tool_runtime=None,  # type: ignore[arg-type]
        tool_registry=ToolRegistry(),
        provider_registry=ProviderRegistry(),
        event_bus=EventBus(),
        llm_profiles={
            "default": make_profile(profile_id="default", is_planner=False, is_default=True),
        },
    )
    sel = services.select_planner_profile()
    assert sel is not None
    assert sel.id == "default"


def test_select_first_when_no_planner_no_default():
    services = OrchestratorServices(
        tool_runtime=None,  # type: ignore[arg-type]
        tool_registry=ToolRegistry(),
        provider_registry=ProviderRegistry(),
        event_bus=EventBus(),
        llm_profiles={
            "x": make_profile(profile_id="x", is_planner=False, is_default=False),
        },
    )
    sel = services.select_planner_profile()
    assert sel is not None


def test_select_returns_none_when_empty():
    services = OrchestratorServices(
        tool_runtime=None,  # type: ignore[arg-type]
        tool_registry=ToolRegistry(),
        provider_registry=ProviderRegistry(),
        event_bus=EventBus(),
        llm_profiles={},
    )
    assert services.select_planner_profile() is None


def test_run_cancellation():
    rc = RunCancellation()
    assert rc.is_cancelled() is False
    rc.cancel()
    assert rc.is_cancelled() is True
    assert rc.token.is_cancelled() is True


@pytest.mark.asyncio
async def test_run_cancellation_wait():
    rc = RunCancellation()
    rc.cancel()
    await rc.wait()  # should return immediately


def test_run_state_helpers():
    state = RunState()
    state.append_message({"role": "user", "content": "hi"})
    state.set_artifact("k", {"v": 1})
    snap = state.to_dict()
    assert snap["messages"] == [{"role": "user", "content": "hi"}]
    assert snap["artifacts"]["k"] == {"v": 1}


# Build services helper smoke
def test_build_services_smoke(tmp_path):
    fake = FakeProviderAdapter()
    s = build_services(
        fake,
        roles={},
        tools=[],
        audit_log_path=tmp_path / "audit.log",
        journal_base=tmp_path / "journal",
    )
    assert "profile-1" in s.llm_profiles
