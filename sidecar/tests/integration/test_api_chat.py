"""POST /chat/sessions + /chat/sessions/{id}/turns -> Planner."""

from __future__ import annotations

from orca_core.providers._base import (
    ChatMessage,
    ChatResponse,
    ChatToolCall,
    ChatUsage,
)
from orca_core.schema.agent import AgentRole

GOOD_YAML = """version: 1
name: planned
nodes:
  - id: a
    role: worker
    position: { x: 0, y: 0 }
edges: []
entrypoint: a
"""


def _planner_response(adapter, args: dict) -> None:
    adapter.enqueue(
        ChatResponse(
            model="fake-model",
            message=ChatMessage(
                role="assistant",
                content="",
                tool_calls=[ChatToolCall(id="c1", name="submit_workflow", arguments=args)],
            ),
            finish_reason="tool_calls",
            usage=ChatUsage(),
        )
    )


def test_chat_uses_same_synthetic_policy_as_runs(app_services):
    """H9: when no policy is configured, chat._default_policy() and
    runs.resolve_policy() must return the *same* synthetic fallback object.
    """
    from orca_core.ipc.dependencies import SYNTHETIC_FALLBACK_POLICY
    from orca_core.ipc.routes.chat import _default_policy
    from orca_core.schema.workflow import AgentNode, Position, Workflow

    # Purge policies to force the fallback branch
    app_services.policies = {}
    app_services.default_policy_id = None

    chat_policy = _default_policy(app_services)
    wf = Workflow(
        name="x",
        nodes=[AgentNode(id="a", role="worker", position=Position(x=0, y=0))],
        edges=[],
        entrypoint="a",
    )
    runs_policy = app_services.resolve_policy(wf)

    assert chat_policy is SYNTHETIC_FALLBACK_POLICY
    assert runs_policy is SYNTHETIC_FALLBACK_POLICY
    assert chat_policy.mode == "strict"


def test_chat_session_planner(app, app_services, fake_adapter):
    app_services.roles["worker"] = AgentRole(
        name="worker",
        role_type="worker",
        system_prompt="be helpful",
        tools=[],
        llm_profile_id="profile-1",
    )
    _planner_response(
        fake_adapter,
        {
            "intent": "summarize",
            "reasoning": "x",
            "workflow_yaml": GOOD_YAML,
            "expected_effects": [],
            "confidence": "high",
            "questions": [],
        },
    )
    session = app.post("/chat/sessions").json()
    sid = session["session_id"]
    out = app.post(f"/chat/sessions/{sid}/turns", json={"user_text": "do it"})
    assert out.status_code == 200
    body = out.json()
    assert body["intent"] == "summarize"
    assert "workflow_yaml" in body
