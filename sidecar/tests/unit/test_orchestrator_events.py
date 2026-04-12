"""EventBus pub/sub + Last-Event-ID 재연결 테스트."""

from __future__ import annotations

import asyncio

import pytest

from orca_core.orchestrator import EventBus

pytestmark = pytest.mark.asyncio


async def test_emit_and_subscribe_returns_event():
    bus = EventBus()
    received: list = []

    async def consume() -> None:
        async for ev in bus.subscribe("run-1"):
            received.append(ev)
            if len(received) == 1:
                return

    consumer = asyncio.create_task(consume())
    await asyncio.sleep(0.01)
    await bus.emit("run-1", "run.started", {"x": 1})
    await asyncio.wait_for(consumer, timeout=1.0)
    assert received[0].event == "run.started"
    assert received[0].id == 1


async def test_replay_from_buffer_after_initial_emit():
    bus = EventBus()
    await bus.emit("run-1", "a", {"i": 1})
    await bus.emit("run-1", "b", {"i": 2})

    received = []
    sub_iter = bus.subscribe("run-1")
    received.append(await sub_iter.__anext__())
    received.append(await sub_iter.__anext__())
    await sub_iter.aclose()

    assert [r.event for r in received] == ["a", "b"]
    assert [r.id for r in received] == [1, 2]


async def test_last_event_id_skips_old_events():
    bus = EventBus()
    await bus.emit("run-1", "a", {})
    await bus.emit("run-1", "b", {})
    await bus.emit("run-1", "c", {})

    sub_iter = bus.subscribe("run-1", last_event_id=1)
    first = await sub_iter.__anext__()
    second = await sub_iter.__anext__()
    await sub_iter.aclose()
    assert first.event == "b"
    assert second.event == "c"


async def test_close_run_terminates_subscribers():
    bus = EventBus()
    received: list = []

    async def consume() -> None:
        async for ev in bus.subscribe("run-1"):
            received.append(ev)

    consumer = asyncio.create_task(consume())
    await asyncio.sleep(0.01)
    await bus.emit("run-1", "ev", {})
    await asyncio.sleep(0.01)
    await bus.close_run("run-1")
    await asyncio.wait_for(consumer, timeout=1.0)
    assert len(received) == 1


async def test_buffer_max_size():
    bus = EventBus(buffer_size=3)
    for i in range(5):
        await bus.emit("run-1", f"e{i}", {"i": i})
    snap = bus.snapshot("run-1")
    assert len(snap) == 3
    assert snap[0].event == "e2"
    assert snap[-1].event == "e4"


async def test_slow_subscriber_dropped_without_blocking_emit():
    """H5: a slow subscriber with a full queue is dropped; emit must not block
    nor fail for other subscribers."""
    bus = EventBus(subscriber_queue_size=2)

    # Manually install both a 'slow' and a 'healthy' subscriber queue.
    slow: asyncio.Queue = asyncio.Queue(maxsize=2)
    healthy: asyncio.Queue = asyncio.Queue(maxsize=1024)
    async with bus._lock:
        bus._subscribers["run-slow"].append(slow)
        bus._subscribers["run-slow"].append(healthy)

    # Saturate the slow queue so the first put_nowait raises QueueFull.
    slow.put_nowait(None)  # type: ignore[arg-type]
    slow.put_nowait(None)  # type: ignore[arg-type]

    # Emit three events — none should block; slow subscriber is dropped.
    await bus.emit("run-slow", "e1", {})
    await bus.emit("run-slow", "e2", {})
    await bus.emit("run-slow", "e3", {})

    received: list = []
    for _ in range(3):
        ev = await asyncio.wait_for(healthy.get(), timeout=1.0)
        received.append(ev.event)

    assert received == ["e1", "e2", "e3"]
    async with bus._lock:
        assert slow not in bus._subscribers.get("run-slow", [])
        assert healthy in bus._subscribers.get("run-slow", [])


async def test_event_bus_emits_run_gap_on_overflow_reconnect():
    """H5 + M2: reconnecting with a last_event_id older than the oldest
    buffered event yields a synthetic `run.gap` marker first."""
    bus = EventBus(buffer_size=3)
    for i in range(10):
        await bus.emit("run-g", f"e{i}", {"i": i})
    await bus.close_run("run-g")

    # IDs 1..10. Buffer of size 3 keeps ids 8,9,10. Reconnect asking for
    # events after id=2 → missing events 3..7, overflow_from = 8.
    seen = []
    async for ev in bus.subscribe("run-g", last_event_id=2):
        seen.append(ev)

    assert seen[0].event == "run.gap"
    assert seen[0].payload == {"dropped_from": 3, "dropped_to": 7}
    assert [e.event for e in seen[1:]] == ["e7", "e8", "e9"]


async def test_multiple_subscribers_independent():
    bus = EventBus()

    async def consumer(name: str, target: list) -> None:
        async for ev in bus.subscribe("run-1"):
            target.append(ev.event)
            if len(target) >= 2:
                return

    a: list = []
    b: list = []
    t1 = asyncio.create_task(consumer("a", a))
    t2 = asyncio.create_task(consumer("b", b))
    await asyncio.sleep(0.01)
    await bus.emit("run-1", "x", {})
    await bus.emit("run-1", "y", {})
    await asyncio.wait_for(asyncio.gather(t1, t2), timeout=1.0)
    assert a == ["x", "y"]
    assert b == ["x", "y"]
