"""Providers routes — list / add / health / models."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...schema.llm import Provider, ProviderKind
from ...providers.openai_compatible import OpenAICompatibleAdapter
from ...providers.ollama import OllamaAdapter
from ..dependencies import AppServices, get_services

router = APIRouter(tags=["providers"])


class AddProviderBody(BaseModel):
    name: str
    kind: ProviderKind
    base_url: str
    api_key: str | None = None


def _create_adapter(provider: Provider) -> OpenAICompatibleAdapter:
    """Provider kind 에 맞는 어댑터 인스턴스 생성."""
    if provider.kind == "ollama":
        return OllamaAdapter(provider)
    return OpenAICompatibleAdapter(provider)


@router.get("", summary="list providers")
async def list_providers(
    services: AppServices = Depends(get_services),
) -> list[dict[str, Any]]:
    return [p.model_dump(mode="json") for p in services.provider_registry.list_providers()]


@router.post("", summary="add provider")
async def add_provider(
    body: AddProviderBody,
    services: AppServices = Depends(get_services),
) -> dict[str, Any]:
    provider = Provider(
        name=body.name,
        kind=body.kind,
        base_url=body.base_url,
        api_key_ref=body.api_key if body.api_key else None,
    )
    adapter = _create_adapter(provider)
    services.provider_registry.register(provider, adapter)
    return provider.model_dump(mode="json")


@router.get("/{provider_id}/health", summary="provider health check")
async def provider_health(
    provider_id: str,
    services: AppServices = Depends(get_services),
) -> dict[str, Any]:
    adapter = services.provider_registry.get(provider_id)
    result = await adapter.health()
    return result.model_dump(mode="json")


@router.get("/{provider_id}/models", summary="list provider models")
async def list_provider_models(
    provider_id: str,
    services: AppServices = Depends(get_services),
) -> list[str]:
    """Provider 에 사용 가능한 모델 목록 조회. health() 의 models 필드를 반환."""
    adapter = services.provider_registry.get(provider_id)
    result = await adapter.health()
    return result.models
