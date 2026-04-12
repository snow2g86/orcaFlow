"""Misc routes — providers / llm-profiles / tools."""

from __future__ import annotations

from orca_core.schema.llm import LLMProfile
from tests.unit._m4_helpers import MockTool


def test_list_providers(app):
    resp = app.get("/providers")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert any(p["id"] == "prov-1" for p in data)


def test_list_llm_profiles(app):
    resp = app.get("/llm-profiles")
    assert resp.status_code == 200
    data = resp.json()
    assert any(p["id"] == "profile-1" for p in data)


def test_upsert_llm_profile(app, app_services):
    new = LLMProfile(
        id="new-profile",
        name="new-profile",
        provider_id="prov-1",
        model="other-model",
    )
    body = new.model_dump(mode="json")
    resp = app.put("/llm-profiles/new-profile", json=body)
    assert resp.status_code == 200
    assert "new-profile" in app_services.llm_profiles


def test_list_tools(app, app_services):
    app_services.tool_registry.register(MockTool())
    resp = app.get("/tools")
    assert resp.status_code == 200
    data = resp.json()
    assert any(t["id"] == "fs.read_file" for t in data)


def test_upsert_policy(app, app_services):
    body = {
        "id": "ignored",
        "name": "custom",
        "mode": "trusted",
        "rules": [],
    }
    resp = app.put("/policies/p1", json=body)
    assert resp.status_code == 200
    # Path id wins
    assert "p1" in app_services.policies


def test_simulate_unknown_policy_returns_404(app):
    body = {"policy_id": "nope", "scenarios": []}
    resp = app.post("/policies/simulate", json=body)
    assert resp.status_code == 404


def test_chat_no_session_returns_404(app):
    resp = app.post("/chat/sessions/missing/turns", json={"user_text": "hi"})
    assert resp.status_code == 404


def test_decide_unknown_approval_returns_404(app):
    resp = app.post("/approvals/missing/decide", json={"decision": "approve"})
    assert resp.status_code == 404


def test_get_unknown_run_returns_404(app):
    resp = app.get("/runs/missing")
    assert resp.status_code == 404


def test_cancel_unknown_run_returns_404(app):
    resp = app.post("/runs/missing/cancel")
    assert resp.status_code == 404


def test_sse_unknown_run_returns_404(app):
    resp = app.get("/runs/missing/events")
    assert resp.status_code == 404


def test_run_with_override_policy(app, app_services, fake_adapter):
    from orca_core.providers._base import ChatMessage, ChatResponse, ChatUsage
    from orca_core.schema.agent import AgentRole
    from orca_core.schema.policy import Policy

    fake_adapter.enqueue(
        ChatResponse(
            model="fake-model",
            message=ChatMessage(role="assistant", content="done"),
            finish_reason="stop",
            usage=ChatUsage(),
        )
    )
    app_services.roles["worker"] = AgentRole(
        name="worker",
        role_type="worker",
        system_prompt="be helpful",
        tools=[],
        llm_profile_id="profile-1",
    )
    other_policy = Policy(name="other-trusted", mode="trusted", rules=[])
    app_services.policies[other_policy.id] = other_policy

    yaml_text = """version: 1
name: o
nodes:
  - id: a
    role: worker
    position: { x: 0, y: 0 }
edges: []
entrypoint: a
"""
    wf = app.post("/workflows", json={"yaml": yaml_text}).json()
    run = app.post("/runs", json={"workflow_id": wf["id"], "override_policy_id": other_policy.id})
    assert run.status_code == 202
