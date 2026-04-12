"""Providers routes — list / add / test."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ..dependencies import AppServices, get_services

router = APIRouter(tags=["providers"])


@router.get("", summary="list providers")
async def list_providers(
    services: AppServices = Depends(get_services),
) -> list[dict[str, Any]]:
    return [p.model_dump(mode="json") for p in services.provider_registry.list_providers()]
