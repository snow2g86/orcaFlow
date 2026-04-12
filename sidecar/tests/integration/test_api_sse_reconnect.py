"""SSE Last-Event-ID reconnect — verify replay of missed events."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from orca_core.ipc.sse import _format_event
from orca_core.orchestrator import EventBus, RunEvent

pytestmark = pytest.mark.asyncio


async def test_event_bus_replay_only_after_last_id():
    bus = EventBus()
    # Pre-populate buffer
    for i in range(5):
        await bus.emit("run-x", f"e{i}", {"i": i})
    # Close the run so subscribe terminates after replay
    await bus.close_run("run-x")

    seen: list = []
    async for ev in bus.subscribe("run-x", last_event_id=2):
        seen.append(ev)
        if len(seen) >= 10:
            break

    # IDs are 1-indexed, so events e0..e4 have ids 1..5; last_event_id=2 means
    # we get ids > 2 = 3,4,5 -> events e2,e3,e4.
    assert [e.event for e in seen] == ["e2", "e3", "e4"]
    assert [e.id for e in seen] == [3, 4, 5]


async def test_event_bus_subscribe_all_events_when_no_last_id():
    bus = EventBus()
    for i in range(3):
        await bus.emit("run-y", f"e{i}", {})
    await bus.close_run("run-y")

    seen = []
    async for ev in bus.subscribe("run-y"):
        seen.append(ev)
    assert len(seen) == 3
    # Use the asyncio import to keep linter happy
    _ = asyncio


async def test_sse_handles_datetime_payload():
    """H6: _format_event must tolerate datetime / non-JSON-native payloads
    via `json.dumps(default=str)`."""
    ev = RunEvent(
        id=1,
        run_id="r1",
        event="custom",
        payload={"at": datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)},
    )
    frame = _format_event(ev)
    decoded = frame.decode("utf-8")
    assert "2024-01-02" in decoded
    assert "event: custom" in decoded


def test_sse_accepts_query_token(app, app_services, fake_adapter):
    """H14: /runs/{id}/events accepts ?token=<TOKEN> as fallback for
    browser EventSource which cannot set custom headers."""
    from orca_core.providers._base import ChatMessage, ChatResponse, ChatUsage
    from orca_core.schema.agent import AgentRole

    app_services.roles["worker"] = AgentRole(
        name="worker",
        role_type="worker",
        system_prompt="x",
        tools=[],
        llm_profile_id="profile-1",
    )
    fake_adapter.enqueue(
        ChatResponse(
            model="fake-model",
            message=ChatMessage(role="assistant", content="done"),
            finish_reason="stop",
            usage=ChatUsage(),
        )
    )
    wf_yaml = (
        "version: 1\nname: q\nnodes:\n  - id: a\n    role: worker\n"
        "    position: { x: 0, y: 0 }\nedges: []\nentrypoint: a\n"
    )
    wf = app.post("/workflows", json={"yaml": wf_yaml}).json()
    run = app.post("/runs", json={"workflow_id": wf["id"]}).json()
    run_id = run["run_id"]

    # Make a request WITHOUT the x-orca-token header but WITH ?token=<TOKEN>
    # — the middleware should allow it for the SSE path only.
    unauth = {"x-orca-token": ""}
    with app.stream(
        "GET",
        f"/runs/{run_id}/events?token=test-token",
        headers=unauth,
    ) as resp:
        assert resp.status_code == 200


def test_sse_rejects_wrong_query_token(app, app_services, fake_adapter):
    """H14: wrong query token still returns 401."""
    from orca_core.providers._base import ChatMessage, ChatResponse, ChatUsage
    from orca_core.schema.agent import AgentRole

    app_services.roles["worker"] = AgentRole(
        name="worker",
        role_type="worker",
        system_prompt="x",
        tools=[],
        llm_profile_id="profile-1",
    )
    fake_adapter.enqueue(
        ChatResponse(
            model="fake-model",
            message=ChatMessage(role="assistant", content="done"),
            finish_reason="stop",
            usage=ChatUsage(),
        )
    )
    wf_yaml = (
        "version: 1\nname: q2\nnodes:\n  - id: a\n    role: worker\n"
        "    position: { x: 0, y: 0 }\nedges: []\nentrypoint: a\n"
    )
    wf = app.post("/workflows", json={"yaml": wf_yaml}).json()
    run = app.post("/runs", json={"workflow_id": wf["id"]}).json()
    run_id = run["run_id"]
    resp = app.get(
        f"/runs/{run_id}/events?token=wrong",
        headers={"x-orca-token": ""},
    )
    assert resp.status_code == 401


async def test_sse_producer_exception_logged_and_terminal_frame(caplog):
    """H6: a producer crash must be logged with `sse.producer_failed` and
    deliver a `stream.error` frame to the client."""
    import logging

    from orca_core.ipc.sse import _iter_events

    # Build a bus whose subscribe() raises unconditionally.
    class BoomBus:
        async def subscribe(self, run_id, *, last_event_id=None):
            raise RuntimeError("boom")
            yield  # pragma: no cover - make it a generator

    # Minimal Request stub that advertises is_disconnected()=False once then True.
    class FakeRequest:
        def __init__(self) -> None:
            self._count = 0

        async def is_disconnected(self) -> bool:
            self._count += 1
            return self._count > 5

    caplog.set_level(logging.ERROR, logger="orca_core.ipc.sse")
    frames: list[bytes] = []
    async for chunk in _iter_events(FakeRequest(), "r-err", BoomBus(), None):  # type: ignore[arg-type]
        frames.append(chunk)
        if any(b"stream.error" in f for f in frames):
            break
    combined = b"".join(frames)
    assert b"stream.error" in combined
    assert any("sse.producer_failed" in rec.message for rec in caplog.records)
