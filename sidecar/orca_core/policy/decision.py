"""Policy 평가 결과 객체."""

from __future__ import annotations

from dataclasses import dataclass

from ..schema.policy import RuleEffect

__all__ = ["Decision"]


@dataclass(frozen=True, slots=True)
class Decision:
    """PolicyEngine.evaluate 반환값.

    - `effect`: 최종 효과 (`allow|deny|ask|dry_run_only`)
    - `rule_id`: 효과를 만든 룰 ID (기본값 경로면 `None`)
    - `reason`: 사용자 표시용 이유 (없으면 `None`)
    - `matched`: 매칭된 룰이 있었는지 (False = 기본값 fallthrough)
    """

    effect: RuleEffect
    rule_id: str | None = None
    reason: str | None = None
    matched: bool = False
