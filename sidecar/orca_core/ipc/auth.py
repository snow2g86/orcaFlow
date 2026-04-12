"""IPC 토큰 인증 미들웨어.

Tauri 셸이 sidecar 를 spawn 할 때 랜덤 토큰을 전달받고, 이후 모든 요청의
`X-Orca-Token` 헤더로 검증한다. localhost 라도 타 프로세스의 무단 접근을
차단하기 위함이다 (conventions.md §8.4, design.md §4.2).

`/health` 와 `/version` 은 사전 진단 용도로 토큰을 요구하지 않는다.

H14: `/runs/{id}/events` (SSE) 는 `?token=<TOKEN>` 쿼리 파라미터 대안을
허용한다. 브라우저 `EventSource` 는 커스텀 헤더를 지원하지 않기 때문이다.
이는 일반 URL 히스토리에 남을 수 있으나 Tauri webview 는 일반 브라우저
히스토리를 갖지 않는다. 다른 엔드포인트는 헤더 전용을 유지.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import hmac
import re

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from ..errors import AuthError

TOKEN_HEADER = "x-orca-token"  # noqa: S105  # header name, not a password
PUBLIC_PATHS: frozenset[str] = frozenset({"/health", "/version"})
# H14: paths that additionally accept ?token=<TOKEN> as fallback.
_SSE_PATH_RE = re.compile(r"^/runs/[^/]+/events$")


class TokenAuthMiddleware(BaseHTTPMiddleware):
    """요청 헤더의 토큰을 sidecar 내부 토큰과 상수 시간 비교."""

    def __init__(self, app: ASGIApp, *, token: str) -> None:
        super().__init__(app)
        if not token:
            msg = "sidecar token must be non-empty"
            raise ValueError(msg)
        self._token = token

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        path = request.url.path
        if path in PUBLIC_PATHS:
            return await call_next(request)

        provided = request.headers.get(TOKEN_HEADER, "")
        if (not provided or not hmac.compare_digest(provided, self._token)) and _SSE_PATH_RE.match(
            path
        ) is not None:
            # H14: SSE fallback — look at query param.
            query_token = request.query_params.get("token", "")
            if query_token and hmac.compare_digest(query_token, self._token):
                return await call_next(request)

        if not provided or not hmac.compare_digest(provided, self._token):
            err = AuthError("invalid or missing X-Orca-Token")
            return JSONResponse(err.to_payload(), status_code=err.http_status)

        return await call_next(request)
