"""공통 Pydantic 베이스·믹스인·ID 헬퍼.

`orca_core.schema` 레이어는 Domain 순수 계층이므로 외부 I/O 라이브러리를
import 하지 않는다. 표준 라이브러리 + pydantic 만 사용한다.
"""

from __future__ import annotations

from datetime import UTC, datetime
import os
import secrets
import threading
import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "OrcaModel",
    "TimestampMixin",
    "generate_uuid_v7",
    "utc_now",
]


def utc_now() -> datetime:
    """현 시각(UTC, naive 금지)."""
    return datetime.now(tz=UTC)


_UUID_V7_LOCK = threading.Lock()
_UUID_V7_MAX_COUNTER: int = (1 << 12) - 1  # rand_a 12-bit field saturates here
# State mutated under lock. Wrapped in a dict to avoid `global` statements.
_UUID_V7_STATE: dict[str, int] = {"last_ms": 0, "last_counter": 0}


def generate_uuid_v7() -> str:
    """RFC 9562 UUID v7 (시간순 정렬 가능) 생성.

    표준 라이브러리만 사용하며 `uuid-utils` 등 외부 패키지 의존을 피한다.
    포맷: `{unix_ms:48}-{ver:4}-{rand_a:12}-{var:2}-{rand_b:62}`.

    **단조성 (M1)**: 동일 ms 내 여러 번 호출되면 rand_a 필드를 카운터로
    사용해 strict 증가를 보장한다. 카운터가 12-bit 한계를 넘으면 unix_ms
    를 1 증가시켜 다음 밀리초로 rollover 한다.
    """
    with _UUID_V7_LOCK:
        now_ms = int(time.time() * 1000) & 0xFFFFFFFFFFFF
        if now_ms > _UUID_V7_STATE["last_ms"]:
            _UUID_V7_STATE["last_ms"] = now_ms
            # start low, keep headroom within the ms tick
            _UUID_V7_STATE["last_counter"] = secrets.randbits(12) >> 4
        else:
            _UUID_V7_STATE["last_counter"] += 1
            if _UUID_V7_STATE["last_counter"] > _UUID_V7_MAX_COUNTER:
                _UUID_V7_STATE["last_ms"] += 1
                _UUID_V7_STATE["last_counter"] = 0
        unix_ms = _UUID_V7_STATE["last_ms"]
        rand_a = _UUID_V7_STATE["last_counter"]

    rand_b = secrets.randbits(62)

    # 128-bit 값 조립
    value = unix_ms << 80
    value |= 0x7 << 76  # version = 7
    value |= rand_a << 64
    value |= 0b10 << 62  # variant = RFC 4122
    value |= rand_b

    hex_str = f"{value:032x}"
    return f"{hex_str[0:8]}-{hex_str[8:12]}-{hex_str[12:16]}-{hex_str[16:20]}-{hex_str[20:32]}"


class OrcaModel(BaseModel):
    """프로젝트 공통 Pydantic 베이스.

    - `populate_by_name=True`: alias 필드도 이름으로 입력 가능
    - `extra='forbid'`: 알 수 없는 필드는 검증 오류
    - `frozen=False`: 가변 (Repository 가 PK 채움)
    """

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class TimestampMixin(BaseModel):
    """created_at / updated_at 타임스탬프 믹스인.

    Pydantic v2 는 `Field(default_factory=...)` 만으로 타임스탬프 자동 채움.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


def model_dump_safe(model: BaseModel, *, exclude_secrets: bool = True) -> dict[str, Any]:
    """`SecretStr` 를 자동으로 마스킹하는 dump.

    Pydantic v2 의 `SecretStr` 는 기본 dump 에서 `**********` 로 나오므로
    별도 처리가 필요 없으나 `exclude_secrets=True` 일 때는 아예 제거한다.
    """
    data = model.model_dump()
    if not exclude_secrets:
        return data
    return {k: v for k, v in data.items() if not _looks_like_secret_key(k)}


_SECRET_KEYS = {"api_key", "token", "password", "secret"}


def _looks_like_secret_key(key: str) -> bool:
    normalized = key.lower()
    return any(marker in normalized for marker in _SECRET_KEYS)


# OS-level sanity check: 시스템 시간이 1970 이전이면 UUID v7 이 깨진다.
# 패키지 import 시점에 한 번만 검증한다.
if (  # pragma: no cover - defensive
    os.environ.get("ORCA_TEST_BYPASS_TIME_CHECK") != "1" and int(time.time() * 1000) <= 0
):
    raise RuntimeError("System clock is invalid; UUID v7 generation will fail")
