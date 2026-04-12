"""Matcher 단위 테스트."""

from __future__ import annotations

from pathlib import Path

from orca_core.policy.matcher import (
    extract_command,
    extract_hosts,
    matches_rule,
    normalize_path,
)
from orca_core.schema import PolicyRule


def test_normalize_path_expands_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    resolved = normalize_path("~/file.txt")
    assert resolved.is_absolute()
    assert str(resolved).startswith(str(tmp_path))


def test_extract_command_from_string():
    assert extract_command({"cmd": "ls -l"}) == "ls -l"
    assert extract_command({"command": ["ls", "-l"]}) == "ls -l"
    assert extract_command({"shell": "pwd"}) == "pwd"
    assert extract_command({}) is None


def test_extract_hosts_from_url():
    hosts = extract_hosts({"url": "https://user:pw@api.example.com:8443/v1/test?q=1"})
    assert "api.example.com" in hosts


def test_extract_hosts_explicit():
    hosts = extract_hosts({"host": "a.com", "hosts": ["b.com", "c.com"]})
    assert set(hosts) == {"a.com", "b.com", "c.com"}


def test_matches_rule_fs_path_requires_path(tmp_path):
    rule = PolicyRule(priority=1, scope="fs_path", matcher=str(tmp_path / "**"), effect="allow")
    assert matches_rule(rule, tool_id="fs.read", path=tmp_path / "a.txt", command=None, hosts=[])
    assert not matches_rule(rule, tool_id="fs.read", path=None, command=None, hosts=[])


def test_matches_rule_shell_requires_command():
    rule = PolicyRule(priority=1, scope="shell_command", matcher=r"^rm ", effect="deny")
    assert matches_rule(rule, tool_id="shell.exec", path=None, command="rm x", hosts=[])
    assert not matches_rule(rule, tool_id="shell.exec", path=None, command=None, hosts=[])


def test_matches_rule_tool_id_prefix():
    rule = PolicyRule(priority=1, scope="tool_id", matcher="fs.*", effect="allow")
    assert matches_rule(rule, tool_id="fs.read_file", path=None, command=None, hosts=[])
    assert not matches_rule(rule, tool_id="shell.exec", path=None, command=None, hosts=[])


def test_matches_rule_tool_id_exact():
    rule = PolicyRule(priority=1, scope="tool_id", matcher="os.applescript", effect="ask")
    assert matches_rule(rule, tool_id="os.applescript", path=None, command=None, hosts=[])


def test_matches_rule_invalid_shell_regex_raises():
    """H4 regression: invalid regex must never silently evaluate to False.

    `matches_rule` raises `PolicyEvaluationError` at runtime. Policy
    validation catches this even earlier at model construction time (see
    `test_policy_rejects_invalid_shell_regex`).
    """
    import pytest

    from orca_core.policy.matcher import PolicyEvaluationError

    rule = PolicyRule(priority=1, scope="shell_command", matcher=r"[", effect="deny")
    with pytest.raises(PolicyEvaluationError):
        matches_rule(rule, tool_id="shell.exec", path=None, command="rm x", hosts=[])


def test_matches_rule_network_host():
    rule = PolicyRule(priority=1, scope="network_host", matcher="*.example.com", effect="allow")
    assert matches_rule(
        rule,
        tool_id="web.http",
        path=None,
        command=None,
        hosts=["api.example.com"],
    )
    assert not matches_rule(rule, tool_id="web.http", path=None, command=None, hosts=["other.com"])


def test_matches_rule_os_api_requires_action():
    rule = PolicyRule(priority=1, scope="os_api", matcher="tell*", effect="deny")
    assert matches_rule(
        rule,
        tool_id="os.applescript",
        path=None,
        command=None,
        hosts=[],
        os_action="tell application",
    )
    assert not matches_rule(rule, tool_id="os.applescript", path=None, command=None, hosts=[])


def test_normalize_path_handles_absolute(tmp_path: Path):
    p = tmp_path / "subdir" / "file.txt"
    p.parent.mkdir(parents=True)
    p.write_text("x")
    resolved = normalize_path(str(p))
    assert resolved == p.resolve()
