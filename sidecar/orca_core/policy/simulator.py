"""Policy 시뮬레이터 (design.md §6.3.3).

주어진 Policy 와 시나리오 리스트(tool_id + args)를 받아 각 시나리오의 효과를
미리 계산한다. 순수 함수.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..schema.policy import Policy
from .decision import Decision
from .engine import PolicyEngine

__all__ = ["Scenario", "SimulationResult", "simulate_policy"]


@dataclass(frozen=True, slots=True)
class Scenario:
    """시뮬레이션 시나리오 1건."""

    tool_id: str
    args: dict[str, Any]


@dataclass(frozen=True, slots=True)
class SimulationResult:
    """시뮬레이션 결과 1건."""

    scenario: Scenario
    decision: Decision


def simulate_policy(policy: Policy, scenarios: list[Scenario]) -> list[SimulationResult]:
    """시나리오 배열에 대해 Policy 를 평가해 결과 배열을 반환."""
    engine = PolicyEngine()
    results: list[SimulationResult] = []
    for sc in scenarios:
        decision = engine.evaluate(policy, tool_id=sc.tool_id, args=sc.args)
        results.append(SimulationResult(scenario=sc, decision=decision))
    return results
