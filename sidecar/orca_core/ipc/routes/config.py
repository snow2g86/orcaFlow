"""Config read (M1) — 쓰기는 M2+ 에서 확장."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

router = APIRouter(tags=["config"])


@router.get("", summary="current sidecar config")
async def read_config(request: Request) -> dict[str, Any]:
    config = request.app.state.config
    public: dict[str, Any] = config.public_dict()
    return public
