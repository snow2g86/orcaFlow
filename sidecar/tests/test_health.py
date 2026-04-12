"""Sidecar M1 smoke tests — health / version / auth."""

from __future__ import annotations

import secrets

from fastapi.testclient import TestClient
import pytest

from orca_core.config import Config
from orca_core.ipc.http_app import create_app


@pytest.fixture
def token() -> str:
    return secrets.token_hex(16)


@pytest.fixture
def client(token: str) -> TestClient:
    app = create_app(config=Config(), token=token)
    return TestClient(app)


def test_health_is_public(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["service"] == "orca-sidecar"
    assert "version" in body


def test_version_is_public(client: TestClient) -> None:
    response = client.get("/version")
    assert response.status_code == 200
    assert "python" in response.json()


def test_config_requires_token(client: TestClient) -> None:
    response = client.get("/config")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "auth.invalid_token"


def test_config_with_token_returns_public_view(client: TestClient, token: str) -> None:
    response = client.get("/config", headers={"X-Orca-Token": token})
    assert response.status_code == 200
    body = response.json()
    assert "sidecar" in body
    assert body["sidecar"]["host"] == "127.0.0.1"
    # 시크릿 누출 없음
    assert "token" not in body
