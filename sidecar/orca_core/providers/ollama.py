"""OllamaAdapter — OpenAI 호환 경로 + Ollama 고유 `/api/tags` 헬스.

Ollama 는 `/v1/chat/completions` 를 OpenAI 호환으로 제공하지만 헬스 체크
및 모델 리스트 조회는 `/api/tags` 를 쓴다 (design.md §6.6).
"""

from __future__ import annotations

import logging
import time

import httpx

from ..audit.scrub import mask_url_secrets
from ._base import ProviderHealth
from .openai_compatible import OpenAICompatibleAdapter

_HTTP_BAD_REQUEST = 400

__all__ = ["OllamaAdapter"]

_LOGGER = logging.getLogger("orca_core.providers.ollama")


class OllamaAdapter(OpenAICompatibleAdapter):
    """Ollama 어댑터.

    `chat` / `stream_chat` 은 부모 구현을 그대로 사용한다. 헬스는
    `/api/tags` 로 override.
    """

    async def health(self) -> ProviderHealth:
        url = self._base() + "/api/tags"
        started = time.monotonic()
        try:
            response = await self._client.get(url)
        except httpx.HTTPError as exc:
            _LOGGER.warning(
                "provider.health.failed",
                extra={
                    "event": "provider.health.failed",
                    "kind": "ollama",
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
        # H6: JSON 파싱 실패 또는 필수 필드 부재 시 ok=False.
        try:
            body = response.json()
        except (ValueError, TypeError) as exc:
            _LOGGER.warning(
                "provider.health.unparseable_body",
                extra={
                    "event": "provider.health.unparseable_body",
                    "kind": "ollama",
                    "url": mask_url_secrets(url),
                    "cause": type(exc).__name__,
                },
            )
            return ProviderHealth(
                ok=False,
                latency_ms=latency_ms,
                message=f"unparseable body: {type(exc).__name__}",
            )
        if not isinstance(body, dict) or "models" not in body:
            return ProviderHealth(
                ok=False,
                latency_ms=latency_ms,
                message="missing field: models",
            )
        raw_models = body.get("models") or []
        if not isinstance(raw_models, list):
            return ProviderHealth(
                ok=False,
                latency_ms=latency_ms,
                message="missing field: models not a list",
            )
        models = [
            str(item.get("name"))
            for item in raw_models
            if isinstance(item, dict) and item.get("name")
        ]
        return ProviderHealth(ok=True, latency_ms=latency_ms, models=models)
