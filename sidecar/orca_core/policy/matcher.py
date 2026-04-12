"""Scope 별 Policy matcher.

각 스코프의 `matcher` 문자열 해석 규칙 (design.md §6.3.1):
- `fs_path`: glob 패턴 (pathspec 사용)
- `shell_command`: 정규식 (컴파일 캐시)
- `network_host`: glob (fnmatch)
- `os_api`: 자유 문자열, 접두/정확 매치
- `tool_id`: 정확 매치 또는 접두 패턴 (`fs.*`)
"""

from __future__ import annotations

import fnmatch
import functools
from pathlib import Path
import re
from typing import Any

import pathspec
from pathspec.patterns.gitwildmatch import GitWildMatchPattern

from ..errors import OrcaError
from ..schema.policy import PolicyRule, PolicyScope

__all__ = [
    "DEFAULT_DENY_PATHS",
    "PolicyEvaluationError",
    "extract_command",
    "extract_hosts",
    "matches_rule",
    "normalize_path",
    "validate_rule_patterns",
]


# M6: 시스템 디렉토리 하드코딩 deny 리스트. 사용자 정책에 앞서 항상 먼저
# 평가된다 (priority=-∞). 여기에 쓰기 허용 허용은 불가.
DEFAULT_DENY_PATHS: tuple[str, ...] = (
    "/System/**",
    "/Library/LaunchDaemons/**",
    "/Library/LaunchAgents/**",
    "C:\\Windows\\System32\\**",
    "C:\\Windows\\System32\\**/*",
)


class PolicyEvaluationError(OrcaError):
    """Policy 평가 중 회복 불가능한 오류 (컴파일 실패 등)."""

    code = "policy.evaluation_error"
    http_status = 500


def normalize_path(raw: str | Path) -> Path:
    """사용자 경로 입력을 정규화.

    conventions.md §8.2 에 따라 `expanduser + resolve` 로 절대 경로화.
    `strict=False` — 존재하지 않는 경로여도 정규화만 수행한다.
    **심볼릭 링크는 resolve 로 따라간다.** 해석된 실제 경로를 정책에 노출
    해서 심볼릭 링크를 통한 화이트리스트 우회를 막는다.

    주의: 존재하지 않는 parent 경로가 포함된 경로는 `Path.resolve(strict=
    False)` 가 symlink 해석을 **제한적으로** 수행한다 — 실제로 존재하지
    않는 중간 디렉토리는 해석 대상이 아니므로 매처는 원본 문자열 기준의
    매칭도 병행해야 한다 (`_match_fs_path` 참조).
    """
    return Path(raw).expanduser().resolve(strict=False)


def extract_command(args: dict[str, Any]) -> str | None:
    """툴 args 에서 shell command 추출.

    일반적으로 `cmd`, `command`, `shell` 키를 본다. 리스트면 공백 join.
    """
    for key in ("cmd", "command", "shell"):
        raw = args.get(key)
        if raw is None:
            continue
        if isinstance(raw, list):
            return " ".join(str(x) for x in raw)
        return str(raw)
    return None


def extract_hosts(args: dict[str, Any]) -> list[str]:
    """툴 args 에서 호스트 목록 추출.

    `url` / `host` / `hosts` 키를 확인. URL 이면 netloc 추출.
    """
    hosts: list[str] = []
    for key in ("host", "hostname"):
        if (val := args.get(key)) is not None:
            hosts.append(str(val))
    raw_hosts = args.get("hosts")
    if isinstance(raw_hosts, list):
        hosts.extend(str(x) for x in raw_hosts)

    url = args.get("url")
    if isinstance(url, str):
        # Simple netloc extraction without urlparse to keep this dependency-free fast.
        rest = url.split("://", 1)[1] if "://" in url else url
        rest = rest.split("/", 1)[0]
        rest = rest.split("?", 1)[0]
        if "@" in rest:
            rest = rest.split("@", 1)[1]
        if ":" in rest:
            rest = rest.split(":", 1)[0]
        if rest:
            hosts.append(rest)
    return hosts


@functools.lru_cache(maxsize=256)
def _compile_regex(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern)


@functools.lru_cache(maxsize=256)
def _compile_pathspec(pattern: str) -> pathspec.PathSpec:
    # pathspec 의 gitwildmatch 는 glob 스타일 (`**`, `?`, `[...]`) 을 지원.
    return pathspec.PathSpec.from_lines(GitWildMatchPattern, [pattern])


def _pathspec_match(matcher_abs: str, candidate: Path) -> bool:
    """절대 경로 matcher 와 candidate 를 비교."""
    try:
        rel = candidate.as_posix().lstrip("/")
    except ValueError:
        rel = candidate.as_posix()
    spec = _compile_pathspec(matcher_abs.lstrip("/"))
    return spec.match_file(rel)


def _match_fs_path(matcher: str, path: Path) -> bool:
    """fs_path scope 매칭.

    macOS 심볼릭 링크(`/tmp` → `/private/tmp` 등)로 인해 matcher 와 target
    이 서로 다른 prefix 로 끝나는 경우가 많다. 해결책: **target 을 resolve
    한 경로와 원본(expanduser 만 된) 경로 두 가지** 를 matcher 와 대조해
    OR 조합으로 판단한다. 두 경로 중 하나라도 매칭되면 True.
    """
    expanded = str(Path(matcher).expanduser())

    # 후보 경로 집합: resolve 한 경로 + 원본(입력) 경로.
    candidates: list[Path] = [path]
    resolved = path.resolve(strict=False)
    if resolved != path:
        candidates.append(resolved)

    if expanded.startswith("/"):
        abs_matcher = Path(expanded).as_posix()
        return any(_pathspec_match(abs_matcher, c) for c in candidates)

    # 상대 matcher 는 후보 경로의 as_posix 로 pathspec 평가.
    spec = _compile_pathspec(expanded)
    for c in candidates:
        try:
            rel = c.as_posix().lstrip("/")
        except ValueError:
            rel = c.as_posix()
        if spec.match_file(rel):
            return True
    return False


def _match_shell(matcher: str, command: str) -> bool:
    """shell_command scope 매칭 (regex).

    **Fail-closed**: 정규식 컴파일 실패 시 `False` 를 반환하지 않고
    `PolicyEvaluationError` 를 raise. 정상 경로에서는 이 오류가 발생할
    수 없도록 `validate_rule_patterns` 에서 미리 검증한다.
    """
    try:
        rx = _compile_regex(matcher)
    except re.error as exc:
        raise PolicyEvaluationError(
            f"invalid regex in shell_command rule: {matcher!r}",
            details={"pattern": matcher, "cause": str(exc)},
        ) from exc
    return rx.search(command) is not None


def _match_host(matcher: str, host: str) -> bool:
    return fnmatch.fnmatchcase(host, matcher)


def _match_tool_id(matcher: str, tool_id: str) -> bool:
    if matcher == tool_id:
        return True
    if matcher.endswith(".*"):
        return tool_id.startswith(matcher[:-1])  # keep the dot
    # fnmatch 도 허용 (`fs.*_file`)
    return fnmatch.fnmatchcase(tool_id, matcher)


def _match_os_api(matcher: str, action: str) -> bool:
    if matcher == action:
        return True
    return fnmatch.fnmatchcase(action, matcher)


def validate_rule_patterns(rules: list[PolicyRule]) -> None:
    """shell_command scope 의 모든 matcher 를 사전 컴파일해 오류 조기 탐지.

    잘못된 정규식 deny 룰이 조용히 무효화되는 것을 막기 위해 Policy 생성
    시점에 호출된다. 실패 시 `ValueError` (Pydantic `ValidationError` 로
    wrap 된다).
    """
    for rule in rules:
        if rule.scope == "shell_command":
            try:
                re.compile(rule.matcher)
            except re.error as exc:
                raise ValueError(
                    f"PolicyRule[{rule.priority}] has invalid regex matcher {rule.matcher!r}: {exc}"
                ) from exc


def matches_rule(  # noqa: PLR0911  # exhaustive scope dispatch
    rule: PolicyRule,
    *,
    tool_id: str,
    path: Path | None,
    command: str | None,
    hosts: list[str],
    os_action: str | None = None,
    paths: list[Path] | None = None,
) -> bool:
    """한 룰이 현재 컨텍스트에 매칭되는지 판정.

    매칭 규칙은 scope 별로 다르다. scope 이 현재 컨텍스트의 입력을 제공받지
    못했다면 (예: `fs_path` 인데 path 가 None) 매칭 실패로 취급한다.

    `paths` 가 주어지면 fs_path scope 는 **any-match** 로 하나라도 맞으면
    True 를 반환한다. H7 에서 `fs.move` 같은 멀티-경로 툴을 지원하려고
    추가됐다. 단일 path 인 기존 호출자는 그대로 `path=` 만 써도 된다.
    """
    scope: PolicyScope = rule.scope
    if scope == "fs_path":
        all_paths: list[Path] = []
        if paths:
            all_paths.extend(paths)
        elif path is not None:
            all_paths.append(path)
        if not all_paths:
            return False
        return any(_match_fs_path(rule.matcher, p) for p in all_paths)
    if scope == "shell_command":
        if command is None:
            return False
        return _match_shell(rule.matcher, command)
    if scope == "network_host":
        return any(_match_host(rule.matcher, h) for h in hosts)
    if scope == "os_api":
        if os_action is None:
            return False
        return _match_os_api(rule.matcher, os_action)
    if scope == "tool_id":
        return _match_tool_id(rule.matcher, tool_id)
    return False  # pragma: no cover — Literal exhaustiveness
