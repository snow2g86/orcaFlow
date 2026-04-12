"""Planner — 자연어 턴을 Workflow YAML 로 변환 (design.md 6.1.2).

- is_planner=True 인 LLMProfile 을 우선 사용, 없으면 is_default.
- 구조화 출력 강제: function calling 을 지원하면 단일 tool `submit_workflow`
  를 노출, 미지원이면 JSON 블록 프롬프트 fallback.
- 응답 파싱 -> YAML -> Workflow.model_validate -> 실패 시 1회 재시도.
- 2회 연속 실패 -> PlannerError.
- 참조 무결성 + 정책 정적 검증 후 PlannerOutput 반환.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
import yaml

from ..policy.engine import PolicyEngine
from ..providers._base import (
    ChatMessage,
    ChatRequest,
    ChatToolDefinition,
    ProviderAdapter,
)
from ..schema.agent import AgentRole
from ..schema.llm import LLMProfile
from ..schema.policy import Policy
from ..schema.run import ConversationTurn
from ..schema.workflow import Workflow
from ..tools._base import Tool
from .errors import PlannerError, ResolutionError

__all__ = ["Planner", "PlannerOutput"]

_LOGGER = logging.getLogger("orca_core.orchestrator.planner")

_SUBMIT_TOOL = "submit_workflow"


class PlannerOutput(BaseModel):
    """구조화된 플래너 응답 (design.md 6.1.2)."""

    model_config = ConfigDict(extra="forbid")

    intent: str
    reasoning: str
    workflow_yaml: str
    expected_effects: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "medium"
    questions: list[str] = Field(default_factory=list)


class Planner:
    """자연어 -> Workflow YAML 변환 파이프라인."""

    def __init__(
        self,
        *,
        adapter: ProviderAdapter,
        profile: LLMProfile,
    ) -> None:
        self._adapter = adapter
        self._profile = profile
        self._policy_engine = PolicyEngine()

    async def plan(
        self,
        turn: ConversationTurn,
        *,
        roles: dict[str, AgentRole],
        tools: dict[str, Tool],
        policy: Policy,
        context: dict[str, Any] | None = None,
    ) -> PlannerOutput:
        """turn.user_text 를 처리해 PlannerOutput 반환.

        Raises:
            PlannerError : 파싱/검증 2회 연속 실패.
        """
        system = self._build_system_prompt(roles, tools, policy)
        user_msg = ChatMessage(role="user", content=turn.user_text)
        tool_defs = self._build_tool_defs() if self._profile.is_tool_capable else []
        messages: list[ChatMessage] = [
            ChatMessage(role="system", content=system),
            user_msg,
        ]

        last_error: str | None = None
        last_stage: str = "unknown"
        last_raw_preview: str | None = None
        last_exc: BaseException | None = None
        attempts = 2
        for attempt in range(attempts):
            if attempt == 1 and last_error:
                messages.append(
                    ChatMessage(
                        role="user",
                        content=(
                            "Your previous output failed validation: "
                            f"{last_error}. Return a corrected response."
                        ),
                    )
                )

            req = ChatRequest(
                model=self._profile.model,
                messages=messages,
                tools=tool_defs,
                tool_choice="required" if tool_defs else None,
                temperature=self._profile.params.get("temperature"),
            )
            response = await self._adapter.chat(req)
            raw_preview = (response.message.content or "")[:200]
            parsed, stage = self._extract_payload(response)
            last_stage = stage
            last_raw_preview = raw_preview
            if parsed is None:
                last_error = f"{stage}: expected submit_workflow tool call or JSON object"
                last_exc = None
                continue
            try:
                draft = PlannerOutput.model_validate(parsed)
            except ValidationError as exc:
                last_stage = "planner_output_schema"
                last_error = f"planner_output_schema: {exc.errors()[:1]}"
                last_exc = exc
                continue
            # Validate the generated Workflow
            try:
                workflow = self._parse_workflow(draft.workflow_yaml)
            except (yaml.YAMLError, ValidationError, ValueError, TypeError) as exc:
                last_stage = "workflow_yaml"
                last_error = f"workflow_yaml: {exc}"
                last_exc = exc
                continue
            try:
                self._validate_references(workflow, roles=roles, tools=tools)
            except ResolutionError as exc:
                last_stage = "workflow_references"
                last_error = f"workflow_references: {exc.message}"
                last_exc = exc
                continue
            # Static policy check + derive expected effects
            expected = self._derive_expected_effects(
                workflow, roles=roles, tools=tools, policy=policy
            )
            return draft.model_copy(update={"expected_effects": expected})

        raise PlannerError(
            f"planner failed after {attempts} attempts: {last_error}",
            details={
                "stage": last_stage,
                "raw_preview": last_raw_preview,
                "attempts": attempts,
                "last_error": last_error,
            },
        ) from last_exc

    # ------------------------------------------------------------------
    # Prompt / payload helpers
    # ------------------------------------------------------------------

    def _build_system_prompt(
        self,
        roles: dict[str, AgentRole],
        tools: dict[str, Tool],
        policy: Policy,
    ) -> str:
        role_desc = "\n".join(
            f"- {r.name} ({r.role_type}): {r.goal or r.system_prompt[:120]}" for r in roles.values()
        )
        tool_desc = "\n".join(
            f"- {t.id} (side_effect={t.side_effect}, reversible={t.reversible})"
            for t in tools.values()
        )
        return (
            "You are the OrcaFlow Planner. Convert the user request into a "
            "Workflow YAML graph using the available AgentRoles and tools. "
            "You MUST call the submit_workflow function with a PlannerOutput "
            "payload: { intent, reasoning, workflow_yaml, expected_effects, "
            "confidence, questions }.\n\n"
            f"Available roles:\n{role_desc or '(none)'}\n\n"
            f"Available tools:\n{tool_desc or '(none)'}\n\n"
            f"Policy mode: {policy.mode}. Respect deny rules when choosing tools."
        )

    def _build_tool_defs(self) -> list[ChatToolDefinition]:
        return [
            ChatToolDefinition(
                name=_SUBMIT_TOOL,
                description="Submit the generated workflow for execution.",
                parameters={
                    "type": "object",
                    "required": ["intent", "workflow_yaml"],
                    "properties": {
                        "intent": {"type": "string"},
                        "reasoning": {"type": "string"},
                        "workflow_yaml": {"type": "string"},
                        "expected_effects": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                        },
                        "questions": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
            )
        ]

    def _extract_payload(self, response: Any) -> tuple[dict[str, Any] | None, str]:
        """submit_workflow tool call 우선, 없으면 content 내 JSON 블록.

        Returns:
            (payload_or_None, stage_label). The stage label reflects which
            parsing path was attempted last so the caller can record it in
            structured error details.
        """
        message = response.message
        if message.tool_calls:
            for call in message.tool_calls:
                if call.name == _SUBMIT_TOOL:
                    return dict(call.arguments), "tool_call"
        content = (message.content or "").strip()
        if not content:
            _LOGGER.warning(
                "planner.payload_unparseable",
                extra={
                    "event": "planner.payload_unparseable",
                    "stage": "empty_content",
                    "raw_preview": content[:200],
                    "has_tool_calls": bool(message.tool_calls),
                },
            )
            return None, "empty_content"
        try:
            return json.loads(content), "content_json"
        except json.JSONDecodeError:
            # last resort: try to locate a JSON block between braces
            start = content.find("{")
            end = content.rfind("}")
            if start >= 0 and end > start:
                try:
                    return (
                        json.loads(content[start : end + 1]),
                        "content_json_block",
                    )
                except json.JSONDecodeError:
                    _LOGGER.warning(
                        "planner.payload_unparseable",
                        extra={
                            "event": "planner.payload_unparseable",
                            "stage": "content_json_block",
                            "raw_preview": content[:200],
                            "has_tool_calls": bool(message.tool_calls),
                        },
                    )
                    return None, "content_json_block"
            _LOGGER.warning(
                "planner.payload_unparseable",
                extra={
                    "event": "planner.payload_unparseable",
                    "stage": "content_json",
                    "raw_preview": content[:200],
                    "has_tool_calls": bool(message.tool_calls),
                },
            )
            return None, "content_json"

    # ------------------------------------------------------------------
    # Workflow validation
    # ------------------------------------------------------------------

    def _parse_workflow(self, workflow_yaml: str) -> Workflow:
        parsed = yaml.safe_load(workflow_yaml)
        if not isinstance(parsed, dict):
            raise TypeError("workflow YAML root must be a mapping")
        return Workflow.model_validate(parsed)

    def _collect_workflow_tool_ids(
        self,
        workflow: Workflow,
        *,
        roles: dict[str, AgentRole],
    ) -> set[str]:
        """H10: workflow 에 실제 등장하는 role 의 tool ID 집합.

        노드가 참조하는 role 만 순회하고, 그 role 의 tool 을 합집합으로 반환.
        M4 스키마에는 node-level tool pinning 이 없으므로 role.tools 가
        최소 상한이 된다. 등장하지 않은 role 의 툴은 포함하지 않는다.
        """
        result: set[str] = set()
        for node in workflow.nodes:
            role = roles.get(node.role)
            if role is None:
                continue
            for tool_id in role.tools:
                result.add(tool_id)
        return result

    def _validate_references(
        self,
        workflow: Workflow,
        *,
        roles: dict[str, AgentRole],
        tools: dict[str, Tool],
    ) -> None:
        missing: list[str] = []
        for node in workflow.nodes:
            if node.role not in roles:
                missing.append(f"role:{node.role}")
                continue
            role = roles[node.role]
            # H10: only validate tool ids actually referenced by roles in
            # this workflow, not roles that happen to exist in the registry.
            for tool_id in role.tools:
                if tool_id not in tools:
                    missing.append(f"tool:{tool_id}")
        if missing:
            raise ResolutionError(
                "workflow references unknown entities",
                missing=sorted(set(missing)),
            )

    def _derive_expected_effects(
        self,
        workflow: Workflow,
        *,
        roles: dict[str, AgentRole],
        tools: dict[str, Tool],
        policy: Policy,
    ) -> list[str]:
        """정책 정적 검증 — workflow 에 등장하는 tool_id 에 한정 (H10)."""
        summary: list[str] = []
        seen: set[str] = set()
        relevant_ids = self._collect_workflow_tool_ids(workflow, roles=roles)
        for tool_id in sorted(relevant_ids):
            if tool_id in seen or tool_id not in tools:
                continue
            seen.add(tool_id)
            tool = tools[tool_id]
            decision = self._policy_engine.evaluate(policy, tool_id=tool_id, args={})
            if decision.effect == "deny":
                summary.append(f"{tool_id}: DENIED ({decision.reason})")
            elif decision.effect == "ask":
                summary.append(f"{tool_id}: requires approval")
            elif tool.side_effect in ("write", "destructive"):
                summary.append(f"{tool_id}: {tool.side_effect} side-effect")
        return summary
