"""FastAPI 앱 팩토리.

design.md §4.2 의 REST 인터페이스를 루트 FastAPI 인스턴스로 구성한다.
M1 에서는 health / version / config 만 장착하고 이후 마일스톤에서
routes 모듈을 추가한다.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .. import __version__
from ..config import Config
from ..errors import OrcaError
from .auth import TokenAuthMiddleware
from .dependencies import AppServices
from .routes import (
    approvals as approvals_routes,
    chat as chat_routes,
    config as config_routes,
    health as health_routes,
    llm_profiles as llm_profiles_routes,
    policies as policies_routes,
    providers as providers_routes,
    runs as runs_routes,
    tools as tools_routes,
    version as version_routes,
    workflows as workflows_routes,
)

logger = logging.getLogger("orcaflow.ipc")


def create_app(
    *,
    config: Config,
    token: str,
    services: AppServices | None = None,
) -> FastAPI:
    """런타임 토큰과 Config 를 주입받는 순수 팩토리.

    M4: `services` 를 주입하면 orchestrator / workflows / runs 라우트가
    활성화된다. M1 호환을 위해 None 을 허용한다 (해당 경로는 501 에 가깝게
    동작하지만, 라우트를 마운트하지 않는 방식으로 처리).
    """
    app = FastAPI(
        title="OrcaFlow Sidecar",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url="/openapi.json",
    )

    app.state.config = config
    app.state.token = token
    if services is not None:
        app.state.services = services

    app.add_middleware(TokenAuthMiddleware, token=token)

    _install_exception_handlers(app)

    app.include_router(health_routes.router)
    app.include_router(version_routes.router)
    app.include_router(config_routes.router, prefix="/config")

    if services is not None:
        app.include_router(workflows_routes.router, prefix="/workflows")
        app.include_router(runs_routes.router, prefix="/runs")
        app.include_router(approvals_routes.router, prefix="/approvals")
        app.include_router(chat_routes.router, prefix="/chat")
        app.include_router(policies_routes.router, prefix="/policies")
        app.include_router(providers_routes.router, prefix="/providers")
        app.include_router(llm_profiles_routes.router, prefix="/llm-profiles")
        app.include_router(tools_routes.router, prefix="/tools")

        @app.on_event("shutdown")
        async def _cancel_runs() -> None:  # pragma: no cover
            await services.cancel_all_runs()

    return app


def _install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(OrcaError)
    async def _orca_error_handler(_: Request, exc: OrcaError) -> JSONResponse:
        logger.warning(
            "orca_error",
            extra={"event": "orca_error", "code": exc.code, "err_message": exc.message},
        )
        return JSONResponse(exc.to_payload(), status_code=exc.http_status)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled", extra={"event": "unhandled"})
        payload: dict[str, Any] = {
            "error": {
                "code": "orca.unknown",
                "message": "internal error",
                "details": {"type": exc.__class__.__name__},
            }
        }
        return JSONResponse(payload, status_code=500)
