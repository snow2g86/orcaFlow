"""도메인 예외 계층.

conventions.md §3.3 에 따라 모든 sidecar 예외는 본 모듈의 `OrcaError`
하위로 정의한다. HTTP 응답 매핑은 `ipc.http_app.install_exception_handlers`
에서 수행한다.
"""

from __future__ import annotations

from typing import Any


class OrcaError(Exception):
    """모든 OrcaFlow 도메인 예외의 최상위 기반."""

    code: str = "orca.unknown"
    http_status: int = 500

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}

    def to_payload(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


class ConfigError(OrcaError):
    code = "config.invalid"
    http_status = 500


class AuthError(OrcaError):
    code = "auth.invalid_token"
    http_status = 401


class NotFoundError(OrcaError):
    code = "resource.not_found"
    http_status = 404


class ValidationError(OrcaError):
    code = "request.invalid"
    http_status = 400


class PolicyViolationError(OrcaError):
    code = "policy.denied"
    http_status = 403

    def __init__(
        self,
        message: str,
        *,
        rule_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged = {"rule_id": rule_id, **(details or {})}
        super().__init__(message, details=merged)
        self.rule_id = rule_id


class ProviderUnavailableError(OrcaError):
    code = "provider.unavailable"
    http_status = 503


class ToolRuntimeError(OrcaError):
    code = "tool.runtime_error"
    http_status = 500


class ToolCancelledError(OrcaError):
    """사용자(혹은 상위 런타임)가 CancelToken 으로 취소한 툴 호출.

    H8 regression — 장기 실행 중에도 CancelToken 감시를 병렬로 수행해
    협력적 cancel 체크 여부와 무관하게 즉시 종료시킬 수 있도록 도입.
    """

    code = "tool.cancelled"
    http_status = 499
