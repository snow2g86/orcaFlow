"""Runs routes — POST /runs, GET /runs/{id}, cancel, SSE events."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ...errors import NotFoundError
from ...orchestrator import (
    ApprovalCancelledError,
    ApprovalExpiredError,
    RunCancellation,
    RunContext,
    RunState,
)
from ...schema._base import generate_uuid_v7
from ...schema.approval import ApprovalRequest
from ..dependencies import AppServices, RunHandle, get_services
from ..sse import run_event_source

router = APIRouter(tags=["runs"])

_logger = logging.getLogger("orca_core.ipc.runs")

# Sentinel value used in RunHandle.approval_results to distinguish cancel
# from reject (H4). reject = False, approve = True, cancel = "cancelled".
_CANCEL_SENTINEL = "cancelled"


class StartRunBody(BaseModel):
    workflow_id: str
    input: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = False
    override_policy_id: str | None = None


@router.post("", status_code=202, summary="start workflow run")
async def start_run(  # noqa: PLR0915 — coordinator of waiter/task/finalizer closures
    body: StartRunBody, services: AppServices = Depends(get_services)
) -> dict[str, Any]:
    entry = services.workflows.get(body.workflow_id)
    if entry is None:
        raise NotFoundError(f"workflow not found: {body.workflow_id}")
    workflow, yaml_text = entry

    policy = services.resolve_policy(workflow)
    if body.override_policy_id and body.override_policy_id in services.policies:
        policy = services.policies[body.override_policy_id]

    run_id = generate_uuid_v7()
    cancellation = RunCancellation()
    orch_services = services.build_orchestrator_services()
    context = RunContext(
        run_id=run_id,
        workflow=workflow,
        policy=policy,
        services=orch_services,
        cancellation=cancellation,
        initial_state=RunState(),
        inputs=body.input,
        dry_run=body.dry_run,
    )

    # Approval waiter binds back to this handle's pending_approvals map.
    handle = RunHandle(
        run_id=run_id,
        task=None,
        context=context,
        snapshot={
            "workflow_id": workflow.id,
            "workflow_snapshot": yaml_text,
            "status": "pending",
            "started_at": datetime.now(tz=UTC).isoformat(),
        },
    )
    services.runs[run_id] = handle

    async def waiter(approval: ApprovalRequest) -> bool:
        ev = asyncio.Event()
        handle.pending_approvals[approval.id] = ev
        services.approvals[approval.id] = approval
        # Emit approval event on the run's bus so clients see it
        await services.event_bus.emit(
            run_id,
            "approval.requested",
            {
                "approval_id": approval.id,
                "run_step_id": approval.run_step_id,
                "reason": approval.reason,
                "tool_call_id": approval.tool_call_id,
            },
        )
        try:
            await asyncio.wait_for(ev.wait(), timeout=approval.ttl_seconds)
        except TimeoutError as exc:
            # H2: TTL elapsed → approval.expired. Mark state & event, raise.
            current = services.approvals.get(approval.id, approval)
            services.approvals[approval.id] = current.model_copy(
                update={
                    "state": "expired",
                    "decided_at": datetime.now(tz=UTC),
                }
            )
            handle.pending_approvals.pop(approval.id, None)
            await services.event_bus.emit(
                run_id,
                "approval.expired",
                {"approval_id": approval.id, "tool_id": approval.tool_call_id},
            )
            raise ApprovalExpiredError(
                f"approval {approval.id} expired after {approval.ttl_seconds}s",
                details={"approval_id": approval.id},
            ) from exc
        finally:
            # best-effort cleanup so a stale Event does not linger past decision
            pass

        outcome = handle.approval_results.get(approval.id, False)
        if outcome == _CANCEL_SENTINEL:
            # H4: user cancelled the run while this approval was pending.
            # Distinguish from a reject.
            raise ApprovalCancelledError(
                f"approval {approval.id} cancelled",
                details={"approval_id": approval.id},
            )
        return bool(outcome)

    # Install waiter on this runner instance via a per-run runner?
    # The singleton GraphRunner doesn't capture waiter in closure — create a
    # per-run runner by cloning configuration is cheap (class has tiny state).
    from ...orchestrator.runner import GraphRunner

    runner = GraphRunner(
        approval_waiter=waiter,
        status_sink=_HandleStatusSink(handle),
    )

    async def _task_wrapper() -> None:
        try:
            await runner.run(context)
        except Exception:
            # runner.run already emitted run.failed + updated snapshot for
            # OrchestratorError paths, but for a pre-loop crash (e.g. role
            # lookup failing before emit) we still want a structured log.
            _logger.exception(
                "run.task_crashed",
                extra={"event": "run.task_crashed", "run_id": run_id},
            )
            raise

    task = asyncio.create_task(_task_wrapper())
    handle.task = task
    services.background_tasks.append(task)

    def _finalize_run(finished: asyncio.Task[None]) -> None:
        # H3: if the task exited with an exception and the snapshot is still
        # in a non-terminal state, force-transition to failed so polling
        # clients don't hang on `running`. We also best-effort emit run.failed
        # if the runner never got far enough to emit one.
        try:
            exc = finished.exception()
        except asyncio.CancelledError:
            exc = None
        except Exception:  # pragma: no cover - defensive
            exc = None
        status = handle.snapshot.get("status")
        non_terminal = {"pending", "running", "awaiting_approval"}
        if exc is not None and status in non_terminal:
            handle.snapshot["status"] = "failed"
            handle.snapshot.setdefault("ended_at", datetime.now(tz=UTC).isoformat())
            handle.snapshot["error"] = {
                "code": "run.task_crashed",
                "message": str(exc),
            }
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(  # noqa: RUF006 - fire and forget inside loop
                    services.event_bus.emit(
                        run_id,
                        "run.failed",
                        {
                            "run_id": run_id,
                            "code": "run.task_crashed",
                            "message": str(exc),
                        },
                    )
                )
                loop.create_task(services.event_bus.close_run(run_id))  # noqa: RUF006
            except RuntimeError:
                pass
        _cleanup_run(services, run_id, finished)

    task.add_done_callback(_finalize_run)

    handle.snapshot["status"] = "running"
    return {
        "run_id": run_id,
        "status": "pending",
        "started_at": handle.snapshot["started_at"],
    }


def _cleanup_run(
    services: AppServices,
    run_id: str,
    task: asyncio.Task[Any] | None,
) -> None:
    """H12: task 완료 시 services.runs / background_tasks 정리.

    - `background_tasks` 에서 제거.
    - `services.runs` 크기가 `run_retention` 을 초과하면 가장 오래된 완료
      run 부터 FIFO 로 제거 (현재 running 인 것은 제외). 제거 시 EventBus
      버퍼도 `clear(run_id)` 로 릴리즈한다.
    """
    if task is not None:
        with contextlib.suppress(ValueError):
            services.background_tasks.remove(task)
    retention = getattr(services, "run_retention", 50)
    if retention <= 0:
        return
    # Iterate in insertion order (Python dicts preserve order).
    runs = services.runs
    if len(runs) <= retention:
        return
    to_evict: list[str] = []
    overflow = len(runs) - retention
    for rid, handle in runs.items():
        if overflow <= 0:
            break
        running = handle.task is not None and not handle.task.done()
        if running:
            continue
        to_evict.append(rid)
        overflow -= 1
    for rid in to_evict:
        runs.pop(rid, None)
        try:
            services.event_bus.clear(rid)
        except Exception:  # pragma: no cover
            _logger.exception(
                "run.event_buffer_clear_failed",
                extra={"event": "run.event_buffer_clear_failed", "run_id": rid},
            )


class _HandleStatusSink:
    """RunHandle 에 상태 전이를 기록. (M5 에서 DB 사상으로 교체)"""

    def __init__(self, handle: RunHandle) -> None:
        self._handle = handle

    async def set_run_status(
        self,
        run_id: str,
        status: str,
        *,
        ended_at: datetime | None = None,
        error: dict[str, Any] | None = None,
    ) -> None:
        self._handle.snapshot["status"] = status
        if ended_at is not None:
            self._handle.snapshot["ended_at"] = ended_at.isoformat()
        if error is not None:
            self._handle.snapshot["error"] = error


@router.get("/{run_id}", summary="get run snapshot")
async def get_run(run_id: str, services: AppServices = Depends(get_services)) -> dict[str, Any]:
    handle = services.runs.get(run_id)
    if handle is None:
        raise NotFoundError(f"run not found: {run_id}")
    events_buffer = services.event_bus.snapshot(run_id)
    buffer_cap = getattr(services.event_bus, "_buffer_size", None)
    events_truncated = bool(buffer_cap and len(events_buffer) >= buffer_cap)
    return {
        "run_id": run_id,
        **handle.snapshot,
        "events": [e.model_dump(mode="json") for e in events_buffer],
        "events_truncated": events_truncated,
    }


@router.post("/{run_id}/cancel", summary="cancel a running run")
async def cancel_run(run_id: str, services: AppServices = Depends(get_services)) -> dict[str, Any]:
    handle = services.runs.get(run_id)
    if handle is None:
        raise NotFoundError(f"run not found: {run_id}")
    # H4: terminal state ⇒ 409 conflict.
    status = handle.snapshot.get("status")
    if status in ("succeeded", "failed", "cancelled"):
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "run.terminal",
                    "message": f"run already in terminal state: {status}",
                    "details": {"status": status},
                }
            },
        )
    if handle.task is None:
        # Task not yet started — mark cancellation flag only.
        handle.context.cancellation.cancel()
        return {"ok": True, "status": "cancelling"}
    if handle.task.done():
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "run.terminal",
                    "message": "run task already completed",
                    "details": {"status": status},
                }
            },
        )
    handle.context.cancellation.cancel()
    # Also unblock any pending approvals so waiter returns — mark them as
    # cancelled (not rejected) so runner surfaces RunCancelledError.
    for approval_id, ev in handle.pending_approvals.items():
        handle.approval_results[approval_id] = _CANCEL_SENTINEL  # type: ignore[assignment]
        ev.set()
    return {"ok": True, "status": "cancelling"}


@router.get("/{run_id}/events", summary="SSE stream of run events")
async def stream_events(
    run_id: str, request: Request, services: AppServices = Depends(get_services)
) -> Any:
    if run_id not in services.runs:
        raise NotFoundError(f"run not found: {run_id}")
    return run_event_source(request, run_id, services.event_bus)


# Suppress unused import
_ = JSONResponse
