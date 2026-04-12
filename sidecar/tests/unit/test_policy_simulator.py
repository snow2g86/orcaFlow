"""Policy simulator — design.md section 6.3.3."""

from __future__ import annotations

from orca_core.policy.simulator import Scenario, simulate_policy
from orca_core.schema import Policy, PolicyRule


def test_simulate_multiple_scenarios():
    pol = Policy(
        name="default",
        mode="ask",
        rules=[
            PolicyRule(priority=10, scope="tool_id", matcher="fs.*", effect="allow"),
            PolicyRule(
                priority=20,
                scope="shell_command",
                matcher=r"^rm\s+-rf\s+/",
                effect="deny",
            ),
        ],
    )
    scenarios = [
        Scenario(tool_id="fs.delete", args={"path": "/tmp/old.txt"}),
        Scenario(tool_id="shell.exec", args={"cmd": "rm -rf /"}),
        Scenario(tool_id="web.http_request", args={"url": "https://a.com"}),
    ]
    results = simulate_policy(pol, scenarios)
    assert len(results) == 3
    assert results[0].decision.effect == "allow"
    assert results[1].decision.effect == "deny"
    assert results[2].decision.effect == "ask"  # fell through to default
    assert results[0].scenario.tool_id == "fs.delete"
