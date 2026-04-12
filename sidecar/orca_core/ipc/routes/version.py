"""Version / build info 엔드포인트 (auth 면제)."""

from __future__ import annotations

import sys

from fastapi import APIRouter
from pydantic import BaseModel

from ... import __version__

router = APIRouter()


class VersionResponse(BaseModel):
    version: str
    python: str
    service: str = "orca-sidecar"


@router.get("/version", response_model=VersionResponse, tags=["system"])
async def version() -> VersionResponse:
    return VersionResponse(version=__version__, python=sys.version.split()[0])
