"""ToolRuntime — 7단계 파괴적 작업 플로우 (design.md §6.2).

```
ToolRuntime.invoke(tool, args, ...):
    1. input_schema JSON Schema 검증
    2. PolicyEngine.evaluate → allow | deny | ask | dry_run_only
    3. dry_run 이거나 write/destructive 이면 tool.dry_run() 선실행
    4. reversible=True 이면 journal.record_before() (fail-closed)
    5. tool.run() 실제 실행 (timeout, cancel, output size limit)
    6. AuditSink.record() — 성공/실패/차단 모든 경로
    7. EventEmitter.emit() — 트랜잭션 커밋 이후
```

핵심 불변:
- 각 단계 실패 시 다음 단계로 넘어가지 않음 (short-circuit).
- AuditLog 는 성공/실패/차단 모든 경로에서 기록 (schema.md §5 #1).
- reversible=True 인데 journal.before 가 실패하면 **실행하지 않음** (§5 #2).
- dry_run 요청 또는 dry_run_only 결정이면 실제 run() 호출 금지.
- 동일 invoke() 에서 생성되는 ToolCall / JournalEntry / AuditLog 는 하나의
  트랜잭션에서 커밋 또는 롤백 (의존성 역전으로 `TransactionFactory` 주입).
- 이벤트 emit 은 **트랜잭션 커밋 이후**에만.

파괴적 예외(`PolicyViolationError`, `ToolRuntimeError` 등)는 트랜잭션이
정상 종료(커밋) 된 후 re-raise 한다. 트랜잭션 안에서 raise 하면 rollback 이
일어나 감사 레코드가 사라지기 때문이다.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
import logging
import time
from typing import Any, Literal

import jsonschema  # type: ignore[import-untyped]

from ..audit.sink import AuditSink
from ..errors import (
    OrcaError,
    PolicyViolationError,
    ToolCancelledError,
    ToolRuntimeError,
    ValidationError,
)
from ..journal.store import JournalStore, JournalWriteError
from ..policy.engine import PolicyEngine
from ..schema._base import generate_uuid_v7
from ..schema.approval import ApprovalRequest
from ..schema.audit import AuditPolicyDecision
from ..schema.policy import Policy
from ..schema.run import ToolCall, ToolCallDecision
from ._base import (
    CancelToken,
    EventEmitter,
    InMemoryEventEmitter,
    Tool,
    ToolContext,
    ToolIo,
    ToolResult,
    TransactionFactory,
    TransactionScope,
    default_tool_io,
)

# M5: 내부 effective_decision 용 확장 Literal. schema 의 4-value Literal
# (allow/denied/approved/dry_run_only) 와 매핑하는 헬퍼를 통해 DB 에 쓸
# 실제 값을 좁힌다.
_EffectiveDecision = Literal["allow", "deny", "dry_run_only"]

__all__ = [
    "ToolInvocationResult",
    "ToolRuntime",
]

_LOGGER = logging.getLogger("orca_core.tools.runtime")


@dataclass(slots=True)
class ToolInvocationResult:
    """`ToolRuntime.invoke()` 결과.

    Attributes:
        outcome : `succeeded` / `failed` / `denied` / `dry_run` / `approval_pending`
        tool_call : 기록된 `ToolCall` 엔티티
        result : 실제 툴 실행 또는 dry_run 결과 (`ToolResult`)
        approval : `approval_pending` 일 때의 `ApprovalRequest`
        audit_id : 기록된 AuditLog id
        duration_ms : 소요 시간
        error : 실패 시 에러 페이로드
    """

    outcome: str
    tool_call: ToolCall | None = None
    result: ToolResult | None = None
    approval: ApprovalRequest | None = None
    audit_id: str | None = None
    duration_ms: int = 0
    error: dict[str, Any] | None = None


class ToolRuntime:
    """단일 툴 호출을 7단계 순서로 실행하는 러너.

    Parameters:
        transaction_factory : 호출마다 새 `TransactionScope` 를 async context
            로 제공하는 팩토리 (persistence 혹은 테스트 어댑터가 구현).
        audit_log_path : 감사 파일 미러 경로 (`~/.orcaflow/logs/audit.log`).
        journal_base_dir : spill 파일 루트 (`~/.orcaflow/journal/`).
        events : 이벤트 emitter (기본 `InMemoryEventEmitter`).
        io : `ToolIo` 인스턴스 (기본 `ToolIo()`).
        secret_store : 선택적 시크릿 스토어 (툴이 필요로 할 때).
    """

    def __init__(
        self,
        *,
        transaction_factory: TransactionFactory,
        audit_log_path: Any,
        journal_base_dir: Any,
        events: EventEmitter | None = None,
        io: ToolIo | None = None,
        secret_store: Any = None,
    ) -> None:
        self._txn_factory = transaction_factory
        self._audit_log_path = audit_log_path
        self._journal_base_dir = journal_base_dir
        self._events: EventEmitter = events or InMemoryEventEmitter()
        self._io = io or default_tool_io()
        self._secret_store = secret_store
        self._policy_engine = PolicyEngine()

    @property
    def events(self) -> EventEmitter:
        return self._events

    async def invoke(
        self,
        tool: Tool,
        args: dict[str, Any],
        *,
        policy: Policy,
        run_id: str,
        run_step_id: str,
        dry_run: bool = False,
        cancel_token: CancelToken | None = None,
        approval_override: bool = False,
    ) -> ToolInvocationResult:
        """단일 툴 호출 실행 — 7단계 플로우.

        Parameters:
            approval_override : M4 재개 경로. True 로 호출하면 policy 가
                `ask` 를 반환해도 ask 분기를 건너뛰고 allow 로 강등한다.
                기본 False → 기존 M3 동작 보존.
        """
        started = time.monotonic()
        tool_call_id = generate_uuid_v7()
        cancel = cancel_token or CancelToken()
        pending_events: list[tuple[str, dict[str, Any]]] = []

        # -------- Step 1: input_schema 검증 --------
        try:
            self._validate_input(tool, args)
        except ValidationError:
            await self._emit(
                "tool_call.failed",
                {
                    "tool_id": tool.id,
                    "tool_call_id": tool_call_id,
                    "run_id": run_id,
                    "run_step_id": run_step_id,
                    "reason": "schema_validation_failed",
                },
            )
            raise

        # Determine effective dry_run: explicit caller flag OR tool default
        want_dry_run = dry_run or tool.default_dry_run

        # Deferred exception: raised AFTER transaction commits so audit/journal
        # rows are not rolled back on denial / policy violation.
        deferred_error: BaseException | None = None
        invocation: ToolInvocationResult | None = None

        try:
            async with self._txn_factory() as scope:
                sink = self._build_sink(scope)
                journal = self._build_journal(scope)

                ctx = ToolContext(
                    run_id=run_id,
                    run_step_id=run_step_id,
                    tool_call_id=tool_call_id,
                    policy_engine=self._policy_engine,
                    journal=journal,
                    audit=sink,
                    events=self._events,
                    secret_store=self._secret_store,
                    io=self._io,
                    cancel_token=cancel,
                    dry_run=want_dry_run,
                )

                # -------- Step 2: Policy 평가 --------
                decision = self._policy_engine.evaluate(policy, tool_id=tool.id, args=args)
                _LOGGER.info(
                    "policy.checked",
                    extra={
                        "event": "policy.checked",
                        "tool_id": tool.id,
                        "run_id": run_id,
                        "run_step_id": run_step_id,
                        "effect": decision.effect,
                        "rule_id": decision.rule_id,
                    },
                )

                # M4: approval_override=True 이면 ask 결정을 allow 로 강등.
                # 재개 경로는 사용자가 이미 승인한 것이므로 다시 ask 하지 않는다.
                if approval_override and decision.effect == "ask":
                    # H15: emit an audit trail event so approval-override
                    # downgrades are observable in the event stream.
                    pending_events.append(
                        (
                            "policy.downgraded_by_approval",
                            {
                                "tool_id": tool.id,
                                "tool_call_id": tool_call_id,
                                "run_id": run_id,
                                "run_step_id": run_step_id,
                                "original_rule_id": decision.rule_id,
                                "original_reason": decision.reason,
                            },
                        )
                    )
                    decision = decision.__class__(
                        effect="allow",
                        rule_id=decision.rule_id,
                        reason=f"approval_override (orig={decision.reason})",
                        matched=decision.matched,
                    )

                if decision.effect == "deny":
                    invocation, deferred_error = await self._do_deny(
                        tool=tool,
                        args=args,
                        ctx=ctx,
                        sink=sink,
                        scope=scope,
                        tool_call_id=tool_call_id,
                        started=started,
                        rule_id=decision.rule_id,
                        reason=decision.reason,
                        pending_events=pending_events,
                    )
                elif decision.effect == "ask":
                    invocation = await self._do_ask(
                        tool=tool,
                        args=args,
                        ctx=ctx,
                        sink=sink,
                        scope=scope,
                        tool_call_id=tool_call_id,
                        started=started,
                        reason=decision.reason,
                        cancel=cancel,
                        pending_events=pending_events,
                    )
                else:
                    # allow or dry_run_only
                    invocation, deferred_error = await self._do_allow_or_dry(
                        tool=tool,
                        args=args,
                        ctx=ctx,
                        sink=sink,
                        journal=journal,
                        scope=scope,
                        tool_call_id=tool_call_id,
                        started=started,
                        decision_effect=decision.effect,
                        want_dry_run=want_dry_run,
                        cancel=cancel,
                        pending_events=pending_events,
                    )
        except ToolRuntimeError as exc:
            # H4: journal 실패로 rollback 된 경우, 새 트랜잭션을 열어 blocked
            # audit + tool_call 레코드를 기록해 DB 레벨 §5 #1 불변 (모든
            # 파괴적 툴 콜은 AuditLog 에 기록된다) 을 만족시킨다.
            rescue_failed = False
            if isinstance(exc, _JournalFailClosedError):
                try:
                    await self._rescue_after_journal_failure(
                        tool=tool,
                        args=args,
                        tool_call_id=tool_call_id,
                        run_id=run_id,
                        run_step_id=run_step_id,
                        cause=exc,
                    )
                except Exception:  # pragma: no cover - defensive
                    rescue_failed = True
                    _LOGGER.exception(
                        "audit.rescue_after_journal_failure_failed",
                        extra={
                            "event": "audit.rescue_failed",
                            "tool_id": tool.id,
                            "tool_call_id": tool_call_id,
                            "run_id": run_id,
                            "run_step_id": run_step_id,
                        },
                    )
                    with contextlib.suppress(Exception):
                        await self._file_mirror_blocked_audit(
                            tool=tool,
                            args=args,
                            run_id=run_id,
                            run_step_id=run_step_id,
                        )
            pending_events.append(
                (
                    "tool_call.failed",
                    {
                        "tool_id": tool.id,
                        "tool_call_id": tool_call_id,
                        "run_id": run_id,
                        "run_step_id": run_step_id,
                        "reason": "journal_write_failed",
                        "rescue_failed": rescue_failed,
                    },
                )
            )
            for event, payload in pending_events:
                await self._events.emit(event, payload)
            raise

        # -------- Step 7: emit events (post-commit) --------
        for event, payload in pending_events:
            await self._events.emit(event, payload)

        if deferred_error is not None:
            raise deferred_error
        assert invocation is not None  # noqa: S101
        return invocation

    # ------------------------------------------------------------------
    # Step handlers
    # ------------------------------------------------------------------

    async def _do_deny(
        self,
        *,
        tool: Tool,
        args: dict[str, Any],
        ctx: ToolContext,
        sink: AuditSink,
        scope: TransactionScope,
        tool_call_id: str,
        started: float,
        rule_id: str | None,
        reason: str | None,
        pending_events: list[tuple[str, dict[str, Any]]],
    ) -> tuple[ToolInvocationResult, BaseException]:
        duration = int((time.monotonic() - started) * 1000)
        tool_call = ToolCall(
            id=tool_call_id,
            run_step_id=ctx.run_step_id,
            tool_id=tool.id,
            args=args,
            policy_decision="denied",
            dry_run=False,
            duration_ms=duration,
            error={"reason": reason, "rule_id": rule_id},
        )
        await scope.tool_call_writer.insert(tool_call)
        audit = await sink.record(
            actor="tool_runtime",
            action=tool.id,
            target=_extract_target(args),
            status="blocked",
            policy_decision="denied",
            run_id=ctx.run_id,
            run_step_id=ctx.run_step_id,
        )
        # H3: back-fill audit_log_id on the denied ToolCall row so DB shows
        # the link from tool_call → audit_log.
        with contextlib.suppress(NotImplementedError, AttributeError):
            await scope.tool_call_writer.update_result(
                tool_call_id,
                result_json=None,
                error_json={"reason": reason, "rule_id": rule_id},
                duration_ms=duration,
                audit_log_id=audit.id,
            )
        pending_events.append(
            (
                "tool_call.denied",
                {
                    "tool_id": tool.id,
                    "tool_call_id": tool_call_id,
                    "run_id": ctx.run_id,
                    "run_step_id": ctx.run_step_id,
                    "rule_id": rule_id,
                },
            )
        )
        err = PolicyViolationError(
            f"policy denied tool call {tool.id}",
            rule_id=rule_id,
            details={"tool_id": tool.id, "reason": reason, "audit_id": audit.id},
        )
        result = ToolInvocationResult(
            outcome="denied",
            tool_call=tool_call,
            audit_id=audit.id,
            duration_ms=duration,
            error={"rule_id": rule_id, "reason": reason},
        )
        return result, err

    async def _do_ask(
        self,
        *,
        tool: Tool,
        args: dict[str, Any],
        ctx: ToolContext,
        sink: AuditSink,
        scope: TransactionScope,
        tool_call_id: str,
        started: float,
        reason: str | None,
        cancel: CancelToken,
        pending_events: list[tuple[str, dict[str, Any]]],
    ) -> ToolInvocationResult:
        diff_preview: dict[str, Any] | None = None
        preview_error: dict[str, Any] | None = None
        if tool.side_effect in ("write", "destructive"):
            # H5: swallow-all 제거. 예외 유형별로 분류해 approval.diff_preview
            # 에 에러 구조를 기록하고 구조화 로그를 남긴다.
            try:
                dry = await self._run_with_timeout(
                    tool.dry_run(args, ctx),
                    timeout_s=tool.timeout_ms / 1000.0,
                    cancel_token=cancel,
                )
                diff_preview = dry.diff_preview
            except TimeoutError as exc:
                preview_error = {
                    "kind": "timeout",
                    "message": f"dry_run timeout after {tool.timeout_ms}ms",
                }
                _LOGGER.warning(
                    "approval.preview_failed",
                    extra={
                        "event": "approval.preview_failed",
                        "tool_id": tool.id,
                        "tool_call_id": tool_call_id,
                        "run_id": ctx.run_id,
                        "run_step_id": ctx.run_step_id,
                        "kind": "timeout",
                    },
                    exc_info=exc,
                )
            except OrcaError as exc:
                preview_error = {
                    "kind": "tool_error",
                    "code": exc.code,
                    "message": str(exc),
                }
                _LOGGER.warning(
                    "approval.preview_failed",
                    extra={
                        "event": "approval.preview_failed",
                        "tool_id": tool.id,
                        "tool_call_id": tool_call_id,
                        "run_id": ctx.run_id,
                        "run_step_id": ctx.run_step_id,
                        "kind": "tool_error",
                        "code": exc.code,
                    },
                    exc_info=exc,
                )
            except Exception as exc:
                preview_error = {
                    "kind": "unknown",
                    "message": str(exc),
                }
                _LOGGER.warning(
                    "approval.preview_failed",
                    extra={
                        "event": "approval.preview_failed",
                        "tool_id": tool.id,
                        "tool_call_id": tool_call_id,
                        "run_id": ctx.run_id,
                        "run_step_id": ctx.run_step_id,
                        "kind": "unknown",
                    },
                    exc_info=exc,
                )
            if preview_error is not None:
                diff_preview = {"preview_error": preview_error}
        approval = ApprovalRequest(
            run_step_id=ctx.run_step_id,
            tool_call_id=tool_call_id,
            reason=reason or "approval required",
            diff_preview=diff_preview,
        )
        duration = int((time.monotonic() - started) * 1000)
        tool_call = ToolCall(
            id=tool_call_id,
            run_step_id=ctx.run_step_id,
            tool_id=tool.id,
            args=args,
            policy_decision="approved",
            dry_run=True,
            duration_ms=duration,
        )
        await scope.tool_call_writer.insert(tool_call)
        audit = await sink.record(
            actor="tool_runtime",
            action=tool.id,
            target=_extract_target(args),
            status="approved",
            policy_decision="approved",
            run_id=ctx.run_id,
            run_step_id=ctx.run_step_id,
        )
        # H3: back-fill audit_log_id + preview diff (as result_json) so DB
        # reflects the 1:1 tool_call ↔ audit_log link.
        with contextlib.suppress(NotImplementedError, AttributeError):
            await scope.tool_call_writer.update_result(
                tool_call_id,
                result_json={"diff_preview": diff_preview} if diff_preview else None,
                error_json=None,
                duration_ms=duration,
                audit_log_id=audit.id,
            )
        tool_call = tool_call.model_copy(update={"audit_log_id": audit.id})
        pending_events.append(
            (
                "approval.requested",
                {
                    "tool_id": tool.id,
                    "tool_call_id": tool_call_id,
                    "approval_id": approval.id,
                    "run_id": ctx.run_id,
                    "run_step_id": ctx.run_step_id,
                    "reason": approval.reason,
                },
            )
        )
        return ToolInvocationResult(
            outcome="approval_pending",
            tool_call=tool_call,
            approval=approval,
            audit_id=audit.id,
            duration_ms=duration,
        )

    async def _do_allow_or_dry(  # noqa: PLR0911, PLR0915
        self,
        *,
        tool: Tool,
        args: dict[str, Any],
        ctx: ToolContext,
        sink: AuditSink,
        journal: JournalStore,
        scope: TransactionScope,
        tool_call_id: str,
        started: float,
        decision_effect: str,
        want_dry_run: bool,
        cancel: CancelToken,
        pending_events: list[tuple[str, dict[str, Any]]],
    ) -> tuple[ToolInvocationResult, BaseException | None]:
        # -------- Step 3: dry_run first (if write/destructive or explicit) --------
        dry_result: ToolResult | None = None
        should_dry_first = (
            want_dry_run
            or decision_effect == "dry_run_only"
            or tool.side_effect in ("write", "destructive")
        )
        # M5: effective_decision 을 audit/ToolCall Literal 로 좁힌다.
        effective_decision: ToolCallDecision = (
            "dry_run_only" if decision_effect == "dry_run_only" else "allow"
        )
        audit_decision: AuditPolicyDecision = effective_decision
        timeout_s = tool.timeout_ms / 1000.0

        if should_dry_first:
            try:
                dry_result = await self._run_with_timeout(
                    tool.dry_run(args, ctx),
                    timeout_s=timeout_s,
                    cancel_token=cancel,
                )
            except ToolCancelledError:
                # H8 cancel during dry_run — surface as failed + cancelled event.
                await self._record_dry_run_failed(
                    tool=tool,
                    args=args,
                    ctx=ctx,
                    sink=sink,
                    scope=scope,
                    tool_call_id=tool_call_id,
                    started=started,
                    effective_decision=effective_decision,
                    audit_decision=audit_decision,
                    cause="cancelled",
                    pending_events=pending_events,
                    phase_event_extra={"reason": "cancelled"},
                )
                return (
                    ToolInvocationResult(
                        outcome="failed",
                        duration_ms=int((time.monotonic() - started) * 1000),
                        error={"phase": "dry_run", "cause": "cancelled"},
                    ),
                    ToolCancelledError("tool dry_run cancelled by user"),
                )
            except Exception as exc:
                await self._record_dry_run_failed(
                    tool=tool,
                    args=args,
                    ctx=ctx,
                    sink=sink,
                    scope=scope,
                    tool_call_id=tool_call_id,
                    started=started,
                    effective_decision=effective_decision,
                    audit_decision=audit_decision,
                    cause=str(exc),
                    pending_events=pending_events,
                )
                return (
                    ToolInvocationResult(
                        outcome="failed",
                        duration_ms=int((time.monotonic() - started) * 1000),
                        error={"phase": "dry_run", "cause": str(exc)},
                    ),
                    None,
                )

        # -------- dry_run_only / explicit dry_run → stop here with success --------
        if want_dry_run or decision_effect == "dry_run_only":
            duration = int((time.monotonic() - started) * 1000)
            tool_call = ToolCall(
                id=tool_call_id,
                run_step_id=ctx.run_step_id,
                tool_id=tool.id,
                args=args,
                result=dry_result.output if dry_result else None,
                dry_run=True,
                policy_decision=effective_decision,
                duration_ms=duration,
            )
            await scope.tool_call_writer.insert(tool_call)
            audit = await sink.record(
                actor="tool_runtime",
                action=tool.id,
                target=_extract_target(args),
                status="success",
                policy_decision=audit_decision,
                run_id=ctx.run_id,
                run_step_id=ctx.run_step_id,
            )
            # H3: back-fill audit_log_id
            with contextlib.suppress(NotImplementedError, AttributeError):
                await scope.tool_call_writer.update_result(
                    tool_call_id,
                    result_json=dry_result.output if dry_result else None,
                    error_json=None,
                    duration_ms=duration,
                    audit_log_id=audit.id,
                )
            tool_call = tool_call.model_copy(update={"audit_log_id": audit.id})
            pending_events.append(
                (
                    "tool_call.succeeded",
                    {
                        "tool_id": tool.id,
                        "tool_call_id": tool_call_id,
                        "run_id": ctx.run_id,
                        "run_step_id": ctx.run_step_id,
                        "dry_run": True,
                    },
                )
            )
            return (
                ToolInvocationResult(
                    outcome="dry_run",
                    tool_call=tool_call,
                    result=dry_result,
                    audit_id=audit.id,
                    duration_ms=duration,
                ),
                None,
            )

        # -------- Step 4: Insert preliminary ToolCall + journal.record_before --------
        preliminary = ToolCall(
            id=tool_call_id,
            run_step_id=ctx.run_step_id,
            tool_id=tool.id,
            args=args,
            dry_run=False,
            policy_decision="allow",
        )
        await scope.tool_call_writer.insert(preliminary)

        if tool.reversible:
            before_snapshot = dry_result.before_snapshot if dry_result is not None else None
            try:
                await journal.record_before(
                    run_id=ctx.run_id,
                    run_step_id=ctx.run_step_id,
                    tool_call_id=tool_call_id,
                    kind=_journal_kind_for(tool),  # type: ignore[arg-type]
                    before=before_snapshot,
                    reversible=True,
                )
            except JournalWriteError as exc:
                # H4: transaction will roll back. We raise a dedicated marker
                # so the outer `invoke()` scope can open a fresh transaction
                # and write the blocked audit + tool_call rows there. This
                # satisfies schema.md §5 #1 at the DB level even on journal
                # failure.
                raise _JournalFailClosedError(
                    "journal record_before failed — tool execution blocked",
                    details={"cause": str(exc), "tool_id": tool.id},
                ) from exc

        # -------- Step 5: tool.run() --------
        try:
            ctx.check_cancel()
            run_result = await self._run_with_timeout(
                tool.run(args, ctx),
                timeout_s=timeout_s,
                cancel_token=cancel,
            )
        except ToolCancelledError as exc:
            audit = await sink.record(
                actor="tool_runtime",
                action=tool.id,
                target=_extract_target(args),
                status="failed",
                policy_decision="allow",
                run_id=ctx.run_id,
                run_step_id=ctx.run_step_id,
            )
            with contextlib.suppress(NotImplementedError, AttributeError):
                await scope.tool_call_writer.update_result(
                    tool_call_id,
                    result_json=None,
                    error_json={"phase": "run", "cause": "cancelled"},
                    duration_ms=int((time.monotonic() - started) * 1000),
                    audit_log_id=audit.id,
                )
            pending_events.append(
                (
                    "tool_call.failed",
                    {
                        "tool_id": tool.id,
                        "tool_call_id": tool_call_id,
                        "run_id": ctx.run_id,
                        "run_step_id": ctx.run_step_id,
                        "reason": "cancelled",
                    },
                )
            )
            return (
                ToolInvocationResult(
                    outcome="failed",
                    tool_call=preliminary,
                    duration_ms=int((time.monotonic() - started) * 1000),
                    error={"phase": "run", "cause": "cancelled"},
                ),
                exc,
            )
        except asyncio.CancelledError as exc:
            audit = await sink.record(
                actor="tool_runtime",
                action=tool.id,
                target=_extract_target(args),
                status="failed",
                policy_decision="allow",
                run_id=ctx.run_id,
                run_step_id=ctx.run_step_id,
            )
            with contextlib.suppress(NotImplementedError, AttributeError):
                await scope.tool_call_writer.update_result(
                    tool_call_id,
                    result_json=None,
                    error_json={"phase": "run", "cause": "cancelled"},
                    duration_ms=int((time.monotonic() - started) * 1000),
                    audit_log_id=audit.id,
                )
            pending_events.append(
                (
                    "tool_call.failed",
                    {
                        "tool_id": tool.id,
                        "tool_call_id": tool_call_id,
                        "run_id": ctx.run_id,
                        "run_step_id": ctx.run_step_id,
                        "reason": "cancelled",
                    },
                )
            )
            return (
                ToolInvocationResult(
                    outcome="failed",
                    tool_call=preliminary,
                    duration_ms=int((time.monotonic() - started) * 1000),
                    error={"phase": "run", "cause": "cancelled"},
                ),
                exc,
            )
        except Exception as exc:
            audit = await sink.record(
                actor="tool_runtime",
                action=tool.id,
                target=_extract_target(args),
                status="failed",
                policy_decision="allow",
                run_id=ctx.run_id,
                run_step_id=ctx.run_step_id,
            )
            with contextlib.suppress(NotImplementedError, AttributeError):
                await scope.tool_call_writer.update_result(
                    tool_call_id,
                    result_json=None,
                    error_json={"phase": "run", "cause": str(exc)},
                    duration_ms=int((time.monotonic() - started) * 1000),
                    audit_log_id=audit.id,
                )
            pending_events.append(
                (
                    "tool_call.failed",
                    {
                        "tool_id": tool.id,
                        "tool_call_id": tool_call_id,
                        "run_id": ctx.run_id,
                        "run_step_id": ctx.run_step_id,
                        "phase": "run",
                        "cause": str(exc),
                    },
                )
            )
            return (
                ToolInvocationResult(
                    outcome="failed",
                    tool_call=preliminary,
                    duration_ms=int((time.monotonic() - started) * 1000),
                    error={"phase": "run", "cause": str(exc)},
                ),
                None,
            )

        # -------- Step 6: audit record (success) --------
        audit = await sink.record(
            actor="tool_runtime",
            action=tool.id,
            target=_extract_target(args),
            status="success",
            policy_decision="allow",
            run_id=ctx.run_id,
            run_step_id=ctx.run_step_id,
        )

        duration = int((time.monotonic() - started) * 1000)
        # H3: back-fill DB row with result/duration/audit_log_id.
        with contextlib.suppress(NotImplementedError, AttributeError):
            await scope.tool_call_writer.update_result(
                tool_call_id,
                result_json=run_result.output,
                error_json=None,
                duration_ms=duration,
                audit_log_id=audit.id,
            )
        final_call = preliminary.model_copy(
            update={
                "result": run_result.output,
                "duration_ms": duration,
                "audit_log_id": audit.id,
            }
        )
        pending_events.append(
            (
                "tool_call.succeeded",
                {
                    "tool_id": tool.id,
                    "tool_call_id": tool_call_id,
                    "run_id": ctx.run_id,
                    "run_step_id": ctx.run_step_id,
                    "duration_ms": duration,
                },
            )
        )
        return (
            ToolInvocationResult(
                outcome="succeeded",
                tool_call=final_call,
                result=run_result,
                audit_id=audit.id,
                duration_ms=duration,
            ),
            None,
        )

    async def _record_dry_run_failed(
        self,
        *,
        tool: Tool,
        args: dict[str, Any],
        ctx: ToolContext,
        sink: AuditSink,
        scope: TransactionScope,
        tool_call_id: str,
        started: float,
        effective_decision: ToolCallDecision,
        audit_decision: AuditPolicyDecision,
        cause: str,
        pending_events: list[tuple[str, dict[str, Any]]],
        phase_event_extra: dict[str, Any] | None = None,
    ) -> None:
        duration = int((time.monotonic() - started) * 1000)
        tool_call = ToolCall(
            id=tool_call_id,
            run_step_id=ctx.run_step_id,
            tool_id=tool.id,
            args=args,
            dry_run=True,
            policy_decision=effective_decision,
            error={"phase": "dry_run", "cause": cause},
            duration_ms=duration,
        )
        await scope.tool_call_writer.insert(tool_call)
        audit = await sink.record(
            actor="tool_runtime",
            action=tool.id,
            target=_extract_target(args),
            status="failed",
            policy_decision=audit_decision,
            run_id=ctx.run_id,
            run_step_id=ctx.run_step_id,
        )
        with contextlib.suppress(NotImplementedError, AttributeError):
            await scope.tool_call_writer.update_result(
                tool_call_id,
                result_json=None,
                error_json={"phase": "dry_run", "cause": cause},
                duration_ms=duration,
                audit_log_id=audit.id,
            )
        event_payload: dict[str, Any] = {
            "tool_id": tool.id,
            "tool_call_id": tool_call_id,
            "run_id": ctx.run_id,
            "run_step_id": ctx.run_step_id,
            "phase": "dry_run",
            "cause": cause,
        }
        if phase_event_extra:
            event_payload.update(phase_event_extra)
        pending_events.append(("tool_call.failed", event_payload))

    async def _rescue_after_journal_failure(
        self,
        *,
        tool: Tool,
        args: dict[str, Any],
        tool_call_id: str,
        run_id: str,
        run_step_id: str,
        cause: Exception,
    ) -> None:
        """H4: journal 실패 후 rollback 된 트랜잭션을 보상하기 위해 새 트랜잭션
        을 열어 blocked audit + tool_call 을 기록한다. §5 #1 (모든 파괴적
        툴 콜은 audit 에 기록된다) 를 DB 레벨에서 만족시키기 위함.
        """
        async with self._txn_factory() as rescue_scope:
            rescue_sink = self._build_sink(rescue_scope)
            blocked_tool_call = ToolCall(
                id=tool_call_id,
                run_step_id=run_step_id,
                tool_id=tool.id,
                args=args,
                dry_run=False,
                policy_decision="allow",
                error={"phase": "journal_before", "cause": str(cause)},
                duration_ms=0,
            )
            await rescue_scope.tool_call_writer.insert(blocked_tool_call)
            audit = await rescue_sink.record(
                actor="tool_runtime",
                action=tool.id,
                target=_extract_target(args),
                status="blocked",
                policy_decision="allow",
                run_id=run_id,
                run_step_id=run_step_id,
            )
            with contextlib.suppress(NotImplementedError, AttributeError):
                await rescue_scope.tool_call_writer.update_result(
                    tool_call_id,
                    result_json=None,
                    error_json={"phase": "journal_before", "cause": str(cause)},
                    duration_ms=0,
                    audit_log_id=audit.id,
                )

    async def _file_mirror_blocked_audit(
        self,
        *,
        tool: Tool,
        args: dict[str, Any],
        run_id: str,
        run_step_id: str,
    ) -> None:
        """파일 미러 단독 blocked audit — rescue 트랜잭션도 실패한 경우 최후의
        보루. 파일 append 는 best-effort 이며 실패 시 상위에서 swallow.
        """
        file_only_sink = AuditSink(log_path=self._audit_log_path, db_writer=None)
        await file_only_sink.record(
            actor="tool_runtime",
            action=tool.id,
            target=_extract_target(args),
            status="blocked",
            policy_decision="allow",
            run_id=run_id,
            run_step_id=run_step_id,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_input(tool: Tool, args: dict[str, Any]) -> None:
        schema = tool.input_schema()
        try:
            jsonschema.validate(instance=args, schema=schema)
        except jsonschema.ValidationError as exc:
            raise ValidationError(
                f"input schema validation failed for {tool.id}: {exc.message}",
                details={"path": list(exc.path), "schema_path": list(exc.schema_path)},
            ) from exc

    def _build_sink(self, scope: TransactionScope) -> AuditSink:
        return AuditSink(
            log_path=self._audit_log_path,
            db_writer=scope.audit_db_writer,
        )

    def _build_journal(self, scope: TransactionScope) -> JournalStore:
        return JournalStore(
            base_dir=self._journal_base_dir,
            db_writer=scope.journal_db_writer,
        )

    @staticmethod
    async def _run_with_timeout(
        awaitable: Any,
        *,
        timeout_s: float,
        cancel_token: CancelToken,
    ) -> ToolResult:
        """H8: CancelToken 과 timeout 을 병렬로 감시해 즉시 종료 가능.

        기존 구현은 `ctx.check_cancel()` 의 협력적 확인에만 의존해, 장기
        실행 툴이 cancel 을 감지하지 못하면 timeout 까지 실제로 기다렸다.
        """
        task = asyncio.create_task(awaitable)
        cancel_wait = asyncio.create_task(cancel_token.wait())
        try:
            done, _pending = await asyncio.wait(
                {task, cancel_wait},
                timeout=timeout_s,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if cancel_wait in done and not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
                raise ToolCancelledError("tool run cancelled by user")
            if not done:
                # timeout elapsed
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
                raise TimeoutError(f"tool timeout after {int(timeout_s * 1000)}ms")
            # task finished first — return its result (or re-raise its exc)
            result: ToolResult = task.result()
            return result
        finally:
            if not cancel_wait.done():
                cancel_wait.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await cancel_wait

    async def _emit(self, event: str, payload: dict[str, Any]) -> None:
        await self._events.emit(event, payload)


class _JournalFailClosedError(ToolRuntimeError):
    """Internal marker — runtime raised when journal.record_before fails.

    Caught by `invoke()` to open a rescue transaction (H4).
    """

    code = "tool.journal_fail_closed"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _extract_target(args: dict[str, Any]) -> str:
    for key in ("path", "src", "dst", "url", "command"):
        value = args.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _journal_kind_for(tool: Tool) -> str:
    mapping = {
        "fs.write_file": "fs_write",
        "fs.move": "fs_move",
        "fs.delete": "fs_delete_to_trash",
    }
    return mapping.get(tool.id, "custom")
