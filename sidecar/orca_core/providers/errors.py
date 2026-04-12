"""Provider 에러 계층.

conventions.md §3.3 에 따라 모든 provider 계층 예외는 `OrcaError` 하위로
정의한다. 시크릿 값(API key, Authorization 헤더 등)은 에러 메시지에 절대
포함하지 않는다. 호출자에게 `mask_url_secrets` 를 통한 스크러빙된 값만
노출한다.
"""

from __future__ import annotations

from ..errors import OrcaError, ProviderUnavailableError

__all__ = [
    "ProviderAuthError",
    "ProviderError",
    "ProviderRateLimitedError",
    "ProviderTimeoutError",
    "ProviderToolNotSupportedError",
    "ProviderUnavailableError",
]


class ProviderError(OrcaError):
    """Provider 공통 베이스 (부모: OrcaError)."""

    code = "provider.error"
    http_status = 502


class ProviderAuthError(ProviderError):
    """인증 실패 (401/403). 재시도 금지 — 즉시 실패."""

    code = "provider.auth_invalid"
    http_status = 401


class ProviderTimeoutError(ProviderError):
    """타임아웃. 호출자는 재시도를 고려할 수 있다."""

    code = "provider.timeout"
    http_status = 504


class ProviderRateLimitedError(ProviderError):
    """429 Rate-limited. 호출자는 지수 백오프 후 재시도."""

    code = "provider.rate_limited"
    http_status = 429


class ProviderToolNotSupportedError(ProviderError):
    """공급자가 tool-call 포맷을 지원하지 않는다."""

    code = "provider.tool_not_supported"
    http_status = 400
