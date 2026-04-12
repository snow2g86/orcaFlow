"""시크릿/PII 스크러빙 (conventions.md §7.4).

모든 감사 로그 파일 미러·Pydantic dump 경로에 통일된 스크러빙을 적용한다.
`api_key`, `token`, `password`, `secret` 같은 키는 `***` 로 치환.
경로 로깅은 `~` 로 홈 디렉토리 마스킹한다.

`mask_free_text_secrets` 는 JSON/HTML/plaintext 섞인 응답 본문 등에서
Bearer 토큰, JWT, `sk-…`/`pk-…` API 키, `"token": "…"` 같은 key/value 쌍을
패턴 기반으로 마스킹한다 (H1 regression — provider 4xx body 스크럽).
"""

from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

__all__ = [
    "MASK",
    "mask_free_text_secrets",
    "mask_home_path",
    "mask_url_secrets",
    "scrub_mapping",
    "scrub_value",
]

MASK = "***"

_SECRET_KEY_MARKERS: tuple[str, ...] = (
    "api_key",
    "apikey",
    "token",
    "password",
    "passwd",
    "secret",
    "authorization",
    "auth_header",
    "bearer",
)

_URL_SECRET_QUERY_PARAMS: frozenset[str] = frozenset(
    {
        "token",
        "access_token",
        "refresh_token",
        "api_key",
        "apikey",
        "password",
        "passwd",
        "secret",
        "client_secret",
        "auth",
        "authorization",
        "signature",
        "sig",
    }
)


def _looks_secret(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in _SECRET_KEY_MARKERS)


def mask_url_secrets(url: str) -> str:
    """URL 문자열의 querystring 내 민감 파라미터 값을 `***` 로 치환.

    `scheme://...` 가 아니어도 동작하나 query 문자열이 없는 값은 원본 그대로.
    파싱 실패시 원본 반환 (보수적 fail-open — 호출측의 key-based 스크러빙이
    추가 방어선).
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    if not parts.query:
        return url
    scrubbed_pairs = [
        (k, MASK if k.lower() in _URL_SECRET_QUERY_PARAMS else v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
    ]
    new_query = urlencode(scrubbed_pairs, doseq=False)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))


def _looks_like_url(value: str) -> bool:
    return "://" in value and "?" in value


def mask_home_path(value: str) -> str:
    """사용자 홈 디렉토리를 `~` 로 마스킹.

    conventions.md §7.4: 경로 로깅은 허용하되 사용자 홈은 `~` 로 마스킹.
    """
    home = os.path.expanduser("~")
    if home and value.startswith(home):
        return "~" + value[len(home) :]
    return value


def scrub_value(key: str, value: Any) -> Any:
    """키 이름이 시크릿 힌트를 포함하면 값을 마스킹한다.

    재귀적으로 dict/list 를 스크럽한다.
    """
    if _looks_secret(key):
        return MASK
    if isinstance(value, dict):
        return scrub_mapping(value)
    if isinstance(value, list):
        return [scrub_mapping(v) if isinstance(v, dict) else v for v in value]
    if isinstance(value, str):
        masked = value
        if _looks_like_url(masked):
            masked = mask_url_secrets(masked)
        return mask_home_path(masked)
    return value


def scrub_mapping(payload: dict[str, Any]) -> dict[str, Any]:
    """dict 의 시크릿 키를 재귀적으로 마스킹해 새 dict 반환."""
    return {k: scrub_value(k, v) for k, v in payload.items()}


# ---------------------------------------------------------------------------
# Free-text secret masking (H1)
# ---------------------------------------------------------------------------

# `Bearer <token>` — 10자 이상의 토큰 매칭.
_BEARER_RE = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-~+/=]{10,}")
# JWT 3-segment: `eyJ…` + `.` + base64url + `.` + base64url
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")
# `sk-abcdef…`, `pk-abcdef…`, `api-key-abcdef…`
_SK_RE = re.compile(
    r"\b(?:sk|pk)-[A-Za-z0-9]{10,}\b|\bapi[-_]?key[-_]?[A-Za-z0-9]{10,}\b",
    re.IGNORECASE,
)
# `"api_key": "value"` / `token=value` / `authorization: value` 류 key-value 쌍
_GENERIC_KEY_VAL_RE = re.compile(
    r"(?i)(\"?(?:api[_-]?key|token|password|secret|authorization)\"?\s*[:=]\s*\"?)"
    r"([^\"\s,}\]]+)"
)


def mask_free_text_secrets(text: str) -> str:
    """JSON/HTML/plaintext 본문에서 시크릿처럼 보이는 문자열을 마스킹.

    패턴 우선순위:
        1. `Bearer <token>`  → `Bearer ***`
        2. JWT (`eyJ…`)      → `***`
        3. `sk-…`, `pk-…`, `api_key_…` → `***`
        4. `"<key>": "<value>"` 형태의 key-value (key 가 `api_key|token|…`)
           → value 부분만 `***`

    None/빈 문자열은 그대로 반환. 패턴에 걸리지 않는 본문은 원본 유지.
    """
    if not text:
        return text
    result = _BEARER_RE.sub(r"\1***", text)
    result = _JWT_RE.sub("***", result)
    result = _SK_RE.sub("***", result)
    return _GENERIC_KEY_VAL_RE.sub(r"\1***", result)
