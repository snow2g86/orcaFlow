"""LLM profiles routes — list / create / upsert."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ...schema.llm import LLMProfile
from ..dependencies import AppServices, get_services

router = APIRouter(tags=["llm_profiles"])


@router.get("", summary="list llm profiles")
async def list_profiles(
    services: AppServices = Depends(get_services),
) -> list[dict[str, Any]]:
    return [p.model_dump(mode="json") for p in services.llm_profiles.values()]


@router.post("", summary="create llm profile")
async def create_profile(
    profile: LLMProfile,
    services: AppServices = Depends(get_services),
) -> dict[str, Any]:
    services.llm_profiles[profile.id] = profile
    # DB 영속화
    repo = getattr(services, "_profile_repo", None)
    if repo is not None:
        await repo.upsert(profile)
    return profile.model_dump(mode="json")


@router.put("/{profile_id}", summary="upsert llm profile")
async def upsert_profile(
    profile_id: str,
    profile: LLMProfile,
    services: AppServices = Depends(get_services),
) -> dict[str, Any]:
    updated = profile.model_copy(update={"id": profile_id})
    services.llm_profiles[profile_id] = updated
    # DB 영속화
    repo = getattr(services, "_profile_repo", None)
    if repo is not None:
        await repo.upsert(updated)
    return updated.model_dump(mode="json")
