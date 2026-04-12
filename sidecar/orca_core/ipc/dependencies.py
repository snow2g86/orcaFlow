"""FastAPI dependency container.

M4 는 sidecar 자체에서 in-memory registries + optional Database 를
관리한다. Production 경로에서는 app lifespan 이 Database 를 초기화하고
roles/profiles 를 DB 로부터 로드하지만, M4 테스트는 AppServices 를 직접
생성해 주입한다.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging
from typing import Any, Literal

from fastapi import Request

from ..orchestrator import EventBus, GraphRunner, OrchestratorServices
from ..providers.registry import ProviderRegistry
from ..schema.agent import AgentRole
from ..schema.approval import ApprovalRequest
from ..schema.llm import LLMProfile
from ..schema.policy import Policy
from ..schema.workflow import Workflow
from ..tools.registry import ToolRegistry
from ..tools.runtime import ToolRuntime

__all__ = [
    "SYNTHETIC_FALLBACK_POLICY",
    "AppServices",
    "RunHandle",
    "get_services",
]

_logger = logging.getLogger("orca_core.ipc.dependencies")

# H9: Unified synthetic fallback policy. Both the chat path (planner) and
# the runs path use this identical object so test and prod semantics match.
# strict mode = deny-by-default; a fallback must never be more permissive
# than the explicit policies that failed to load.
SYNTHETIC_FALLBACK_POLICY: Policy = Policy(
    name="synthetic-fallback",
    mode="strict",
    rules=[],
)


@dataclass
class ChatSession:
    """In-memory chat session (M5 에서 DB 테이블로 승격)."""

    id: str
    turns: list[dict[str, Any]] = field(default_factory=list)


ApprovalResult = bool | Literal["cancelled"]


@dataclass
class RunHandle:
    """실행 중인 Run 의 task + cancellation + snapshot."""

    run_id: str
    task: asyncio.Task[None] | None
    context: Any  # RunContext (avoid cyclic import cost)
    pending_approvals: dict[str, asyncio.Event] = field(default_factory=dict)
    approval_results: dict[str, ApprovalResult] = field(default_factory=dict)
    snapshot: dict[str, Any] = field(default_factory=dict)

    def approve(self, approval_id: str) -> None:
        self.approval_results[approval_id] = True
        event = self.pending_approvals.get(approval_id)
        if event is not None:
            event.set()

    def reject(self, approval_id: str) -> None:
        self.approval_results[approval_id] = False
        event = self.pending_approvals.get(approval_id)
        if event is not None:
            event.set()


@dataclass
class AppServices:
    """Sidecar 전역 서비스 번들."""

    # Registries
    tool_registry: ToolRegistry
    provider_registry: ProviderRegistry
    tool_runtime: ToolRuntime
    event_bus: EventBus
    runner: GraphRunner

    # In-memory state (M4)
    workflows: dict[str, tuple[Workflow, str]] = field(default_factory=dict)
    roles: dict[str, AgentRole] = field(default_factory=dict)
    llm_profiles: dict[str, LLMProfile] = field(default_factory=dict)
    policies: dict[str, Policy] = field(default_factory=dict)
    runs: dict[str, RunHandle] = field(default_factory=dict)
    approvals: dict[str, ApprovalRequest] = field(default_factory=dict)
    chat_sessions: dict[str, ChatSession] = field(default_factory=dict)
    default_policy_id: str | None = None
    # H12: keep at most this many runs; oldest completed ones are evicted.
    run_retention: int = 50

    # Background tasks to cancel on shutdown
    background_tasks: list[asyncio.Task[Any]] = field(default_factory=list)

    def build_orchestrator_services(self) -> OrchestratorServices:
        return OrchestratorServices(
            tool_runtime=self.tool_runtime,
            tool_registry=self.tool_registry,
            provider_registry=self.provider_registry,
            event_bus=self.event_bus,
            roles=dict(self.roles),
            llm_profiles=dict(self.llm_profiles),
        )

    def resolve_policy(self, workflow: Workflow) -> Policy:
        if workflow.policy_id and workflow.policy_id in self.policies:
            return self.policies[workflow.policy_id]
        if self.default_policy_id and self.default_policy_id in self.policies:
            return self.policies[self.default_policy_id]
        if self.policies:
            return next(iter(self.policies.values()))
        # H9: Fallback — log + return the shared strict synthetic policy.
        _logger.warning(
            "policy.synthetic_fallback_used",
            extra={
                "event": "policy.synthetic_fallback_used",
                "caller": "runs.resolve_policy",
                "workflow_id": workflow.id,
            },
        )
        return SYNTHETIC_FALLBACK_POLICY

    async def cancel_all_runs(self) -> None:
        for handle in list(self.runs.values()):
            if handle.task and not handle.task.done():
                handle.task.cancel()
        for task in self.background_tasks:
            if not task.done():
                task.cancel()


def get_services(request: Request) -> AppServices:
    services: AppServices | None = getattr(request.app.state, "services", None)
    if services is None:
        raise RuntimeError("AppServices not attached to app.state.services")
    return services
