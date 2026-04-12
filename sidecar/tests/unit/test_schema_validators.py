"""schema.md section 5 불변 규칙 및 엔티티 유효성 검증 테스트."""

from __future__ import annotations

from pydantic import ValidationError
import pytest

from orca_core.schema import (
    AgentNode,
    AgentRole,
    AuditLog,
    Edge,
    JournalEntry,
    Policy,
    PolicyRule,
    Position,
    Run,
    Tool,
    Workflow,
    generate_uuid_v7,
)

# ---------------------------------------------------------------------------
# Workflow graph 참조 무결성
# ---------------------------------------------------------------------------


def test_workflow_accepts_valid_graph():
    wf = Workflow(
        name="t",
        nodes=[
            AgentNode(id="a", role="worker", position=Position(x=0, y=0)),
            AgentNode(id="b", role="worker", position=Position(x=1, y=0)),
        ],
        edges=[Edge(**{"from": "a", "to": "b"})],
        entrypoint="a",
    )
    assert wf.entrypoint_node_id == "a"
    assert wf.edges[0].from_ == "a"


def test_workflow_rejects_duplicate_node_ids():
    with pytest.raises(ValidationError, match="duplicate id"):
        Workflow(
            name="t",
            nodes=[
                AgentNode(id="a", role="w", position=Position(x=0, y=0)),
                AgentNode(id="a", role="w", position=Position(x=1, y=0)),
            ],
            edges=[],
            entrypoint="a",
        )


def test_workflow_rejects_unknown_entrypoint():
    with pytest.raises(ValidationError, match="entrypoint"):
        Workflow(
            name="t",
            nodes=[AgentNode(id="a", role="w", position=Position(x=0, y=0))],
            edges=[],
            entrypoint="ghost",
        )


def test_workflow_rejects_edge_with_unknown_endpoints():
    with pytest.raises(ValidationError, match="Edge.from"):
        Workflow(
            name="t",
            nodes=[AgentNode(id="a", role="w", position=Position(x=0, y=0))],
            edges=[Edge(**{"from": "ghost", "to": "a"})],
            entrypoint="a",
        )


def test_workflow_requires_non_empty_nodes():
    with pytest.raises(ValidationError):
        Workflow(name="t", nodes=[], edges=[], entrypoint="a")


# ---------------------------------------------------------------------------
# Tool ID consistency
# ---------------------------------------------------------------------------


def test_tool_requires_matching_namespace_and_name():
    with pytest.raises(ValidationError, match="namespace"):
        Tool(
            id="fs.write_file",
            namespace="fs",
            name="read_file",
            description="x",
            side_effect="write",
            reversible=True,
            default_dry_run=True,
        )


def test_tool_valid_id_ok():
    tool = Tool(
        id="fs.read_file",
        namespace="fs",
        name="read_file",
        description="x",
        side_effect="read",
        reversible=False,
        default_dry_run=False,
    )
    assert tool.id == "fs.read_file"


# ---------------------------------------------------------------------------
# Policy invariants (schema.md section 5 #6)
# ---------------------------------------------------------------------------


def test_policy_default_effects():
    strict = Policy(name="strict", mode="strict")
    ask = Policy(name="ask", mode="ask")
    trusted = Policy(name="trusted", mode="trusted")
    assert strict.default_effect() == "deny"
    assert ask.default_effect() == "ask"
    assert trusted.default_effect() == "allow"


def test_policy_rejects_duplicate_priority():
    with pytest.raises(ValidationError, match="duplicate rule priority"):
        Policy(
            name="p",
            mode="ask",
            rules=[
                PolicyRule(priority=10, scope="tool_id", matcher="fs.*", effect="allow"),
                PolicyRule(priority=10, scope="tool_id", matcher="shell.*", effect="deny"),
            ],
        )


def test_policy_propagates_id_to_rules():
    pol = Policy(
        name="p",
        mode="ask",
        rules=[
            PolicyRule(priority=10, scope="tool_id", matcher="fs.*", effect="allow"),
        ],
    )
    assert pol.rules[0].policy_id == pol.id


# ---------------------------------------------------------------------------
# JournalEntry invariant (schema.md section 5 #2)
# ---------------------------------------------------------------------------


def test_journal_entry_reversible_requires_before_or_ref():
    with pytest.raises(ValidationError, match="reversible"):
        JournalEntry(
            run_step_id="s",
            tool_call_id="t",
            kind="fs_write",
            before=None,
            before_storage_ref=None,
            reversible=True,
        )


def test_journal_entry_irreversible_allows_no_before():
    entry = JournalEntry(
        run_step_id="s",
        tool_call_id="t",
        kind="custom",
        reversible=False,
    )
    assert entry.reversible is False


# ---------------------------------------------------------------------------
# AuditLog immutability (schema.md section 5 #8)
# ---------------------------------------------------------------------------


def test_audit_log_is_frozen():
    record = AuditLog(
        actor="user",
        action="fs.delete",
        target="/tmp/x",
        status="success",
        policy_decision="allow",
        run_id="r",
        run_step_id="s",
    )
    with pytest.raises(ValidationError):
        record.actor = "attacker"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Run.workflow_snapshot invariant (schema.md section 5 #3)
# ---------------------------------------------------------------------------


def test_run_requires_workflow_snapshot():
    with pytest.raises(ValidationError):
        Run(
            workflow_id="wf",
            workflow_snapshot="",
            trigger="manual",
            status="pending",
        )


def test_run_accepts_valid_snapshot():
    run = Run(
        workflow_id="wf",
        workflow_snapshot="version: 1\nname: x",
        trigger="manual",
        status="pending",
    )
    assert run.workflow_snapshot.startswith("version")


# ---------------------------------------------------------------------------
# AgentRole & UUID helpers
# ---------------------------------------------------------------------------


def test_agent_role_requires_llm_profile():
    with pytest.raises(ValidationError):
        AgentRole(
            name="x",
            role_type="worker",
            system_prompt="hi",
        )  # type: ignore[call-arg]


def test_generate_uuid_v7_is_unique_and_sortable():
    ids = sorted([generate_uuid_v7() for _ in range(20)])
    # 시간순 정렬 가능 → 앞부분이 단조 증가
    assert len(set(ids)) == 20
    # Check version nibble
    for uid in ids:
        assert uid[14] == "7", f"{uid} is not UUID v7"


def test_generate_uuid_v7_strictly_monotonic():
    """M1 regression: rapid calls within the same ms must strictly increase.

    We generate many IDs back-to-back and check that the list is both unique
    and strictly sorted (no equal or descending pair).
    """
    import itertools

    count = 1000
    ids = [generate_uuid_v7() for _ in range(count)]
    assert len(set(ids)) == count
    for prev, curr in itertools.pairwise(ids):
        assert curr > prev, f"UUID v7 not strictly increasing: {prev} >= {curr}"


# ---------------------------------------------------------------------------
# H4 regression: Policy rejects invalid regex in shell_command rules
# ---------------------------------------------------------------------------


def test_policy_rejects_invalid_shell_regex():
    with pytest.raises(ValidationError, match="invalid regex"):
        Policy(
            name="p",
            mode="strict",
            rules=[
                PolicyRule(
                    priority=10,
                    scope="shell_command",
                    matcher=r"[unterminated",
                    effect="deny",
                ),
            ],
        )


# ---------------------------------------------------------------------------
# M2 regression: destructive/write tools must default_dry_run=True
# ---------------------------------------------------------------------------


def test_tool_destructive_requires_default_dry_run():
    with pytest.raises(ValidationError, match="default_dry_run"):
        Tool(
            id="fs.delete",
            namespace="fs",
            name="delete",
            description="delete",
            side_effect="destructive",
            reversible=False,
            default_dry_run=False,
        )


def test_tool_write_requires_default_dry_run():
    with pytest.raises(ValidationError, match="default_dry_run"):
        Tool(
            id="fs.write_file",
            namespace="fs",
            name="write_file",
            description="write",
            side_effect="write",
            reversible=True,
            default_dry_run=False,
        )


def test_tool_read_does_not_require_dry_run():
    t = Tool(
        id="fs.read_file",
        namespace="fs",
        name="read_file",
        description="read",
        side_effect="read",
        reversible=False,
        default_dry_run=False,
    )
    assert t.default_dry_run is False


# ---------------------------------------------------------------------------
# M3 regression: Workflow graph must be a DAG (no cycles, no self-loops)
# ---------------------------------------------------------------------------


def test_workflow_rejects_self_loop():
    with pytest.raises(ValidationError, match="self-loop"):
        Workflow(
            name="t",
            nodes=[AgentNode(id="a", role="w", position=Position(x=0, y=0))],
            edges=[Edge(**{"from": "a", "to": "a"})],
            entrypoint="a",
        )


def test_workflow_rejects_cycle():
    with pytest.raises(ValidationError, match="cycle"):
        Workflow(
            name="t",
            nodes=[
                AgentNode(id="a", role="w", position=Position(x=0, y=0)),
                AgentNode(id="b", role="w", position=Position(x=1, y=0)),
                AgentNode(id="c", role="w", position=Position(x=2, y=0)),
            ],
            edges=[
                Edge(**{"from": "a", "to": "b"}),
                Edge(**{"from": "b", "to": "c"}),
                Edge(**{"from": "c", "to": "a"}),
            ],
            entrypoint="a",
        )
