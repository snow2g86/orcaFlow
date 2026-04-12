"""OpenAICompatibleAdapter — 대다수 공급자 공통 베이스.

Ollama, vLLM, Together, Groq, Fireworks, TGI, LM Studio 등 OpenAI 호환
`/v1/chat/completions` 엔드포인트를 제공하는 공급자는 모두 이 어댑터
하나로 커버한다. 네이티브 예외(Ollama 의 `/api/tags` 헬스 등)는 별도
서브클래스에서 override.

핵심 원칙:
- **시크릿 조회**: `ProviderSecretStore.get(api_key_ref)` 경유. os.environ
  직접 읽기, DB 평문 저장 금지.
- **스크러빙**: 에러 메시지·로그에서 Authorization / URL querystring
  시크릿을 `mask_url_secrets` 로 마스킹 (conventions.md §7.4).
- **재시도**: 기본 3회, exponential backoff 0.5 → 1 → 2 s. Auth 실패는
  즉시 raise (재시도 금지).
- **타임아웃**: Provider.timeout_ms (기본 30_000 ms).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import json
import logging
import time
from typing import Any

import httpx

from ..audit.scrub import mask_free_text_secrets, mask_url_secrets
from ..schema.llm import Provider
from ._base import (
    ChatChunk,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatToolCall,
    ChatUsage,
    ProviderHealth,
)
from .errors import (
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from .secret_store import ProviderSecretStore

__all__ = ["OpenAICompatibleAdapter"]

_LOGGER = logging.getLogger("orca_core.providers.openai_compatible")

_DEFAULT_MAX_RETRIES = 3
_BACKOFF_SCHEDULE: tuple[float, ...] = (0.5, 1.0, 2.0)

_HTTP_BAD_REQUEST = 400
_HTTP_UNAUTHORIZED = 401
_HTTP_FORBIDDEN = 403
_HTTP_RATE_LIMITED = 429
_HTTP_INTERNAL_ERROR = 500


class OpenAICompatibleAdapter:
    """OpenAI `/v1/chat/completions` 호환 공통 어댑터.

    Parameters:
        provider : `Provider` 엔티티 — base_url / api_key_ref / headers / timeout.
        secret_store : API key 조회. None 이면 api_key_ref 가 있어도 auth 없이
            호출 (로컬 Ollama 등에서 유효).
        http_client : 주입 가능한 `httpx.AsyncClient` (테스트용 MockTransport).
        max_retries : 재시도 횟수 (기본 3).
    """

    kind = "openai_compatible"

    def __init__(
        self,
        provider: Provider,
        *,
        secret_store: ProviderSecretStore | None = None,
        http_client: httpx.AsyncClient | None = None,
        max_retries: int = _DEFAULT_MAX_RETRIES,
    ) -> None:
        self._provider = provider
        self._secret_store = secret_store
        self._external_client = http_client is not None
        self._client = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(provider.timeout_ms / 1000.0),
        )
        self._max_retries = max(1, max_retries)
        # Ollama subclass 등에서 override 가능하도록 kind 인스턴스 속성
        self.kind = provider.kind

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def chat(self, req: ChatRequest) -> ChatResponse:
        url = self._chat_url()
        payload = self._build_payload(req, stream=False)
        headers = await self._build_headers()

        response_data = await self._post_with_retry(url, payload=payload, headers=headers)
        return self._parse_chat_response(response_data)

    async def stream_chat(self, req: ChatRequest) -> AsyncIterator[ChatChunk]:
        """스트리밍 응답 iterator. M3 에서는 non-streaming polyfill 로 1 chunk 를 반환.

        완전한 SSE 파싱은 M4 Orchestrator 에서 필요해질 때 확장한다.
        """
        resp = await self.chat(req)
        delta = resp.message.content
        yield ChatChunk(
            delta=delta,
            tool_calls_delta=list(resp.message.tool_calls),
            finish_reason=resp.finish_reason,
        )

    async def health(self) -> ProviderHealth:  # noqa: PLR0911
        """기본 구현: `/v1/models` 호출. 실패 시 `ok=False` 반환 (raise 하지 않음)."""
        url = self._base() + "/v1/models"
        headers = await self._build_headers()
        started = time.monotonic()
        try:
            response = await self._client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            _LOGGER.warning(
                "provider.health.failed",
                extra={
                    "event": "provider.health.failed",
                    "kind": self.kind,
                    "url": mask_url_secrets(url),
                    "cause": type(exc).__name__,
                },
            )
            return ProviderHealth(ok=False, message=type(exc).__name__)
        latency_ms = int((time.monotonic() - started) * 1000)
        if response.status_code >= _HTTP_BAD_REQUEST:
            return ProviderHealth(
                ok=False,
                latency_ms=latency_ms,
                message=f"HTTP {response.status_code}",
            )
        # H6: JSON 파싱 실패 또는 필수 필드 부재 시 ok=False 로 내려간다.
        try:
            body = response.json()
        except (ValueError, TypeError) as exc:
            _LOGGER.warning(
                "provider.health.unparseable_body",
                extra={
                    "event": "provider.health.unparseable_body",
                    "kind": self.kind,
                    "url": mask_url_secrets(url),
                    "cause": type(exc).__name__,
                },
            )
            return ProviderHealth(
                ok=False,
                latency_ms=latency_ms,
                message=f"unparseable body: {type(exc).__name__}",
            )
        if not isinstance(body, dict):
            return ProviderHealth(
                ok=False,
                latency_ms=latency_ms,
                message="unparseable body: not an object",
            )
        if "data" not in body and "models" not in body:
            return ProviderHealth(
                ok=False,
                latency_ms=latency_ms,
                message="missing field: data/models",
            )
        models_list = body.get("data") or body.get("models") or []
        if not isinstance(models_list, list):
            return ProviderHealth(
                ok=False,
                latency_ms=latency_ms,
                message="missing field: data/models not a list",
            )
        models = [self._extract_model_id(item) for item in models_list]
        return ProviderHealth(ok=True, latency_ms=latency_ms, models=[m for m in models if m])

    async def aclose(self) -> None:
        if not self._external_client:
            await self._client.aclose()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _base(self) -> str:
        return self._provider.base_url.rstrip("/")

    def _chat_url(self) -> str:
        return self._base() + "/v1/chat/completions"

    async def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        headers.update(self._provider.headers)
        if self._provider.api_key_ref and self._secret_store is not None:
            api_key = await self._secret_store.get(self._provider.api_key_ref)
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def _build_payload(self, req: ChatRequest, *, stream: bool) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": req.model,
            "messages": [_message_to_openai(m) for m in req.messages],
            "stream": stream,
        }
        if req.temperature is not None:
            payload["temperature"] = req.temperature
        if req.top_p is not None:
            payload["top_p"] = req.top_p
        if req.max_tokens is not None:
            payload["max_tokens"] = req.max_tokens
        if req.stop:
            payload["stop"] = req.stop
        if req.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in req.tools
            ]
        if req.tool_choice is not None:
            payload["tool_choice"] = req.tool_choice
        if req.extra:
            for k, v in req.extra.items():
                payload.setdefault(k, v)
        return payload

    async def _post_with_retry(
        self,
        url: str,
        *,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                _LOGGER.info(
                    "provider.request",
                    extra={
                        "event": "provider.request",
                        "kind": self.kind,
                        "url": mask_url_secrets(url),
                        "attempt": attempt + 1,
                    },
                )
                response = await self._client.post(url, json=payload, headers=headers)
            except httpx.TimeoutException as exc:
                last_exc = exc
                _LOGGER.warning(
                    "provider.timeout",
                    extra={
                        "event": "provider.timeout",
                        "kind": self.kind,
                        "url": mask_url_secrets(url),
                        "attempt": attempt + 1,
                    },
                )
                if attempt + 1 >= self._max_retries:
                    raise ProviderTimeoutError(
                        f"provider timeout after {self._max_retries} attempts",
                        details={"url": mask_url_secrets(url)},
                    ) from exc
                await asyncio.sleep(_BACKOFF_SCHEDULE[min(attempt, len(_BACKOFF_SCHEDULE) - 1)])
                continue
            except httpx.HTTPError as exc:
                last_exc = exc
                _LOGGER.warning(
                    "provider.error",
                    extra={
                        "event": "provider.error",
                        "kind": self.kind,
                        "url": mask_url_secrets(url),
                        "attempt": attempt + 1,
                        "cause": type(exc).__name__,
                    },
                )
                if attempt + 1 >= self._max_retries:
                    raise ProviderUnavailableError(
                        "provider http transport error",
                        details={"cause": type(exc).__name__},
                    ) from exc
                await asyncio.sleep(_BACKOFF_SCHEDULE[min(attempt, len(_BACKOFF_SCHEDULE) - 1)])
                continue

            # Dispatch by status
            if response.status_code in (_HTTP_UNAUTHORIZED, _HTTP_FORBIDDEN):
                raise ProviderAuthError(
                    f"provider auth failed: HTTP {response.status_code}",
                    details={"url": mask_url_secrets(url)},
                )
            if response.status_code == _HTTP_RATE_LIMITED:
                if attempt + 1 >= self._max_retries:
                    raise ProviderRateLimitedError(
                        "provider rate-limited",
                        details={"url": mask_url_secrets(url)},
                    )
                await asyncio.sleep(_BACKOFF_SCHEDULE[min(attempt, len(_BACKOFF_SCHEDULE) - 1)])
                continue
            if response.status_code >= _HTTP_INTERNAL_ERROR:
                last_exc = ProviderUnavailableError(
                    f"provider server error HTTP {response.status_code}",
                    details={"url": mask_url_secrets(url)},
                )
                if attempt + 1 >= self._max_retries:
                    raise last_exc
                await asyncio.sleep(_BACKOFF_SCHEDULE[min(attempt, len(_BACKOFF_SCHEDULE) - 1)])
                continue
            if response.status_code >= _HTTP_BAD_REQUEST:
                # H1: 4xx body 를 스크럽한 뒤 256 자 truncate 해서 details 에 포함.
                # Bearer 토큰, sk-…, JWT, `"token":"…"` 류 모두 마스킹.
                raw_body = response.text
                scrubbed = mask_free_text_secrets(raw_body)
                raise ProviderError(
                    f"provider client error HTTP {response.status_code}",
                    details={
                        "url": mask_url_secrets(url),
                        "body": _truncate(scrubbed, 256),
                    },
                )
            try:
                parsed: dict[str, Any] = response.json()
            except (ValueError, json.JSONDecodeError) as exc:
                raise ProviderError(
                    "provider returned non-JSON body",
                    details={"url": mask_url_secrets(url)},
                ) from exc
            return parsed

        # Should never reach here because every path either returns or raises
        raise ProviderUnavailableError(
            "provider request exhausted retries",
            details={"cause": type(last_exc).__name__ if last_exc else "unknown"},
        )

    def _parse_chat_response(self, data: dict[str, Any]) -> ChatResponse:
        choices = data.get("choices") or []
        if not choices:
            raise ProviderError(
                "provider response has no choices",
                details={"keys": list(data.keys())},
            )
        first = choices[0]
        raw_msg: dict[str, Any] = first.get("message") or {}
        content = raw_msg.get("content") or ""
        tool_calls_raw = raw_msg.get("tool_calls") or []
        tool_calls: list[ChatToolCall] = []
        for tc in tool_calls_raw:
            fn = tc.get("function") or {}
            args_raw = fn.get("arguments") or "{}"
            tool_name = str(fn.get("name") or "")
            if isinstance(args_raw, str):
                try:
                    arguments: dict[str, Any] = json.loads(args_raw) if args_raw else {}
                except json.JSONDecodeError as exc:
                    # H7: 조용히 `{_raw: …}` 로 감싸 넘기지 말고 즉시 raise.
                    # 호출자가 재시도/Run fail 로 분기할 수 있도록 원문 일부만
                    # 스크럽 후 128 자 절단 해 details 에 싣는다.
                    scrubbed_raw = mask_free_text_secrets(args_raw)[:128]
                    raise ProviderError(
                        "provider tool_call arguments invalid json",
                        details={
                            "tool_name": tool_name,
                            "error_type": type(exc).__name__,
                            "raw_truncated": scrubbed_raw,
                        },
                    ) from exc
            else:
                arguments = dict(args_raw)
            tool_calls.append(
                ChatToolCall(
                    id=str(tc.get("id") or ""),
                    name=tool_name,
                    arguments=arguments,
                )
            )
        message = ChatMessage(
            role="assistant",
            content=content,
            tool_calls=tool_calls,
        )
        finish_reason = first.get("finish_reason")
        usage_raw = data.get("usage") or {}
        usage = ChatUsage(
            prompt_tokens=int(usage_raw.get("prompt_tokens") or 0),
            completion_tokens=int(usage_raw.get("completion_tokens") or 0),
            total_tokens=int(usage_raw.get("total_tokens") or 0),
        )
        return ChatResponse(
            model=str(data.get("model") or ""),
            message=message,
            finish_reason=finish_reason
            if finish_reason
            in {
                "stop",
                "length",
                "tool_calls",
                "content_filter",
                "error",
            }
            else None,
            usage=usage,
            raw=data,
        )

    @staticmethod
    def _extract_model_id(item: Any) -> str:
        if isinstance(item, dict):
            for key in ("id", "name", "model"):
                value = item.get(key)
                if isinstance(value, str):
                    return value
        if isinstance(item, str):
            return item
        return ""


def _message_to_openai(msg: ChatMessage) -> dict[str, Any]:
    out: dict[str, Any] = {"role": msg.role, "content": msg.content}
    if msg.name:
        out["name"] = msg.name
    if msg.tool_call_id:
        out["tool_call_id"] = msg.tool_call_id
    if msg.tool_calls:
        out["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                },
            }
            for tc in msg.tool_calls
        ]
    return out


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "…"
