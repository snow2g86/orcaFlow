"""Planner — 구조화 출력, 1회 재시도, PlannerError."""

from __future__ import annotations

import pytest

from orca_core.orchestrator import Planner, PlannerError
from orca_core.providers._base import ChatMessage, ChatResponse, ChatToolCall, ChatUsage
from orca_core.providers.fake import FakeProviderAdapter
from orca_core.schema.policy import Policy
from orca_core.schema.run import ConversationTurn

from ._m4_helpers import MockTool, make_profile, make_role

pytestmark = pytest.mark.asyncio


def _planner_response(args: dict) -> ChatResponse:
    return ChatResponse(
        model="fake-model",
        message=ChatMessage(
            role="assistant",
            content="",
            tool_calls=[ChatToolCall(id="c1", name="submit_workflow", arguments=args)],
        ),
        finish_reason="tool_calls",
        usage=ChatUsage(),
    )


GOOD_YAML = """version: 1
name: planner-test
nodes:
  - id: a
    role: worker
    position: { x: 0, y: 0 }
edges: []
entrypoint: a
"""


async def test_planner_success_first_try():
    fake = FakeProviderAdapter()
    fake.enqueue(
        _planner_response(
            {
                "intent": "test",
                "reasoning": "ok",
                "workflow_yaml": GOOD_YAML,
                "expected_effects": [],
                "confidence": "high",
                "questions": [],
            }
        )
    )
    profile = make_profile(is_planner=True)
    planner = Planner(adapter=fake, profile=profile)
    roles = {"worker": make_role("worker", tools=[])}
    tools = {"fs.read_file": MockTool()}
    policy = Policy(name="ask", mode="ask", rules=[])

    out = await planner.plan(
        ConversationTurn(session_id="s1", user_text="hello"),
        roles=roles,
        tools=tools,
        policy=policy,
    )
    assert out.intent == "test"
    assert "planner-test" in out.workflow_yaml


async def test_planner_retries_after_invalid_yaml():
    fake = FakeProviderAdapter()
    # First: bad YAML
    fake.enqueue(
        _planner_response(
            {
                "intent": "x",
                "reasoning": "x",
                "workflow_yaml": "not: [valid: yaml: at all",
                "expected_effects": [],
                "confidence": "low",
                "questions": [],
            }
        )
    )
    # Second: good YAML
    fake.enqueue(
        _planner_response(
            {
                "intent": "x",
                "reasoning": "x",
                "workflow_yaml": GOOD_YAML,
                "expected_effects": [],
                "confidence": "low",
                "questions": [],
            }
        )
    )
    profile = make_profile(is_planner=True)
    planner = Planner(adapter=fake, profile=profile)
    roles = {"worker": make_role("worker", tools=[])}
    tools = {"fs.read_file": MockTool()}
    policy = Policy(name="ask", mode="ask", rules=[])

    out = await planner.plan(
        ConversationTurn(session_id="s1", user_text="hello"),
        roles=roles,
        tools=tools,
        policy=policy,
    )
    assert out.intent == "x"


async def test_planner_fails_after_two_attempts():
    fake = FakeProviderAdapter()
    bad = _planner_response(
        {
            "intent": "x",
            "reasoning": "x",
            "workflow_yaml": "garbage: [",
            "expected_effects": [],
            "confidence": "low",
            "questions": [],
        }
    )
    fake.enqueue(bad)
    fake.enqueue(bad)
    profile = make_profile(is_planner=True)
    planner = Planner(adapter=fake, profile=profile)
    with pytest.raises(PlannerError):
        await planner.plan(
            ConversationTurn(session_id="s1", user_text="hi"),
            roles={"worker": make_role("worker")},
            tools={},
            policy=Policy(name="ask", mode="ask", rules=[]),
        )


async def test_planner_text_json_fallback():
    """Provider doesn't use tool call — JSON content fallback."""
    fake = FakeProviderAdapter()
    import json

    payload = {
        "intent": "x",
        "reasoning": "x",
        "workflow_yaml": GOOD_YAML,
        "expected_effects": [],
        "confidence": "medium",
        "questions": [],
    }
    fake.enqueue(
        ChatResponse(
            model="fake-model",
            message=ChatMessage(role="assistant", content=json.dumps(payload)),
            finish_reason="stop",
            usage=ChatUsage(),
        )
    )
    profile = make_profile(is_planner=True)
    profile = profile.model_copy(update={"is_tool_capable": False})
    planner = Planner(adapter=fake, profile=profile)
    out = await planner.plan(
        ConversationTurn(session_id="s1", user_text="hi"),
        roles={"worker": make_role("worker")},
        tools={},
        policy=Policy(name="ask", mode="ask", rules=[]),
    )
    assert out.intent == "x"


async def test_planner_text_json_block_extraction():
    """Provider returns text with JSON inside braces."""
    fake = FakeProviderAdapter()
    import json

    payload = {
        "intent": "x",
        "reasoning": "x",
        "workflow_yaml": GOOD_YAML,
        "expected_effects": [],
        "confidence": "medium",
        "questions": [],
    }
    text = "Here is your plan: " + json.dumps(payload) + " end."
    fake.enqueue(
        ChatResponse(
            model="fake-model",
            message=ChatMessage(role="assistant", content=text),
            finish_reason="stop",
            usage=ChatUsage(),
        )
    )
    profile = make_profile(is_planner=True).model_copy(update={"is_tool_capable": False})
    planner = Planner(adapter=fake, profile=profile)
    out = await planner.plan(
        ConversationTurn(session_id="s1", user_text="hi"),
        roles={"worker": make_role("worker")},
        tools={},
        policy=Policy(name="ask", mode="ask", rules=[]),
    )
    assert out.intent == "x"


async def test_planner_expected_effects_from_policy():
    """Static policy check should populate expected_effects.

    H10: expected_effects are scoped to the tools *actually referenced* by
    the roles the workflow uses. A role must list the tool in `role.tools`
    for it to appear in the summary.
    """
    fake = FakeProviderAdapter()
    fake.enqueue(
        _planner_response(
            {
                "intent": "x",
                "reasoning": "x",
                "workflow_yaml": GOOD_YAML,
                "expected_effects": [],
                "confidence": "low",
                "questions": [],
            }
        )
    )
    profile = make_profile(is_planner=True)
    planner = Planner(adapter=fake, profile=profile)
    from orca_core.schema.policy import PolicyRule

    policy = Policy(
        name="strict",
        mode="strict",
        rules=[PolicyRule(priority=10, scope="tool_id", matcher="fs.read_file", effect="ask")],
    )
    tools = {"fs.read_file": MockTool()}
    out = await planner.plan(
        ConversationTurn(session_id="s1", user_text="hi"),
        roles={"worker": make_role("worker", tools=["fs.read_file"])},
        tools=tools,
        policy=policy,
    )
    # The expected_effects should mention the ask requirement
    assert any("approval" in e or "fs.read_file" in e for e in out.expected_effects)


async def test_planner_failure_includes_stage_and_raw_preview():
    """H8: PlannerError details include stage + raw_preview + attempts."""
    fake = FakeProviderAdapter()
    # Two identical bad responses: JSON-in-content fails both times.
    bad_resp = ChatResponse(
        model="fake-model",
        message=ChatMessage(role="assistant", content="not json at all"),
        finish_reason="stop",
        usage=ChatUsage(),
    )
    fake.enqueue(bad_resp)
    fake.enqueue(bad_resp)
    profile = make_profile(is_planner=True).model_copy(update={"is_tool_capable": False})
    planner = Planner(adapter=fake, profile=profile)
    with pytest.raises(PlannerError) as excinfo:
        await planner.plan(
            ConversationTurn(session_id="s1", user_text="hi"),
            roles={"worker": make_role("worker")},
            tools={},
            policy=Policy(name="ask", mode="ask", rules=[]),
        )
    details = excinfo.value.details
    assert details.get("stage") == "content_json"
    assert "not json at all" in (details.get("raw_preview") or "")
    assert details.get("attempts") == 2


async def test_planner_error_preserves_cause_chain():
    """H11: PlannerError.__cause__ must point at the last internal exception."""
    fake = FakeProviderAdapter()
    bad = _planner_response(
        {
            "intent": "x",
            "reasoning": "x",
            "workflow_yaml": "this: [is: invalid: yaml:",
            "expected_effects": [],
            "confidence": "low",
            "questions": [],
        }
    )
    fake.enqueue(bad)
    fake.enqueue(bad)
    profile = make_profile(is_planner=True)
    planner = Planner(adapter=fake, profile=profile)
    with pytest.raises(PlannerError) as excinfo:
        await planner.plan(
            ConversationTurn(session_id="s1", user_text="hi"),
            roles={"worker": make_role("worker")},
            tools={},
            policy=Policy(name="ask", mode="ask", rules=[]),
        )
    assert excinfo.value.__cause__ is not None


async def test_expected_effects_scoped_to_workflow_tools():
    """H10: tools not referenced by any workflow role must NOT appear in
    expected_effects, even if they live in the global tool registry."""
    fake = FakeProviderAdapter()
    fake.enqueue(
        _planner_response(
            {
                "intent": "x",
                "reasoning": "x",
                "workflow_yaml": GOOD_YAML,
                "expected_effects": [],
                "confidence": "low",
                "questions": [],
            }
        )
    )
    profile = make_profile(is_planner=True)
    planner = Planner(adapter=fake, profile=profile)
    # Two registry tools but worker role only references the first.
    tools = {
        "fs.read_file": MockTool(id="fs.read_file"),
        "fs.destructive": MockTool(id="fs.destructive", side_effect="destructive"),
    }
    out = await planner.plan(
        ConversationTurn(session_id="s1", user_text="hi"),
        roles={"worker": make_role("worker", tools=["fs.read_file"])},
        tools=tools,
        policy=Policy(name="trusted", mode="trusted", rules=[]),
    )
    joined = " | ".join(out.expected_effects)
    # fs.destructive is out of scope → must not surface.
    assert "fs.destructive" not in joined


async def test_planner_unknown_role_reference():
    fake = FakeProviderAdapter()
    yaml_with_bad_role = GOOD_YAML.replace("role: worker", "role: nonexistent")
    bad_resp = _planner_response(
        {
            "intent": "x",
            "reasoning": "x",
            "workflow_yaml": yaml_with_bad_role,
            "expected_effects": [],
            "confidence": "low",
            "questions": [],
        }
    )
    fake.enqueue(bad_resp)
    fake.enqueue(bad_resp)
    profile = make_profile(is_planner=True)
    planner = Planner(adapter=fake, profile=profile)
    with pytest.raises(PlannerError):
        await planner.plan(
            ConversationTurn(session_id="s1", user_text="hi"),
            roles={"worker": make_role("worker")},
            tools={},
            policy=Policy(name="ask", mode="ask", rules=[]),
        )
