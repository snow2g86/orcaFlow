"""Orchestrator 예외 계층 (M4).

모든 예외는 `orca_core.errors.OrcaError` 를 상속해 HTTP 계층이 통일된
페이로드로 응답할 수 있게 한다. conventions.md §3.3 참조.
"""

from __future__ import annotations

from typing import Any

from ..errors import OrcaError

__all__ = [
    "ApprovalCancelledError",
    "ApprovalExpiredError",
    "CycleDetectedError",
    "OrchestratorError",
    "PlannerError",
    "ResolutionError",
    "RoutingError",
    "RunCancelledError",
    "RunningError",
]


class OrchestratorError(OrcaError):
    """Orchestrator 레이어 최상위 예외."""

    code = "orchestrator.error"
    http_status = 500


class PlannerError(OrchestratorError):
    """Planner 가 유효한 Workflow YAML 을 생성하지 못했을 때."""

    code = "planner.failed"
    http_status = 422


class RunningError(OrchestratorError):
    """Run 실행 중 발생한 일반 오류."""

    code = "run.runtime_error"
    http_status = 500


class CycleDetectedError(OrchestratorError):
    """DAG 검증 실패 (schema validator 이 이미 잡아야 하지만 방어용)."""

    code = "workflow.cycle"
    http_status = 400


class ResolutionError(OrchestratorError):
    """참조(role / tool / llm_profile) 해석 실패."""

    code = "workflow.invalid_reference"
    http_status = 400

    def __init__(
        self,
        message: str,
        *,
        missing: list[str] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged = {"missing": missing or [], **(details or {})}
        super().__init__(message, details=merged)
        self.missing = missing or []


class RoutingError(OrchestratorError):
    """Edge.condition 평가 실패 (안전 expr 파서에서 감지)."""

    code = "workflow.routing"
    http_status = 400


class RunCancelledError(OrchestratorError):
    """Run 이 사용자 요청으로 취소됨."""

    code = "run.cancelled"
    http_status = 499


class ApprovalExpiredError(OrchestratorError):
    """Approval TTL 만료 — H2. waiter 에서 TimeoutError 발생 시 변환.

    schema.md §3.14 ApprovalRequest.state=expired 전이와 짝.
    """

    code = "approval.expired"
    http_status = 408


class ApprovalCancelledError(OrchestratorError):
    """사용자가 approval 대기 중에 Run 을 cancel 했을 때. 거부(reject)와
    구분한다 — H4. waiter 에서 `cancelled` sentinel 을 돌려받으면 발생.
    """

    code = "approval.cancelled"
    http_status = 499
