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
from .config import Settings, load_config
from .ipc.http_app import create_app


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


def main() -> NoReturn:
    config = load_config(Settings())
    _configure_logging(config.app.log_level)

    token = secrets.token_hex(32)
    sock = _reserve_port(config.sidecar.host, config.sidecar.port)
    actual_port = sock.getsockname()[1]

    app = create_app(config=config, token=token)

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
