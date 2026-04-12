"""RunContext — GraphRunner 실행 컨텍스트 및 리소스 바인딩.

Orchestrator 는 persistence / providers / tools / audit / journal 을
DIP (의존성 주입) 로 받는다. Run 단위로 고정되는 설정(정책, 워크플로우,
cancellation) 과 static 서비스(레지스트리, bus 등) 를 분리한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..providers._base import ProviderAdapter
from ..providers.registry import ProviderRegistry
from ..schema.agent import AgentRole
from ..schema.llm import LLMProfile
from ..schema.policy import Policy
from ..schema.workflow import Workflow
from ..tools.registry import ToolRegistry
from ..tools.runtime import ToolRuntime
from .cancel import RunCancellation
from .events import EventBus
from .state import RunState

__all__ = ["OrchestratorServices", "RunContext"]


@dataclass
class OrchestratorServices:
    """Orchestrator 가 Run 독립적으로 공유하는 서비스 번들.

    GraphRunner / Planner 가 동일 인스턴스를 공유한다.
    """

    tool_runtime: ToolRuntime
    tool_registry: ToolRegistry
    provider_registry: ProviderRegistry
    event_bus: EventBus
    # roles / llm_profiles 은 DB 대신 in-memory lookup 을 기본값으로 받되,
    # 테스트는 dict 로 직접 주입할 수 있다.
    roles: dict[str, AgentRole] = field(default_factory=dict)
    llm_profiles: dict[str, LLMProfile] = field(default_factory=dict)

    def resolve_provider_for_profile(self, profile: LLMProfile) -> ProviderAdapter:
        return self.provider_registry.get(profile.provider_id)

    def select_planner_profile(self) -> LLMProfile | None:
        """is_planner=True 인 프로파일을 우선, 그다음 is_default."""
        planner = [p for p in self.llm_profiles.values() if p.is_planner]
        if planner:
            return planner[0]
        default = [p for p in self.llm_profiles.values() if p.is_default]
        if default:
            return default[0]
        if self.llm_profiles:
            return next(iter(self.llm_profiles.values()))
        return None


@dataclass
class RunContext:
    """단일 Run 실행 동안 고정되는 상태."""

    run_id: str
    workflow: Workflow
    policy: Policy
    services: OrchestratorServices
    cancellation: RunCancellation
    initial_state: RunState = field(default_factory=RunState)
    inputs: dict[str, Any] = field(default_factory=dict)
    dry_run: bool = False
