"""PolicyEngine — design.md §6.3.1 평가 알고리즘 구현.

순수 함수 스타일: 입력(Policy, tool, args) → 출력(Decision). I/O 금지.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..schema.policy import Policy
from .decision import Decision
from .matcher import (
    DEFAULT_DENY_PATHS,
    extract_command,
    extract_hosts,
    matches_rule,
)

__all__ = ["PolicyContext", "PolicyEngine", "build_context"]


# H7: 알려진 path / 경로성 args 키. args 를 훑어 이 키들을 list[Path] 로 모은다.
# fs.move 같은 src/dst 페어, fs.copy multiple destinations 등을 지원.
_PATH_KEYS: tuple[str, ...] = (
    "path",
    "paths",
    "src",
    "dst",
    "source",
    "target",
    "from",
    "to",
    "destination",
    "destinations",
)


@dataclass(frozen=True, slots=True)
class PolicyContext:
    """build_context 반환 타입 (dataclass 로 정적 타입 보장).

    - `paths` : 정규화된 모든 경로 (fs_path scope any-match 대상)
    - `path`  : `paths[0]` 또는 None — 단일 경로 호출자용 호환성
    """

    paths: list[Path]
    path: Path | None
    command: str | None
    hosts: list[str]
    os_action: str | None


def _collect_paths(args: dict[str, Any]) -> list[Path]:
    """args 에서 경로성 값을 모아 `Path` 리스트로 반환.

    **expanduser 만 적용**하고 `resolve` 는 `_match_fs_path` 가 내부적으로
    수행한다 (매칭 시 resolve 전/후 경로를 모두 candidate 로 사용). 여기서
    바로 resolve 하면 원본 문자열이 소실되어 macOS symlink 케이스의 매칭이
    비대칭적으로 실패한다 (H3).
    """
    collected: list[Path] = []
    for key in _PATH_KEYS:
        if key not in args:
            continue
        value = args[key]
        if value is None:
            continue
        if isinstance(value, str):
            if value:
                collected.append(Path(value).expanduser())
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item:
                    collected.append(Path(item).expanduser())
    return collected


def build_context(args: dict[str, Any]) -> PolicyContext:
    """툴 args 에서 path(s) / command / hosts / os_action 컨텍스트 추출."""
    paths = _collect_paths(args)
    path = paths[0] if paths else None

    command = extract_command(args)
    hosts = extract_hosts(args)
    raw_action = args.get("action")
    os_action = raw_action if isinstance(raw_action, str) else None
    return PolicyContext(paths=paths, path=path, command=command, hosts=hosts, os_action=os_action)


def _matches_system_deny(paths: list[Path]) -> str | None:
    """DEFAULT_DENY_PATHS 중 하나라도 매칭되면 해당 패턴을 반환.

    이 룰은 priority=-∞ 로 간주되며 사용자 정책보다 먼저 적용된다.
    """
    if not paths:
        return None
    # 간단한 glob 매칭 — 패턴 끝 `/**` 은 해당 prefix 의 모든 하위 경로.
    for pattern in DEFAULT_DENY_PATHS:
        prefix = pattern.split("**", 1)[0].rstrip("/\\")
        if not prefix:
            continue
        for p in paths:
            p_str = str(p)
            # POSIX 형태로 비교. Windows prefix 는 문자열 단순 매칭.
            if p_str == prefix or p_str.startswith(prefix + "/"):
                return pattern
            if "\\" in prefix and (
                p_str == prefix or p_str.lower().startswith(prefix.lower() + "\\")
            ):
                return pattern
    return None


class PolicyEngine:
    """정책 평가 엔진 (순수 계층).

    사용 예:
        >>> engine = PolicyEngine()
        >>> decision = engine.evaluate(policy, tool_id="fs.delete", args={"path": "/tmp/x"})
    """

    def evaluate(
        self,
        policy: Policy,
        *,
        tool_id: str,
        args: dict[str, Any],
    ) -> Decision:
        """design.md §6.3.1 평가 알고리즘.

        0. **시스템 디렉토리 deny (DEFAULT_DENY_PATHS)** — 사용자 정책보다 우선
        1. 컨텍스트 정규화
        2. 매칭 룰 필터 (scope 별 matcher)
        3. priority 오름차순 정렬, 첫 매칭 룰 채택
        4. 없으면 `policy.default_effect()` 반환
        """
        ctx = build_context(args)

        # 0. 시스템 경로 하드코딩 deny — 사용자 rule 이 이를 override 하지 못함.
        denied_pattern = _matches_system_deny(ctx.paths)
        if denied_pattern is not None:
            return Decision(
                effect="deny",
                rule_id=None,
                reason=f"system path denied by default (matches {denied_pattern})",
                matched=True,
            )

        candidates = [
            rule
            for rule in policy.rules
            if matches_rule(
                rule,
                tool_id=tool_id,
                path=ctx.path,
                paths=ctx.paths,
                command=ctx.command,
                hosts=ctx.hosts,
                os_action=ctx.os_action,
            )
        ]

        if candidates:
            chosen = min(candidates, key=lambda r: r.priority)
            return Decision(
                effect=chosen.effect,
                rule_id=chosen.id,
                reason=chosen.reason,
                matched=True,
            )

        return Decision(
            effect=policy.default_effect(),
            rule_id=None,
            reason=f"default effect for mode={policy.mode}",
            matched=False,
        )
