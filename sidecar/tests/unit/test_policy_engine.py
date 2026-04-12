"""PolicyEngine — design.md section 6.3.1 알고리즘 커버리지."""

from __future__ import annotations

import sys

import pytest

from orca_core.policy import PolicyEngine
from orca_core.schema import Policy, PolicyRule


@pytest.fixture
def engine() -> PolicyEngine:
    return PolicyEngine()


# ---------------------------------------------------------------------------
# Default effects by mode (no matching rule)
# ---------------------------------------------------------------------------


def test_strict_mode_default_deny(engine: PolicyEngine):
    pol = Policy(name="strict", mode="strict")
    result = engine.evaluate(pol, tool_id="fs.read_file", args={"path": "/tmp/x"})
    assert result.effect == "deny"
    assert result.matched is False
    assert result.rule_id is None


def test_ask_mode_default_ask(engine: PolicyEngine):
    pol = Policy(name="ask", mode="ask")
    result = engine.evaluate(pol, tool_id="fs.read_file", args={"path": "/tmp/x"})
    assert result.effect == "ask"
    assert result.matched is False


def test_trusted_mode_default_allow(engine: PolicyEngine):
    pol = Policy(name="trusted", mode="trusted")
    result = engine.evaluate(pol, tool_id="fs.read_file", args={"path": "/tmp/x"})
    assert result.effect == "allow"


# ---------------------------------------------------------------------------
# Rule selection: priority ordering
# ---------------------------------------------------------------------------


def test_lowest_priority_wins(engine: PolicyEngine):
    pol = Policy(
        name="p",
        mode="ask",
        rules=[
            PolicyRule(priority=100, scope="tool_id", matcher="fs.*", effect="deny"),
            PolicyRule(priority=10, scope="tool_id", matcher="fs.*", effect="allow"),
        ],
    )
    result = engine.evaluate(pol, tool_id="fs.delete", args={})
    assert result.effect == "allow"
    assert result.matched is True


# ---------------------------------------------------------------------------
# fs_path scope with expand/resolve
# ---------------------------------------------------------------------------


def test_fs_path_glob_matches_home(tmp_path, engine: PolicyEngine, monkeypatch):
    # Redirect HOME to an isolated path
    monkeypatch.setenv("HOME", str(tmp_path))
    docs = tmp_path / "Documents" / "report.md"
    docs.parent.mkdir(parents=True)
    docs.write_text("x")

    pol = Policy(
        name="p",
        mode="strict",
        rules=[
            PolicyRule(
                priority=10,
                scope="fs_path",
                matcher="~/Documents/**",
                effect="allow",
                reason="user docs",
            ),
        ],
    )
    result = engine.evaluate(pol, tool_id="fs.read_file", args={"path": "~/Documents/report.md"})
    assert result.effect == "allow"
    assert result.rule_id is not None
    assert result.reason == "user docs"


def test_fs_path_no_match_falls_through_to_default(tmp_path, engine: PolicyEngine):
    pol = Policy(
        name="p",
        mode="strict",
        rules=[
            PolicyRule(
                priority=10,
                scope="fs_path",
                matcher=str(tmp_path / "allowed" / "**"),
                effect="allow",
            ),
        ],
    )
    other = tmp_path / "denied" / "x.txt"
    result = engine.evaluate(pol, tool_id="fs.write_file", args={"path": str(other)})
    assert result.effect == "deny"
    assert result.matched is False


# ---------------------------------------------------------------------------
# shell_command scope (regex)
# ---------------------------------------------------------------------------


def test_shell_command_regex_deny(engine: PolicyEngine):
    pol = Policy(
        name="p",
        mode="ask",
        rules=[
            PolicyRule(
                priority=10,
                scope="shell_command",
                matcher=r"^rm\s+-rf\s+/",
                effect="deny",
                reason="root recursive delete",
            ),
        ],
    )
    result = engine.evaluate(pol, tool_id="shell.exec", args={"cmd": "rm -rf /"})
    assert result.effect == "deny"
    assert result.reason == "root recursive delete"


def test_shell_command_no_match(engine: PolicyEngine):
    pol = Policy(
        name="p",
        mode="ask",
        rules=[
            PolicyRule(
                priority=10,
                scope="shell_command",
                matcher=r"^rm\s+-rf\s+/",
                effect="deny",
            ),
        ],
    )
    result = engine.evaluate(pol, tool_id="shell.exec", args={"cmd": "ls -l /tmp"})
    assert result.effect == "ask"  # default for ask mode


# ---------------------------------------------------------------------------
# network_host scope (glob via fnmatch)
# ---------------------------------------------------------------------------


def test_network_host_glob(engine: PolicyEngine):
    pol = Policy(
        name="p",
        mode="strict",
        rules=[
            PolicyRule(
                priority=10,
                scope="network_host",
                matcher="*.example.com",
                effect="allow",
            ),
        ],
    )
    result = engine.evaluate(
        pol,
        tool_id="web.http_request",
        args={"url": "https://api.example.com/v1/test"},
    )
    assert result.effect == "allow"


def test_network_host_no_match(engine: PolicyEngine):
    pol = Policy(
        name="p",
        mode="strict",
        rules=[
            PolicyRule(
                priority=10,
                scope="network_host",
                matcher="*.example.com",
                effect="allow",
            ),
        ],
    )
    result = engine.evaluate(
        pol,
        tool_id="web.http_request",
        args={"url": "https://api.other.com/x"},
    )
    assert result.effect == "deny"


# ---------------------------------------------------------------------------
# tool_id scope with wildcard
# ---------------------------------------------------------------------------


def test_tool_id_wildcard(engine: PolicyEngine):
    pol = Policy(
        name="p",
        mode="ask",
        rules=[
            PolicyRule(priority=10, scope="tool_id", matcher="fs.*", effect="allow"),
            PolicyRule(priority=20, scope="tool_id", matcher="os.applescript", effect="ask"),
        ],
    )
    assert engine.evaluate(pol, tool_id="fs.read_file", args={}).effect == "allow"
    assert engine.evaluate(pol, tool_id="os.applescript", args={}).effect == "ask"
    # Unknown tool → default mode (ask)
    assert engine.evaluate(pol, tool_id="shell.exec", args={}).effect == "ask"


# ---------------------------------------------------------------------------
# os_api scope
# ---------------------------------------------------------------------------


def test_os_api_scope(engine: PolicyEngine):
    pol = Policy(
        name="p",
        mode="strict",
        rules=[
            PolicyRule(priority=10, scope="os_api", matcher="tell *", effect="deny"),
        ],
    )
    result = engine.evaluate(pol, tool_id="os.applescript", args={"action": "tell application"})
    assert result.effect == "deny"


# ---------------------------------------------------------------------------
# dry_run_only effect
# ---------------------------------------------------------------------------


def test_dry_run_only_effect_returned(engine: PolicyEngine):
    pol = Policy(
        name="p",
        mode="ask",
        rules=[
            PolicyRule(
                priority=10,
                scope="tool_id",
                matcher="fs.delete",
                effect="dry_run_only",
            ),
        ],
    )
    # Use /private/tmp to avoid both the system deny list and symlink quirks.
    result = engine.evaluate(pol, tool_id="fs.delete", args={"path": "/private/tmp/x"})
    assert result.effect == "dry_run_only"


# ---------------------------------------------------------------------------
# H3 regression: macOS /tmp → /private/tmp symlink still matches /tmp/** rule
# ---------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS symlink behavior")
def test_fs_path_matches_across_macos_symlink(engine: PolicyEngine):
    """`/tmp/**` rule must match `/tmp/x` even after resolve → /private/tmp/x.

    Previously the matcher only compared the resolved path against the raw
    pattern prefix, so `/tmp/**` failed to hit `/private/tmp/x`.
    """
    pol = Policy(
        name="p",
        mode="strict",
        rules=[
            PolicyRule(
                priority=10,
                scope="fs_path",
                matcher="/tmp/**",
                effect="allow",
                reason="tmp allowed",
            ),
        ],
    )
    result = engine.evaluate(pol, tool_id="fs.read_file", args={"path": "/tmp/x"})
    assert result.effect == "allow"
    # And the inverse: a /private/tmp pattern should still match input /tmp/x
    pol2 = Policy(
        name="p2",
        mode="strict",
        rules=[
            PolicyRule(
                priority=10,
                scope="fs_path",
                matcher="/private/tmp/**",
                effect="allow",
            ),
        ],
    )
    result2 = engine.evaluate(pol2, tool_id="fs.read_file", args={"path": "/tmp/x"})
    assert result2.effect == "allow"


# ---------------------------------------------------------------------------
# H7 regression: multi-path args (fs.move src/dst) evaluated as any-match
# ---------------------------------------------------------------------------


def test_multi_path_deny_wins_across_src_dst(engine: PolicyEngine, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".ssh").mkdir()
    (tmp_path / "Documents").mkdir()

    pol = Policy(
        name="p",
        mode="strict",
        rules=[
            PolicyRule(
                priority=5,
                scope="fs_path",
                matcher="~/.ssh/**",
                effect="deny",
                reason="ssh private",
            ),
            PolicyRule(
                priority=100,
                scope="fs_path",
                matcher="~/Documents/**",
                effect="allow",
            ),
        ],
    )
    # src is allowed but dst is denied → deny wins because of lowest priority.
    result = engine.evaluate(
        pol,
        tool_id="fs.move",
        args={"src": "~/Documents/a", "dst": "~/.ssh/b"},
    )
    assert result.effect == "deny"
    assert result.reason == "ssh private"


def test_multi_path_known_aliases_collected(engine: PolicyEngine):
    pol = Policy(
        name="p",
        mode="strict",
        rules=[
            PolicyRule(
                priority=10,
                scope="fs_path",
                matcher="/private/tmp/**",
                effect="allow",
            ),
        ],
    )
    # `source`/`target` variants
    result = engine.evaluate(
        pol,
        tool_id="fs.copy",
        args={"source": "/private/tmp/a", "target": "/private/tmp/b"},
    )
    assert result.effect == "allow"


# ---------------------------------------------------------------------------
# M6 regression: DEFAULT_DENY_PATHS take priority over any user rule
# ---------------------------------------------------------------------------


def test_default_deny_system_paths_override_user_allow(engine: PolicyEngine):
    pol = Policy(
        name="p",
        mode="trusted",
        rules=[
            PolicyRule(
                priority=1,
                scope="fs_path",
                matcher="/System/**",
                effect="allow",  # user tries to allow but must be overridden
            ),
        ],
    )
    result = engine.evaluate(pol, tool_id="fs.write_file", args={"path": "/System/Library/foo"})
    assert result.effect == "deny"
    assert result.matched is True
    assert "system path" in (result.reason or "").lower()
