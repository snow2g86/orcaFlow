"""Health check — sidecar liveness probe (auth 면제)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ... import __version__

router = APIRouter()


class HealthResponse(BaseModel):
    ok: bool
    version: str
    service: str = "orca-sidecar"


@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(ok=True, version=__version__)
