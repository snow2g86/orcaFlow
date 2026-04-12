"""RunState — GraphRunner 가 노드 간 전달하는 워크플로우 실행 상태.

design.md 6.1.1: state 는 {messages, artifacts, plan, scratchpad} 키를
표준화한다. TypedDict 대신 dataclass 로 구현해 routing expression evaluator
가 attribute 접근(state.plan, state.messages 등) 으로 자연스럽게 읽을 수
있게 한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["RunState"]


@dataclass
class RunState:
    """Run 실행 동안 노드 간 전달되는 상태 객체.

    - messages: ChatMessage 호환 dict 리스트 (planner/routing expression 이
      읽을 수 있도록 dict 로 유지).
    - artifacts: key -> 임의 페이로드 (툴 결과 누적).
    - plan: planner 가 만든 중간 plan 객체 (Optional).
    - scratchpad: 노드 내부 temp 저장소.
    """

    messages: list[dict[str, Any]] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)
    plan: Any = None
    scratchpad: dict[str, Any] = field(default_factory=dict)

    def append_message(self, message: dict[str, Any]) -> None:
        self.messages.append(dict(message))

    def set_artifact(self, key: str, value: Any) -> None:
        self.artifacts[key] = value

    def to_dict(self) -> dict[str, Any]:
        return {
            "messages": list(self.messages),
            "artifacts": dict(self.artifacts),
            "plan": self.plan,
            "scratchpad": dict(self.scratchpad),
        }
