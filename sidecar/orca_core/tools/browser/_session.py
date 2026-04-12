"""BrowserSessionManager — Playwright 세션 라이프사이클 관리.

Playwright 가 설치되지 않은 환경에서는 `require_playwright()` 가
`ToolRuntimeError` 를 raise 한다.
"""

from __future__ import annotations

import ipaddress
import re
from typing import Any
from urllib.parse import urlparse

from ...errors import ToolRuntimeError
from ...schema._base import generate_uuid_v7

__all__ = ["BrowserSessionManager", "require_playwright", "validate_url_host"]

# Lazy import guard
try:
    from playwright.async_api import async_playwright  # type: ignore[import-not-found]

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

# Internal network patterns (blocked by default)
_PRIVATE_HOST_RE = re.compile(
    r"^("
    r"localhost|"
    r"127\.\d+\.\d+\.\d+|"
    r"10\.\d+\.\d+\.\d+|"
    r"172\.(1[6-9]|2\d|3[01])\.\d+\.\d+|"
    r"192\.168\.\d+\.\d+|"
    r"\[?::1\]?"
    r")$",
    re.IGNORECASE,
)


def require_playwright() -> None:
    """Playwright 설치 여부를 확인하고 없으면 ToolRuntimeError."""
    if not PLAYWRIGHT_AVAILABLE:
        raise ToolRuntimeError(
            "playwright not installed — install with: pip install playwright && playwright install",
            details={"missing_dependency": "playwright"},
        )


def validate_url_host(url: str, *, allow_private: bool = False) -> None:
    """URL 호스트가 내부 네트워크인지 검증. 기본 차단."""
    parsed = urlparse(url)
    host = parsed.hostname or ""

    if not allow_private and _is_private_host(host):
        raise ToolRuntimeError(
            f"access to internal host '{host}' is blocked by default policy",
            details={"host": host, "url": url},
        )


def _is_private_host(host: str) -> bool:
    """호스트가 사설 네트워크 또는 로컬호스트인지 확인."""
    if _PRIVATE_HOST_RE.match(host):
        return True
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    else:
        return addr.is_private or addr.is_loopback


class BrowserSessionManager:
    """싱글턴 세션 매니저. 세션 ID → (browser, context, page) 매핑."""

    _instance: BrowserSessionManager | None = None

    def __init__(self) -> None:
        self._sessions: dict[str, Any] = {}
        self._playwright: Any = None

    @classmethod
    def get_instance(cls) -> BrowserSessionManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """테스트용 리셋."""
        cls._instance = None

    async def create_session(self, *, headless: bool = True) -> str:
        require_playwright()
        if self._playwright is None:
            self._playwright = await async_playwright().start()

        browser = await self._playwright.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()
        session_id = generate_uuid_v7()
        self._sessions[session_id] = {
            "browser": browser,
            "context": context,
            "page": page,
        }
        return session_id

    def get_page(self, session_id: str) -> Any:
        session = self._sessions.get(session_id)
        if session is None:
            raise ToolRuntimeError(
                f"browser session not found: {session_id}",
                details={"session_id": session_id},
            )
        return session["page"]

    async def close_session(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session:
            await session["browser"].close()

    async def close_all(self) -> None:
        for sid in list(self._sessions.keys()):
            await self.close_session(sid)
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
