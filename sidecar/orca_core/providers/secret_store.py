"""ProviderSecretStore — OS 키체인 래퍼 Protocol 및 인메모리 구현.

conventions.md §4.4 / §8 에 따라 API 키·토큰은 **반드시** 본 스토어 경유로
조회한다. 어댑터 코드에서 `os.environ` 직접 읽기, config.toml 평문 저장,
Pydantic 덤프 금지.

프로덕션에서는 OS 키체인(Tauri keyring 플러그인 연동) 구현체가 주입되며,
본 모듈은 Protocol 과 테스트용 `InMemorySecretStore` 만 제공한다.
"""

from __future__ import annotations

from typing import Protocol

from ..errors import OrcaError

__all__ = [
    "InMemorySecretStore",
    "ProviderSecretNotFoundError",
    "ProviderSecretStore",
]


class ProviderSecretNotFoundError(OrcaError):
    """요청한 `api_key_ref` 가 스토어에 존재하지 않는다."""

    code = "provider.secret_not_found"
    http_status = 500


class ProviderSecretStore(Protocol):
    """프로바이더 시크릿 조회 Protocol.

    `get(api_key_ref)` 는 키체인 엔트리 ID 를 받아 평문 시크릿을 반환한다.
    엔트리가 없으면 `ProviderSecretNotFoundError` 를 raise.
    """

    async def get(self, api_key_ref: str) -> str: ...


class InMemorySecretStore:
    """테스트/개발용 인메모리 시크릿 스토어.

    프로덕션에서는 사용하지 말 것 — OS 키체인 구현체로 교체해야 한다.
    """

    def __init__(self, secrets: dict[str, str] | None = None) -> None:
        self._secrets: dict[str, str] = dict(secrets or {})

    def set(self, api_key_ref: str, value: str) -> None:
        self._secrets[api_key_ref] = value

    async def get(self, api_key_ref: str) -> str:
        try:
            return self._secrets[api_key_ref]
        except KeyError as exc:
            raise ProviderSecretNotFoundError(
                f"secret not found for ref={api_key_ref!r}",
                details={"api_key_ref": api_key_ref},
            ) from exc
