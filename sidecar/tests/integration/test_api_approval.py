"""ask -> approval.requested -> POST /approvals/{id}/decide -> resume."""

from __future__ import annotations

import time

from orca_core.providers._base import (
    ChatMessage,
    ChatResponse,
    ChatToolCall,
    ChatUsage,
)
from orca_core.schema.agent import AgentRole
from orca_core.schema.policy import Policy, PolicyRule
from tests.unit._m4_helpers import MockTool

WORKFLOW_YAML = """version: 1
name: with-tool
nodes:
  - id: a
    role: worker
    position: { x: 0, y: 0 }
edges: []
entrypoint: a
"""


def _enqueue_tool_call(adapter, tool_id: str, args: dict) -> None:
    adapter.enqueue(
        ChatResponse(
            model="fake-model",
            message=ChatMessage(
                role="assistant",
                content="",
                tool_calls=[ChatToolCall(id="c1", name=tool_id, arguments=args)],
            ),
            finish_reason="tool_calls",
            usage=ChatUsage(),
        )
    )


def test_full_approval_flow(app, app_services, fake_adapter):
    # Configure ask policy + a write tool
    policy = Policy(
        name="ask",
        mode="ask",
        rules=[
            PolicyRule(priority=10, scope="tool_id", matcher="fs.read_file", effect="ask"),
        ],
    )
    app_services.policies = {policy.id: policy}
    app_services.default_policy_id = policy.id

    tool = MockTool(id="fs.read_file", side_effect="write")
    app_services.tool_registry.register(tool)
    app_services.roles["worker"] = AgentRole(
        name="worker",
        role_type="worker",
        system_prompt="be helpful",
        tools=["fs.read_file"],
        llm_profile_id="profile-1",
    )

    _enqueue_tool_call(fake_adapter, "fs.read_file", {"path": "/x"})
    wf = app.post("/workflows", json={"yaml": WORKFLOW_YAML}).json()
    run = app.post("/runs", json={"workflow_id": wf["id"]}).json()
    run_id = run["run_id"]

    # Wait for approval.requested
    approval_id = None
    deadline = time.time() + 2.0
    while time.time() < deadline and approval_id is None:
        pending = app.get("/approvals/pending").json()
        if pending:
            approval_id = pending[0]["id"]
            break
        time.sleep(0.02)
    assert approval_id is not None

    # Approve
    decide = app.post(f"/approvals/{approval_id}/decide", json={"decision": "approve"})
    assert decide.status_code == 200
    assert decide.json()["state"] == "approved"

    # Wait for run.succeeded
    deadline = time.time() + 2.0
    final = None
    while time.time() < deadline:
        snap = app.get(f"/runs/{run_id}").json()
        if snap["status"] in ("succeeded", "failed"):
            final = snap
            break
        time.sleep(0.02)
    assert final is not None
    assert final["status"] == "succeeded"
    assert tool.invocations == [{"path": "/x"}]


def test_decide_already_approved_returns_409(app, app_services, fake_adapter):
    """H13: a second decision on an approved/rejected approval returns 409."""
    policy = Policy(
        name="ask",
        mode="ask",
        rules=[
            PolicyRule(priority=10, scope="tool_id", matcher="fs.read_file", effect="ask"),
        ],
    )
    app_services.policies = {policy.id: policy}
    app_services.default_policy_id = policy.id

    tool = MockTool(id="fs.read_file", side_effect="write")
    app_services.tool_registry.register(tool)
    app_services.roles["worker"] = AgentRole(
        name="worker",
        role_type="worker",
        system_prompt="be helpful",
        tools=["fs.read_file"],
        llm_profile_id="profile-1",
    )

    _enqueue_tool_call(fake_adapter, "fs.read_file", {"path": "/x"})
    wf = app.post("/workflows", json={"yaml": WORKFLOW_YAML}).json()
    run = app.post("/runs", json={"workflow_id": wf["id"]}).json()
    run_id = run["run_id"]

    # Wait for approval.requested
    deadline = time.time() + 2.0
    approval_id = None
    while time.time() < deadline and approval_id is None:
        pending = app.get("/approvals/pending").json()
        if pending:
            approval_id = pending[0]["id"]
            break
        time.sleep(0.02)
    assert approval_id is not None

    # First decision succeeds
    first = app.post(f"/approvals/{approval_id}/decide", json={"decision": "approve"})
    assert first.status_code == 200

    # Wait for the run to resume to a terminal state so subsequent requests
    # see a stable approval state.
    deadline = time.time() + 2.0
    while time.time() < deadline:
        snap = app.get(f"/runs/{run_id}").json()
        if snap["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.02)

    # Second decision on the same approval must 409.
    second = app.post(f"/approvals/{approval_id}/decide", json={"decision": "reject"})
    assert second.status_code == 409
    body = second.json()
    assert body["detail"]["error"]["code"] == "approval.already_decided"


def test_approval_reject_fails_run(app, app_services, fake_adapter):
    policy = Policy(
        name="ask",
        mode="ask",
        rules=[
            PolicyRule(priority=10, scope="tool_id", matcher="fs.read_file", effect="ask"),
        ],
    )
    app_services.policies = {policy.id: policy}
    app_services.default_policy_id = policy.id

    tool = MockTool(id="fs.read_file", side_effect="write")
    app_services.tool_registry.register(tool)
    app_services.roles["worker"] = AgentRole(
        name="worker",
        role_type="worker",
        system_prompt="be helpful",
        tools=["fs.read_file"],
        llm_profile_id="profile-1",
    )

    _enqueue_tool_call(fake_adapter, "fs.read_file", {"path": "/x"})
    wf = app.post("/workflows", json={"yaml": WORKFLOW_YAML}).json()
    run = app.post("/runs", json={"workflow_id": wf["id"]}).json()
    run_id = run["run_id"]

    deadline = time.time() + 2.0
    approval_id = None
    while time.time() < deadline and approval_id is None:
        pending = app.get("/approvals/pending").json()
        if pending:
            approval_id = pending[0]["id"]
            break
        time.sleep(0.02)
    assert approval_id is not None

    app.post(f"/approvals/{approval_id}/decide", json={"decision": "reject"})

    deadline = time.time() + 2.0
    final = None
    while time.time() < deadline:
        snap = app.get(f"/runs/{run_id}").json()
        if snap["status"] in ("succeeded", "failed"):
            final = snap
            break
        time.sleep(0.02)
    assert final is not None
    assert final["status"] == "failed"
    assert tool.invocations == []
