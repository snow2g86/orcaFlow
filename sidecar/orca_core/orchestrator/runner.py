"""GraphRunner — Workflow DAG 실행 엔진 (design.md 6.1.1).

실행 루프 개요:
    1. run.started 이벤트 + Run.status=running
    2. BFS / 토폴로지 순서로 노드 큐를 소진
    3. 각 노드마다:
       a. AgentRole 해석
       b. ChatRequest 구성 (system=role.system_prompt, messages=state.messages,
          tools=role 의 tools 메타)
       c. Provider.chat 호출 -> ChatResponse
       d. response.tool_calls 가 있으면 ToolRuntime.invoke 로 각각 실행
          - approval_pending 이면 Run.status=awaiting_approval 저장 후 대기
          - 승인 후 approval_override=True 로 재호출
       e. 라우팅: edge.condition 평가 후 다음 노드들 큐에 추가
    4. 예외 시 Run.status=failed, cancel 시 run.cancelled
"""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
import logging
from typing import Any, Literal

from ..providers._base import (
    ChatMessage,
    ChatRequest,
    ChatToolCall,
    ChatToolDefinition,
)
from ..schema._base import generate_uuid_v7
from ..schema.agent import AgentRole
from ..schema.approval import ApprovalRequest
from ..schema.workflow import AgentNode, Edge, Workflow
from ..tools.runtime import ToolInvocationResult
from .context import RunContext
from .errors import (
    ApprovalCancelledError,
    ApprovalExpiredError,
    OrchestratorError,
    ResolutionError,
    RunCancelledError,
    RunningError,
)
from .routing import evaluate_condition
from .state import RunState

__all__ = ["GraphRunner", "NodeResult"]

_LOGGER = logging.getLogger("orca_core.orchestrator.runner")


class NodeResult:
    """단일 노드 실행 결과 (private helper 용)."""

    __slots__ = ("approval", "next_ids", "succeeded")

    def __init__(
        self,
        *,
        succeeded: bool,
        next_ids: list[str] | None = None,
        approval: ApprovalRequest | None = None,
    ) -> None:
        self.succeeded = succeeded
        self.next_ids = next_ids or []
        self.approval = approval


class _NodeFailureError(Exception):
    """Internal marker — `_execute_node` raises this when a tool call reports
    failure. `_execute_loop` catches it to emit `run_step.failed` and then
    converts to `RunningError` so the outer `run()` emits `run.failed`.
    """

    def __init__(
        self,
        *,
        error: dict[str, Any],
        tool_call_id: str | None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(error.get("message", "node failed"))
        self.error = error
        self.tool_call_id = tool_call_id
        self.cause = cause


# Approval decision awaiter: async callable that receives an ApprovalRequest
# and returns True on approve, False on reject. The HTTP layer wires this to
# an `asyncio.Event` keyed by approval_id. H2/H4: waiters may raise
# `ApprovalExpiredError` (TTL) or `ApprovalCancelledError` (user cancel during
# approval wait) — both distinguished from plain reject.
ApprovalWaiter = Callable[[ApprovalRequest], Awaitable[bool]]

DispatchOutcome = Literal["ok", "failed", "cancelled", "approved"]


class GraphRunner:
    """Workflow DAG 의 실행 루프."""

    def __init__(
        self,
        *,
        approval_waiter: ApprovalWaiter | None = None,
        status_sink: Any = None,
    ) -> None:
        """
        Parameters:
            approval_waiter : ask 분기에서 승인 결과를 기다리는 async 콜러블.
                기본 None 이면 즉시 실패(no-op). HTTP 레이어는 ApprovalRegistry
                기반 waiter 를 주입한다.
            status_sink : Optional object with async method
                `set_run_status(run_id, status, ended_at=None, error=None)`.
                DB 기반 런너는 RunsRepository 를 감싸서 주입하고,
                테스트는 in-memory mock 을 주입할 수 있다.
        """
        self._approval_waiter = approval_waiter
        self._status_sink = status_sink

    async def run(self, ctx: RunContext) -> None:
        """Run 실행. 예외는 run.failed 이벤트로 매핑한 뒤 raise."""
        bus = ctx.services.event_bus
        state = ctx.initial_state
        try:
            await self._set_status(ctx.run_id, "running")
            await bus.emit(
                ctx.run_id,
                "run.started",
                {"run_id": ctx.run_id, "workflow_id": ctx.workflow.id},
            )
            await self._execute_loop(ctx, state)
        except (RunCancelledError, ApprovalCancelledError):
            await bus.emit(ctx.run_id, "run.cancelled", {"run_id": ctx.run_id})
            await self._set_status(
                ctx.run_id,
                "cancelled",
                ended_at=datetime.now(tz=UTC),
                terminal=True,
            )
            await bus.close_run(ctx.run_id)
            return
        except OrchestratorError as exc:
            await bus.emit(
                ctx.run_id,
                "run.failed",
                {"run_id": ctx.run_id, "code": exc.code, "message": exc.message},
            )
            await self._set_status(
                ctx.run_id,
                "failed",
                ended_at=datetime.now(tz=UTC),
                error={"code": exc.code, "message": exc.message, "details": exc.details},
                terminal=True,
            )
            await bus.close_run(ctx.run_id)
            raise
        except Exception as exc:
            _LOGGER.exception(
                "run.failed_unexpected",
                extra={"event": "run.failed", "run_id": ctx.run_id},
            )
            await bus.emit(
                ctx.run_id,
                "run.failed",
                {"run_id": ctx.run_id, "code": "run.runtime_error", "message": str(exc)},
            )
            await self._set_status(
                ctx.run_id,
                "failed",
                ended_at=datetime.now(tz=UTC),
                error={"code": "run.runtime_error", "message": str(exc)},
                terminal=True,
            )
            await bus.close_run(ctx.run_id)
            raise RunningError(str(exc)) from exc

        await bus.emit(
            ctx.run_id,
            "run.succeeded",
            {"run_id": ctx.run_id, "stats": {"messages": len(state.messages)}},
        )
        await self._set_status(
            ctx.run_id,
            "succeeded",
            ended_at=datetime.now(tz=UTC),
            terminal=True,
        )
        await bus.close_run(ctx.run_id)

    # ------------------------------------------------------------------
    # Execution loop
    # ------------------------------------------------------------------

    async def _execute_loop(self, ctx: RunContext, state: RunState) -> None:
        queue: deque[str] = deque([ctx.workflow.entrypoint_node_id])
        visited: set[str] = set()
        node_map = {n.id: n for n in ctx.workflow.nodes}

        while queue:
            if ctx.cancellation.is_cancelled():
                raise RunCancelledError("run cancelled by user")
            node_id = queue.popleft()
            if node_id in visited:
                continue
            visited.add(node_id)
            node = node_map.get(node_id)
            if node is None:
                raise ResolutionError(f"node '{node_id}' not in workflow")

            role = self._resolve_role(ctx, node)
            run_step_id = generate_uuid_v7()
            await ctx.services.event_bus.emit(
                ctx.run_id,
                "run_step.started",
                {
                    "node_id": node_id,
                    "run_step_id": run_step_id,
                    "role": role.name,
                    "kind": "llm_call",
                },
            )
            try:
                result = await self._execute_node(ctx, node, role, state, run_step_id)
            except _NodeFailureError as failure:
                # H1: tool failure or other per-step error → emit run_step.failed
                # and propagate as RunningError so run.failed is emitted.
                await ctx.services.event_bus.emit(
                    ctx.run_id,
                    "run_step.failed",
                    {
                        "node_id": node_id,
                        "run_step_id": run_step_id,
                        "tool_call_id": failure.tool_call_id,
                        "error": failure.error,
                    },
                )
                raise RunningError(
                    f"run step failed: {failure.error.get('message', 'unknown')}",
                    details={
                        "code": "run.step_failed",
                        "node_id": node_id,
                        "run_step_id": run_step_id,
                        **failure.error,
                    },
                ) from failure.cause
            await ctx.services.event_bus.emit(
                ctx.run_id,
                "run_step.succeeded",
                {
                    "node_id": node_id,
                    "run_step_id": run_step_id,
                    "next": result.next_ids,
                },
            )
            for nxt in result.next_ids:
                if nxt not in visited:
                    queue.append(nxt)

    def _resolve_role(self, ctx: RunContext, node: AgentNode) -> AgentRole:
        role = ctx.services.roles.get(node.role)
        if role is None:
            raise ResolutionError(
                f"role '{node.role}' not registered",
                missing=[node.role],
            )
        return role

    async def _execute_node(
        self,
        ctx: RunContext,
        node: AgentNode,
        role: AgentRole,
        state: RunState,
        run_step_id: str,
    ) -> NodeResult:
        """단일 노드 실행 = LLM 호출 + tool dispatch + routing."""
        profile = ctx.services.llm_profiles.get(role.llm_profile_id)
        if profile is None:
            raise ResolutionError(
                f"llm_profile '{role.llm_profile_id}' not registered",
                missing=[role.llm_profile_id],
            )
        adapter = ctx.services.resolve_provider_for_profile(profile)

        tools_meta = self._build_tool_definitions(ctx, role)
        messages = self._build_messages(role, state)

        response = await adapter.chat(
            ChatRequest(
                model=profile.model,
                messages=messages,
                tools=tools_meta,
                tool_choice="auto" if tools_meta else None,
            )
        )
        assistant = response.message
        # Append assistant message to state
        state.append_message(
            {
                "role": "assistant",
                "content": assistant.content,
                "tool_calls": [tc.model_dump() for tc in assistant.tool_calls],
            }
        )

        # Dispatch tool calls (serially — enough for M4 MVP)
        for tool_call in assistant.tool_calls:
            outcome = await self._dispatch_tool_call(
                ctx, role, state, node, tool_call, run_step_id=run_step_id
            )
            if outcome == "cancelled":
                raise RunCancelledError("cancelled during tool execution")
            if outcome == "failed":
                # H1: bubble a typed marker so _execute_loop emits
                # run_step.failed before converting to RunningError.
                raise _NodeFailureError(
                    error={
                        "code": "tool.failed",
                        "tool_id": tool_call.name,
                        "message": "tool reported failure",
                    },
                    tool_call_id=tool_call.id,
                )

        # Compute next nodes via edges (after tool calls are done)
        next_ids = self._route(ctx.workflow, node.id, state)
        return NodeResult(succeeded=True, next_ids=next_ids)

    def _build_messages(self, role: AgentRole, state: RunState) -> list[ChatMessage]:
        system = ChatMessage(role="system", content=role.system_prompt)
        msgs: list[ChatMessage] = [system]
        for raw in state.messages:
            # Keep only fields understood by ChatMessage
            r = raw.get("role", "assistant")
            content = raw.get("content", "")
            tool_calls_raw = raw.get("tool_calls") or []
            tool_call_id = raw.get("tool_call_id")
            tool_calls = [ChatToolCall(**tc) for tc in tool_calls_raw]
            msgs.append(
                ChatMessage(
                    role=r,
                    content=content or "",
                    tool_calls=tool_calls,
                    tool_call_id=tool_call_id,
                )
            )
        return msgs

    def _build_tool_definitions(self, ctx: RunContext, role: AgentRole) -> list[ChatToolDefinition]:
        definitions: list[ChatToolDefinition] = []
        for tool_id in role.tools:
            if tool_id not in ctx.services.tool_registry:
                continue
            tool = ctx.services.tool_registry.get(tool_id)
            definitions.append(
                ChatToolDefinition(
                    name=tool.id,
                    description=getattr(tool, "description", tool.id),
                    parameters=tool.input_schema(),
                )
            )
        return definitions

    async def _dispatch_tool_call(
        self,
        ctx: RunContext,
        role: AgentRole,
        state: RunState,
        node: AgentNode,
        tool_call: ChatToolCall,
        *,
        run_step_id: str,
    ) -> DispatchOutcome:
        """단일 tool_call 처리. 반환값은 상태 sentinel."""
        tool_id = tool_call.name
        if tool_id not in role.tools:
            raise ResolutionError(
                f"tool '{tool_id}' not permitted for role {role.name}",
                missing=[tool_id],
            )
        if tool_id not in ctx.services.tool_registry:
            raise ResolutionError(
                f"tool '{tool_id}' not registered",
                missing=[tool_id],
            )
        tool = ctx.services.tool_registry.get(tool_id)
        try:
            result = await ctx.services.tool_runtime.invoke(
                tool,
                tool_call.arguments,
                policy=ctx.policy,
                run_id=ctx.run_id,
                run_step_id=run_step_id,
                dry_run=ctx.dry_run,
                cancel_token=ctx.cancellation.token,
            )
        except OrchestratorError:
            raise
        except Exception as exc:
            # Policy violations / tool errors propagate
            raise RunningError(f"tool call failed: {exc}") from exc

        if result.outcome == "approval_pending":
            approval = result.approval
            if approval is None:  # defensive
                raise RunningError("approval_pending without approval payload")
            return await self._await_approval_and_retry(
                ctx, tool, tool_call, run_step_id, approval, state
            )

        if result.outcome in ("succeeded", "dry_run"):
            self._record_tool_result(state, tool_call, result)
            return "ok"

        if result.outcome == "failed":
            self._record_tool_failure(state, tool_call, result)
            return "failed"

        return "failed"

    async def _await_approval_and_retry(
        self,
        ctx: RunContext,
        tool: Any,
        tool_call: ChatToolCall,
        run_step_id: str,
        approval: ApprovalRequest,
        state: RunState,
    ) -> DispatchOutcome:
        """ask 경로: Run.status=awaiting_approval 저장 → waiter 대기 → 승인시
        approval_override=True 로 재호출.

        H2: waiter 가 `ApprovalExpiredError` 를 raise 하면 전파해 run.failed
        로 매핑. H4: `ApprovalCancelledError` 는 RunCancelledError 로 변환.
        """
        await self._set_status(ctx.run_id, "awaiting_approval")
        if self._approval_waiter is None:
            raise RunningError("no approval waiter configured")

        try:
            approved = await self._approval_waiter(approval)
        except ApprovalExpiredError as exc:
            await ctx.services.event_bus.emit(
                ctx.run_id,
                "approval.expired",
                {"approval_id": approval.id, "tool_id": tool.id},
            )
            raise RunningError(
                f"approval expired for {tool.id}",
                details={
                    "code": "approval.expired",
                    "approval_id": approval.id,
                    "tool_id": tool.id,
                },
            ) from exc
        except ApprovalCancelledError as exc:
            raise RunCancelledError("cancelled while awaiting approval") from exc

        if ctx.cancellation.is_cancelled():
            raise RunCancelledError("cancelled while awaiting approval")
        if not approved:
            await ctx.services.event_bus.emit(
                ctx.run_id,
                "approval.rejected",
                {"approval_id": approval.id, "tool_id": tool.id},
            )
            raise RunningError(f"approval rejected for {tool.id}")

        await ctx.services.event_bus.emit(
            ctx.run_id,
            "approval.approved",
            {"approval_id": approval.id, "tool_id": tool.id},
        )
        await self._set_status(ctx.run_id, "running")

        # Retry with approval_override=True so ToolRuntime bypasses the ask
        # branch and executes the allow path.
        result = await ctx.services.tool_runtime.invoke(
            tool,
            tool_call.arguments,
            policy=ctx.policy,
            run_id=ctx.run_id,
            run_step_id=run_step_id,
            dry_run=ctx.dry_run,
            cancel_token=ctx.cancellation.token,
            approval_override=True,
        )
        if result.outcome in ("succeeded", "dry_run"):
            self._record_tool_result(state, tool_call, result)
            return "ok"
        if result.outcome == "failed":
            self._record_tool_failure(state, tool_call, result)
            return "failed"
        raise RunningError(
            f"unexpected outcome after approval: {result.outcome}",
        )

    def _record_tool_result(
        self,
        state: RunState,
        tool_call: ChatToolCall,
        result: ToolInvocationResult,
    ) -> None:
        output: dict[str, Any] = {}
        if result.result is not None:
            output = dict(result.result.output)
        state.append_message(
            {
                "role": "tool",
                "content": str(output),
                "tool_call_id": tool_call.id,
            }
        )
        state.set_artifact(tool_call.id, output)

    def _record_tool_failure(
        self,
        state: RunState,
        tool_call: ChatToolCall,
        result: ToolInvocationResult,
    ) -> None:
        err = result.error or {"message": "tool failed"}
        state.append_message(
            {
                "role": "tool",
                "content": f"ERROR: {err}",
                "tool_call_id": tool_call.id,
            }
        )

    def _route(self, workflow: Workflow, node_id: str, state: RunState) -> list[str]:
        outs: list[Edge] = [e for e in workflow.edges if e.from_ == node_id]
        next_ids: list[str] = []
        for edge in outs:
            if evaluate_condition(edge.condition, state=state):
                next_ids.append(edge.to)
        return next_ids

    async def _set_status(
        self,
        run_id: str,
        status: str,
        *,
        ended_at: datetime | None = None,
        error: dict[str, Any] | None = None,
        terminal: bool = False,
    ) -> None:
        """H7: conventions.md §7.5 fail_run 정책.

        - 일반 전이에서 sink 실패 시 RunningError 로 승격 → run.failed 경로.
        - `terminal=True` (이미 run.failed/run.cancelled/run.succeeded 방출
          직후 기록) 경로에서는 swallow — 최후의 실패 경로이므로 더 이상
          승격할 상위가 없기 때문이다. 로그는 남긴다.
        """
        if self._status_sink is None:
            return
        try:
            await self._status_sink.set_run_status(run_id, status, ended_at=ended_at, error=error)
        except Exception as exc:
            _LOGGER.exception(
                "run.status_sink_failed",
                extra={
                    "event": "run.status_sink_failed",
                    "run_id": run_id,
                    "status": status,
                    "terminal": terminal,
                },
            )
            if terminal:
                return
            raise RunningError(
                "run status persist failed",
                details={
                    "code": "run.status_persist_failed",
                    "status": status,
                },
            ) from exc


# Simple async barrier allowing external approval decision:
class _ApprovalAwaitable:
    def __init__(self) -> None:
        self.event = asyncio.Event()
        self.approved = False

    def approve(self) -> None:
        self.approved = True
        self.event.set()

    def reject(self) -> None:
        self.approved = False
        self.event.set()

    async def wait(self) -> bool:
        await self.event.wait()
        return self.approved
