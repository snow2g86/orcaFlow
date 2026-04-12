"""Policy / PolicyRule (schema.md sections 3.8-3.9)."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import Field, model_validator

from ._base import OrcaModel, generate_uuid_v7

__all__ = [
    "Policy",
    "PolicyMode",
    "PolicyRule",
    "PolicyScope",
    "RuleEffect",
]

PolicyMode = Literal["strict", "ask", "trusted"]
"""Policy 기본 모드 (매칭 룰이 없을 때의 기본 효과).

- `strict`: 기본 `deny`
- `ask`: 기본 `ask` (사용자에게 승인 프롬프트)
- `trusted`: 기본 `allow`
"""

PolicyScope = Literal["fs_path", "shell_command", "network_host", "os_api", "tool_id"]
"""PolicyRule 대상 범위 (schema.md §3.9)."""

RuleEffect = Literal["allow", "deny", "ask", "dry_run_only"]
"""PolicyRule 적용 결과."""


class PolicyRule(OrcaModel):
    """단일 정책 규칙 (schema.md §3.9)."""

    id: str = Field(default_factory=generate_uuid_v7)
    policy_id: str = ""
    priority: int = Field(..., ge=0)
    scope: PolicyScope
    matcher: str
    effect: RuleEffect
    reason: str | None = None


class Policy(OrcaModel):
    """정책 집합 (schema.md §3.8).

    Invariant (schema.md §5 #6):
        `mode=strict` 에서 매칭 룰이 없으면 기본 `deny`.
        `trusted` 는 기본 `allow`. `ask` 는 기본 `ask`.
    """

    id: str = Field(default_factory=generate_uuid_v7)
    name: str
    mode: PolicyMode
    rules: list[PolicyRule] = Field(default_factory=list)
    require_dry_run_for: list[Literal["destructive", "write", "network"]] = Field(
        default_factory=list,
    )
    auto_approve_reversible: bool = False

    @model_validator(mode="after")
    def _validate_rules(self) -> Policy:
        # priority 중복은 모호성의 원인 → 금지
        seen: set[int] = set()
        for rule in self.rules:
            if rule.priority in seen:
                raise ValueError(
                    f"Policy '{self.name}' has duplicate rule priority {rule.priority}; "
                    "priorities must be unique per policy"
                )
            seen.add(rule.priority)
            # 소속 정책 id 전파
            if not rule.policy_id:
                rule.policy_id = self.id
            elif rule.policy_id != self.id:
                raise ValueError(
                    f"PolicyRule.policy_id '{rule.policy_id}' does not match "
                    f"parent Policy.id '{self.id}'"
                )
            # shell_command scope 의 regex 는 반드시 사전 컴파일 가능해야 함
            # (잘못된 정규식 deny 룰이 런타임에 조용히 무효화되는 버그 방지)
            if rule.scope == "shell_command":
                try:
                    re.compile(rule.matcher)
                except re.error as exc:
                    raise ValueError(
                        f"PolicyRule[priority={rule.priority}] has invalid regex "
                        f"matcher {rule.matcher!r}: {exc}"
                    ) from exc
        return self

    def default_effect(self) -> RuleEffect:
        """매칭 룰이 없을 때의 기본 효과를 반환."""
        if self.mode == "strict":
            return "deny"
        if self.mode == "trusted":
            return "allow"
        return "ask"
