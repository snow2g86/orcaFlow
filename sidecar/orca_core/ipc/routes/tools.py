"""Tools registry read route."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ..dependencies import AppServices, get_services

router = APIRouter(tags=["tools"])


@router.get("", summary="list registered tools")
async def list_tools(
    services: AppServices = Depends(get_services),
) -> list[dict[str, Any]]:
    registry = services.tool_registry
    return [
        {
            "id": registry.get(tid).id,
            "namespace": registry.get(tid).namespace,
            "side_effect": registry.get(tid).side_effect,
            "reversible": registry.get(tid).reversible,
            "default_dry_run": registry.get(tid).default_dry_run,
        }
        for tid in registry.list_ids()
    ]
