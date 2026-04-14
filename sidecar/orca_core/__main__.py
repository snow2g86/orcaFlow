"""Sidecar entry point.

Tauri 셸이 이 프로세스를 spawn 하면 아래 순서를 수행한다:

1. Config 로딩 (파일 + 환경변수)
2. 토큰 생성 (128bit)
3. TCP 소켓을 먼저 bind 해 OS 할당 포트를 확보
4. stdout 첫 줄에 handshake JSON 출력 → Tauri 가 읽어 보관
5. uvicorn 서버 기동 (확보된 소켓 사용)

handshake JSON 포맷은 design.md §6.7 및 OrcaFlow.do.md §2.3 을 따른다.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import socket
import sys
from typing import NoReturn

import uvicorn

from . import __version__
from .config import Config, Settings, load_config
from .ipc.dependencies import AppServices
from .ipc.http_app import create_app
from .orchestrator import EventBus, GraphRunner
from .persistence.db import Database
from .persistence.repo.providers import ProvidersRepository
from .persistence.repo.llm_profiles import LLMProfilesRepository
from .providers.ollama import OllamaAdapter
from .providers.openai_compatible import OpenAICompatibleAdapter
from .providers.registry import ProviderRegistry
from .schema.policy import Policy
from .tools.register_all import create_default_registry
from .tools.runtime import ToolRuntime


def _emit_handshake(port: int, token: str) -> None:
    payload = {
        "kind": "handshake",
        "port": port,
        "token": token,
        "pid": os.getpid(),
        "version": __version__,
    }
    sys.stdout.write(json.dumps(payload, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def _reserve_port(host: str, requested_port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, requested_port))
    sock.set_inheritable(True)
    return sock


def _configure_logging(level: str) -> None:
    numeric = {
        "trace": logging.DEBUG,
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warn": logging.WARNING,
        "error": logging.ERROR,
    }.get(level.lower(), logging.INFO)
    logging.basicConfig(
        level=numeric,
        stream=sys.stderr,
        format='{"ts":"%(asctime)s","level":"%(levelname)s","component":"%(name)s","message":"%(message)s"}',
    )


async def _serve(sock: socket.socket, app, *, host: str) -> None:
    config = uvicorn.Config(
        app,
        host=host,
        fd=sock.fileno(),
        log_config=None,
        lifespan="on",
        access_log=False,
    )
    server = uvicorn.Server(config)
    await server.serve()


async def _build_services(config: Config) -> AppServices:
    """DB 초기화 → Provider/Profile 로드 → AppServices 조립."""
    db = Database(config.db.path)
    await db.initialize()

    provider_repo = ProvidersRepository(db)
    profile_repo = LLMProfilesRepository(db)

    # DB 에서 기존 데이터 로드
    providers = await provider_repo.list_all()
    profiles = await profile_repo.list_all()

    # Provider → Adapter 매핑
    registry = ProviderRegistry()
    for p in providers:
        adapter = OllamaAdapter(p) if p.kind == "ollama" else OpenAICompatibleAdapter(p)
        registry.register(p, adapter)

    # Tool 등록
    tool_reg = create_default_registry()
    event_bus = EventBus()

    workspace = config.workspace
    logs_dir = workspace / "logs"
    journal_dir = workspace / "journal"
    logs_dir.mkdir(parents=True, exist_ok=True)
    journal_dir.mkdir(parents=True, exist_ok=True)

    # No-op 트랜잭션 팩토리 (Production 용 DB 트랜잭션은 M5 에서 확장)
    from .tools._base import TransactionScope

    class _NoOpWriter:
        async def write(self, *args, **kwargs):
            pass

    class _NoOpTxContext:
        async def __aenter__(self) -> TransactionScope:
            return TransactionScope(
                audit_db_writer=None,
                journal_db_writer=None,
                tool_call_writer=_NoOpWriter(),  # type: ignore[arg-type]
            )

        async def __aexit__(self, *args):
            pass

    tool_runtime = ToolRuntime(
        transaction_factory=_NoOpTxContext,
        audit_log_path=logs_dir / "audit.log",
        journal_base_dir=journal_dir,
    )
    runner = GraphRunner()

    services = AppServices(
        tool_registry=tool_reg,
        provider_registry=registry,
        tool_runtime=tool_runtime,
        event_bus=event_bus,
        runner=runner,
    )
    # In-memory 에 DB 데이터 로드
    for prof in profiles:
        services.llm_profiles[prof.id] = prof

    # 기본 정책
    policy = Policy(name="trusted", mode="trusted", rules=[])
    services.policies[policy.id] = policy
    services.default_policy_id = policy.id

    # Repo 참조 보관 (라우트에서 DB 영속화 용도)
    services._db = db  # type: ignore[attr-defined]
    services._provider_repo = provider_repo  # type: ignore[attr-defined]
    services._profile_repo = profile_repo  # type: ignore[attr-defined]

    return services


def main() -> NoReturn:
    config = load_config(Settings())
    _configure_logging(config.app.log_level)

    token = secrets.token_hex(32)
    sock = _reserve_port(config.sidecar.host, config.sidecar.port)
    actual_port = sock.getsockname()[1]

    services = asyncio.run(_build_services(config))

    app = create_app(config=config, token=token, services=services)

    _emit_handshake(actual_port, token)

    try:
        asyncio.run(_serve(sock, app, host=config.sidecar.host))
    except KeyboardInterrupt:
        logging.getLogger("orcaflow").info("shutdown requested")
    finally:
        sock.close()
    sys.exit(0)


if __name__ == "__main__":
    main()
