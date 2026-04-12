"""Policy engine (Domain layer).

순수 Pydantic + 표준 라이브러리 + pathspec 만 의존. I/O 금지.
design.md §6.3 참조.
"""

from __future__ import annotations

from .decision import Decision
from .engine import PolicyEngine, build_context
from .matcher import (
    extract_command,
    extract_hosts,
    matches_rule,
    normalize_path,
)
from .simulator import Scenario, SimulationResult, simulate_policy

__all__ = [
    "Decision",
    "PolicyEngine",
    "Scenario",
    "SimulationResult",
    "build_context",
    "extract_command",
    "extract_hosts",
    "matches_rule",
    "normalize_path",
    "simulate_policy",
]
