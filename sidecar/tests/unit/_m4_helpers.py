"""M4 테스트 헬퍼 — Fake provider, runner setup, 가벼운 mock tool."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from orca_core.orchestrator import (
    EventBus,
    GraphRunner,
    OrchestratorServices,
    RunCancellation,
    RunContext,
    RunState,
)
from orca_core.providers._base import (
    ChatMessage,
    ChatResponse,
    ChatToolCall,
    ChatUsage,
)
from orca_core.providers.fake import FakeProviderAdapter
from orca_core.providers.registry import ProviderRegistry
from orca_core.schema.agent import AgentRole
from orca_core.schema.llm import LLMProfile, Provider
from orca_core.schema.policy import Policy, PolicyRule
from orca_core.schema.tool import Permission
from orca_core.schema.workflow import AgentNode, Edge, Position, Workflow
from orca_core.tools._base import ToolContext, ToolResult
from orca_core.tools.registry import ToolRegistry
from orca_core.tools.runtime import ToolRuntime

from ._m3_helpers import InMemoryTransactionFactory

# ---------------------------------------------------------------------------
# Mock tool
# ---------------------------------------------------------------------------


@dataclass
class MockTool:
    """Minimal Tool implementation for orchestrator tests.

    Tracks invocations and returns a deterministic result.
    """

    id: str = "fs.read_file"
    namespace: str = "fs"
    side_effect: str = "read"
    reversible: bool = False
    default_dry_run: bool = False
    timeout_ms: int = 5000
    max_output_bytes: int = 1024
    description: str = "mock tool"
    invocations: list[dict[str, Any]] = field(default_factory=list)
    returns: dict[str, Any] = field(default_factory=lambda: {"ok": True})
    fail: bool = False

    def input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"path": {"type": "string"}}}

    def output_schema(self) -> dict[str, Any]:
        return {"type": "object"}

    def permissions(self) -> list[Permission]:
        return []

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        self.invocations.append(dict(args))
        if self.fail:
            raise RuntimeError("mock tool failed")
        return ToolResult(output=dict(self.returns))

    async def dry_run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        return ToolResult(output=dict(self.returns), diff_preview={"would": "do"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_response_with_tool_call(
    tool_id: str,
    args: dict[str, Any] | None = None,
    *,
    call_id: str = "call-1",
    text: str = "",
) -> ChatResponse:
    return ChatResponse(
        model="fake-model",
        message=ChatMessage(
            role="assistant",
            content=text,
            tool_calls=[ChatToolCall(id=call_id, name=tool_id, arguments=args or {})],
        ),
        finish_reason="tool_calls",
        usage=ChatUsage(),
    )


def make_response_text(text: str) -> ChatResponse:
    return ChatResponse(
        model="fake-model",
        message=ChatMessage(role="assistant", content=text),
        finish_reason="stop",
        usage=ChatUsage(),
    )


def make_workflow(
    nodes: list[tuple[str, str]],
    edges: list[tuple[str, str, str | None]],
    entrypoint: str,
) -> Workflow:
    """nodes: [(id, role_name)], edges: [(from, to, condition_or_None)]"""
    n = [AgentNode(id=nid, role=role, position=Position(x=0, y=0)) for (nid, role) in nodes]
    e = [
        Edge.model_validate({"from": src, "to": dst, "condition": cond})
        for (src, dst, cond) in edges
    ]
    return Workflow(name="test-wf", nodes=n, edges=e, entrypoint=entrypoint)


def make_role(
    name: str,
    *,
    tools: list[str] | None = None,
    role_type: str = "worker",
    llm_profile_id: str = "profile-1",
) -> AgentRole:
    return AgentRole(
        name=name,
        role_type=role_type,  # type: ignore[arg-type]
        system_prompt=f"You are {name}",
        tools=tools or [],
        llm_profile_id=llm_profile_id,
    )


def make_profile(
    *,
    profile_id: str = "profile-1",
    provider_id: str = "provider-1",
    is_planner: bool = False,
    is_default: bool = True,
) -> LLMProfile:
    return LLMProfile(
        id=profile_id,
        name=profile_id,
        provider_id=provider_id,
        model="fake-model",
        is_tool_capable=True,
        is_planner=is_planner,
        is_default=is_default,
    )


def build_services(
    fake: FakeProviderAdapter,
    *,
    roles: dict[str, AgentRole] | None = None,
    tools: list[Any] | None = None,
    audit_log_path: Any,
    journal_base: Any,
) -> OrchestratorServices:
    provider = Provider(id="provider-1", name="fake", kind="openai_compatible", base_url="x")
    registry = ProviderRegistry()
    registry.register(provider, fake)

    profile = make_profile(profile_id="profile-1", provider_id=provider.id)

    tool_registry = ToolRegistry()
    for t in tools or []:
        tool_registry.register(t)

    txn = InMemoryTransactionFactory()
    runtime = ToolRuntime(
        transaction_factory=txn,
        audit_log_path=audit_log_path,
        journal_base_dir=journal_base,
    )

    return OrchestratorServices(
        tool_runtime=runtime,
        tool_registry=tool_registry,
        provider_registry=registry,
        event_bus=EventBus(),
        roles=dict(roles or {}),
        llm_profiles={profile.id: profile},
    )


def make_run_context(
    services: OrchestratorServices,
    workflow: Workflow,
    *,
    policy: Policy | None = None,
    run_id: str = "run-1",
) -> RunContext:
    return RunContext(
        run_id=run_id,
        workflow=workflow,
        policy=policy or Policy(name="trusted", mode="trusted", rules=[]),
        services=services,
        cancellation=RunCancellation(),
        initial_state=RunState(),
        inputs={},
        dry_run=False,
    )


def make_runner(approval_waiter: Any = None) -> GraphRunner:
    return GraphRunner(approval_waiter=approval_waiter)


def make_ask_policy() -> Policy:
    return Policy(
        name="ask-policy",
        mode="ask",
        rules=[
            PolicyRule(priority=10, scope="tool_id", matcher="fs.read_file", effect="ask"),
        ],
    )
