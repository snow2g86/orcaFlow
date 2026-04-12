"""web.http_request — HTTP 요청 (network side-effect).

httpx.AsyncClient 사용. URL 스크러빙 적용. 응답 body 크기 제한.
"""

from __future__ import annotations

import re
from typing import Any, ClassVar
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import httpx

from ...errors import ToolRuntimeError
from ...schema.tool import Permission, SideEffect, ToolNamespace
from .._base import ToolContext, ToolResult

__all__ = ["WebHttpRequestTool"]

_MAX_OUTPUT_BYTES = 1 * 1024 * 1024
_DEFAULT_TIMEOUT = 30
_MAX_TIMEOUT = 120

# Query param keys to scrub
_SCRUB_PATTERNS = re.compile(
    r"(api[_-]?key|secret|token|password|auth|credential)",
    re.IGNORECASE,
)


def _scrub_url(url: str) -> str:
    """URL 쿼리 스트링에서 시크릿 파라미터를 마스킹."""
    parsed = urlparse(url)
    if not parsed.query:
        return url
    params = parse_qs(parsed.query, keep_blank_values=True)
    scrubbed = {}
    for key, values in params.items():
        if _SCRUB_PATTERNS.search(key):
            scrubbed[key] = ["***SCRUBBED***"]
        else:
            scrubbed[key] = values
    clean_query = urlencode(
        [(k, v) for k, vals in scrubbed.items() for v in vals],
    )
    return urlunparse(parsed._replace(query=clean_query))


class WebHttpRequestTool:
    """HTTP 요청 툴."""

    id: str = "web.http_request"
    namespace: ClassVar[ToolNamespace] = "web"
    name: str = "http_request"
    side_effect: ClassVar[SideEffect] = "network"
    reversible: bool = False
    default_dry_run: bool = False
    timeout_ms: int = _DEFAULT_TIMEOUT * 1000
    max_output_bytes: int = _MAX_OUTPUT_BYTES

    # httpx.AsyncClient 를 외부에서 주입할 수 있도록 (테스트용)
    _client_factory: type[httpx.AsyncClient] | None = None

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["method", "url"],
            "properties": {
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
                },
                "url": {"type": "string", "minLength": 1},
                "headers": {"type": ["object", "null"]},
                "body": {"type": ["string", "null"]},
                "timeout_seconds": {
                    "type": ["integer", "null"],
                    "minimum": 1,
                    "maximum": _MAX_TIMEOUT,
                },
            },
            "additionalProperties": False,
        }

    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["status_code", "headers", "body", "url"],
            "properties": {
                "status_code": {"type": "integer"},
                "headers": {"type": "object"},
                "body": {"type": "string"},
                "url": {"type": "string"},
                "truncated": {"type": "boolean"},
            },
        }

    def permissions(self) -> list[Permission]:
        return [Permission(kind="network_host", scope="*", action="read")]

    async def dry_run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        method = args["method"]
        url = args["url"]
        scrubbed = _scrub_url(url)
        return ToolResult(
            output={
                "dry_run": True,
                "method": method,
                "url": scrubbed,
            },
            diff_preview={"preview": f"Would send {method} to {scrubbed}"},
        )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        method: str = args["method"]
        url: str = args["url"]
        headers: dict[str, str] = args.get("headers") or {}
        body: str | None = args.get("body")
        timeout = min(args.get("timeout_seconds") or _DEFAULT_TIMEOUT, _MAX_TIMEOUT)

        scrubbed_url = _scrub_url(url)

        try:
            client_cls = self._client_factory or httpx.AsyncClient
            async with client_cls() as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    content=body.encode("utf-8") if body else None,
                    timeout=timeout,
                )
        except httpx.HTTPError as exc:
            raise ToolRuntimeError(
                f"HTTP request failed: {exc}",
                details={"url": scrubbed_url, "method": method},
            ) from exc

        response_body = response.text
        truncated = False
        if len(response_body) > self.max_output_bytes:
            response_body = response_body[: self.max_output_bytes]
            truncated = True

        resp_headers = dict(response.headers)

        return ToolResult(
            output={
                "status_code": response.status_code,
                "headers": resp_headers,
                "body": response_body,
                "url": scrubbed_url,
                "truncated": truncated,
            },
            side_effects=[f"sent {method} request"],
        )
