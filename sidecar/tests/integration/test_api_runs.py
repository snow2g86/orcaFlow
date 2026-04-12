"""POST /runs + GET /runs/{id} + SSE /runs/{id}/events."""

from __future__ import annotations

import json
import time

from orca_core.providers._base import ChatMessage, ChatResponse, ChatUsage
from orca_core.schema.agent import AgentRole

WORKFLOW_YAML = """version: 1
name: linear
nodes:
  - id: a
    role: worker
    position: { x: 0, y: 0 }
edges: []
entrypoint: a
"""


def _enqueue_text(adapter, text: str) -> None:
    adapter.enqueue(
        ChatResponse(
            model="fake-model",
            message=ChatMessage(role="assistant", content=text),
            finish_reason="stop",
            usage=ChatUsage(),
        )
    )


def _seed_role(services, name="worker"):
    services.roles[name] = AgentRole(
        name=name,
        role_type="worker",
        system_prompt="be helpful",
        tools=[],
        llm_profile_id="profile-1",
    )


def test_start_run_returns_202(app, app_services, fake_adapter):
    _seed_role(app_services)
    _enqueue_text(fake_adapter, "done")
    wf = app.post("/workflows", json={"yaml": WORKFLOW_YAML}).json()
    run = app.post("/runs", json={"workflow_id": wf["id"]})
    assert run.status_code == 202
    body = run.json()
    assert "run_id" in body


def test_get_run_returns_snapshot_with_events(app, app_services, fake_adapter):
    _seed_role(app_services)
    _enqueue_text(fake_adapter, "done")
    wf = app.post("/workflows", json={"yaml": WORKFLOW_YAML}).json()
    run = app.post("/runs", json={"workflow_id": wf["id"]}).json()
    run_id = run["run_id"]

    # Wait for the background task to finish (poll up to 1s)
    deadline = time.time() + 2.0
    snapshot = None
    while time.time() < deadline:
        snapshot = app.get(f"/runs/{run_id}").json()
        if snapshot["status"] in ("succeeded", "failed", "cancelled"):
            break
        time.sleep(0.02)
    assert snapshot is not None
    assert snapshot["status"] == "succeeded"
    events = [e["event"] for e in snapshot["events"]]
    assert "run.started" in events
    assert "run.succeeded" in events


def test_sse_events_stream(app, app_services, fake_adapter):
    _seed_role(app_services)
    _enqueue_text(fake_adapter, "done")
    wf = app.post("/workflows", json={"yaml": WORKFLOW_YAML}).json()
    run = app.post("/runs", json={"workflow_id": wf["id"]}).json()
    run_id = run["run_id"]

    # Wait for run to finish first so all events are buffered
    deadline = time.time() + 2.0
    while time.time() < deadline:
        snap = app.get(f"/runs/{run_id}").json()
        if snap["status"] == "succeeded":
            break
        time.sleep(0.02)

    # Now subscribe to the event stream — it should replay all buffered
    # events and then close the run.
    seen: list[dict] = []
    with app.stream("GET", f"/runs/{run_id}/events") as resp:
        assert resp.status_code == 200
        # Collect frames until we see run.succeeded
        buf = ""
        for chunk in resp.iter_text():
            buf += chunk
            while "\n\n" in buf:
                frame, buf = buf.split("\n\n", 1)
                if not frame.strip() or frame.startswith(":"):
                    continue
                ev = _parse_frame(frame)
                if ev is not None:
                    seen.append(ev)
                    if ev.get("event") == "run.succeeded":
                        return
            if any(s.get("event") == "run.succeeded" for s in seen):
                return
    assert any(s.get("event") == "run.succeeded" for s in seen)


def test_run_task_crash_updates_snapshot_to_failed(app, app_services, fake_adapter, monkeypatch):
    """H3: if the runner task blows up before reaching a terminal state,
    the finalize callback must force-transition the snapshot to `failed`."""
    _seed_role(app_services)

    # Force GraphRunner.run to raise BEFORE emitting any event — simulates a
    # pre-loop crash in the task wrapper.
    from orca_core.orchestrator.runner import GraphRunner

    async def boom(self, ctx):
        raise RuntimeError("boom before loop")

    monkeypatch.setattr(GraphRunner, "run", boom)

    wf = app.post("/workflows", json={"yaml": WORKFLOW_YAML}).json()
    run = app.post("/runs", json={"workflow_id": wf["id"]}).json()
    run_id = run["run_id"]

    # Poll for terminal state — the done-callback flips snapshot to failed.
    deadline = time.time() + 2.0
    final = None
    while time.time() < deadline:
        snap = app.get(f"/runs/{run_id}").json()
        if snap["status"] in ("succeeded", "failed", "cancelled"):
            final = snap
            break
        time.sleep(0.02)
    assert final is not None
    assert final["status"] == "failed"
    assert final.get("error", {}).get("code") == "run.task_crashed"


def test_cancel_run_terminal_state_returns_409(app, app_services, fake_adapter):
    """H4: cancel after terminal state ⇒ 409 conflict."""
    _seed_role(app_services)
    _enqueue_text(fake_adapter, "done")
    wf = app.post("/workflows", json={"yaml": WORKFLOW_YAML}).json()
    run = app.post("/runs", json={"workflow_id": wf["id"]}).json()
    run_id = run["run_id"]

    # Wait until finished
    deadline = time.time() + 2.0
    while time.time() < deadline:
        snap = app.get(f"/runs/{run_id}").json()
        if snap["status"] == "succeeded":
            break
        time.sleep(0.02)

    resp = app.post(f"/runs/{run_id}/cancel")
    assert resp.status_code == 409
    body = resp.json()
    assert body["detail"]["error"]["code"] == "run.terminal"
    assert body["detail"]["error"]["details"]["status"] == "succeeded"


def test_run_retention_caps_services_runs(app, app_services, fake_adapter):
    """H12: services.runs is bounded by run_retention — oldest completed
    runs evict first. Buffer is cleared for evicted runs."""
    _seed_role(app_services)
    app_services.run_retention = 2

    ids: list[str] = []
    for _ in range(4):
        _enqueue_text(fake_adapter, "done")
        wf = app.post("/workflows", json={"yaml": WORKFLOW_YAML}).json()
        run = app.post("/runs", json={"workflow_id": wf["id"]}).json()
        ids.append(run["run_id"])
        # Wait until done so FIFO eviction is deterministic.
        deadline = time.time() + 2.0
        while time.time() < deadline:
            snap = app.get(f"/runs/{run['run_id']}").json()
            if snap["status"] == "succeeded":
                break
            time.sleep(0.02)

    # Only the 2 most recent should remain accessible.
    assert len(app_services.runs) == 2
    assert ids[-1] in app_services.runs
    assert ids[-2] in app_services.runs
    assert ids[0] not in app_services.runs


def _parse_frame(frame: str) -> dict | None:
    out: dict = {}
    for line in frame.splitlines():
        if line.startswith("event:"):
            out["event"] = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            try:
                out["data"] = json.loads(line.split(":", 1)[1].strip())
            except json.JSONDecodeError:
                out["data"] = {}
        elif line.startswith("id:"):
            out["id"] = int(line.split(":", 1)[1].strip())
    return out or None


def test_cancel_run(app, app_services, fake_adapter):
    _seed_role(app_services)
    _enqueue_text(fake_adapter, "done")
    wf = app.post("/workflows", json={"yaml": WORKFLOW_YAML}).json()
    run = app.post("/runs", json={"workflow_id": wf["id"]}).json()
    run_id = run["run_id"]

    # H4: if the task has already finished (fast path), cancel must return
    # 409 with a terminal error. Wait for terminal state explicitly so the
    # assertion is deterministic.
    deadline = time.time() + 2.0
    while time.time() < deadline:
        snap = app.get(f"/runs/{run_id}").json()
        if snap["status"] in ("succeeded", "failed", "cancelled"):
            break
        time.sleep(0.02)
    cancel = app.post(f"/runs/{run_id}/cancel")
    assert cancel.status_code == 409
    body = cancel.json()
    assert body["detail"]["error"]["code"] == "run.terminal"
