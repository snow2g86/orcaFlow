"""EventBus — Run 당 pub/sub + Last-Event-ID 재연결 버퍼.

design.md §4.3 SSE 스트림 요구:
- 이벤트는 `run_id` 로 격리된 큐에 emit.
- 5분 / 500개 버퍼에서 `Last-Event-ID` 이후 이벤트 재전송.
- 15초 keep-alive 는 SSE 계층(`ipc/sse.py`)이 담당.

H5 (M4 review):
- 구독자 큐 bounded (기본 1024). 느린 구독자는 드롭 + 경고 로그.
- 한 구독자 실패가 emit 자체를 블록하면 안 됨 (per-subscriber try/except).
- 버퍼 overflow 기록. 재연결 시 `last_event_id < overflow_from` 이면
  synthetic `run.gap` 이벤트 (payload=dropped_from/dropped_to) 를 replay 첫
  이벤트로 주입한다.
- `close_run` 경로에서 버퍼도 같이 clear 옵션.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from collections.abc import AsyncIterator
import contextlib
from datetime import datetime
import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..schema._base import utc_now

__all__ = ["EventBus", "RunEvent"]


_BUFFER_SIZE = 500
_SUBSCRIBER_QUEUE_SIZE = 1024
_MIN_BUFFER_FOR_OVERFLOW = 2

_LOGGER = logging.getLogger("orca_core.orchestrator.events")


class RunEvent(BaseModel):
    """단일 Run 이벤트 (SSE 프레임 직전 표현)."""

    model_config = ConfigDict(extra="forbid")

    id: int = Field(..., ge=1)
    run_id: str
    event: str
    payload: dict[str, Any] = Field(default_factory=dict)
    at: datetime = Field(default_factory=utc_now)


class EventBus:
    """Run 단위 pub/sub.

    - `emit(run_id, event, payload)` : 새 이벤트 발행. 모든 활성 구독자에게
      배포하고 replay 버퍼에 저장. 느린 구독자는 드롭한다.
    - `subscribe(run_id, last_event_id=None)` : async generator. 버퍼에서
      `last_event_id` 이후 replay 후 실시간 수신. last_event_id 가
      버퍼에서 증발한 구간보다 작으면 첫 이벤트로 `run.gap` 을 방출한다.
    - `close_run(run_id)` : 해당 Run 의 구독자 모두에게 None sentinel 을
      배포해 loop 를 종료시킨다 (GC 용도).
    - `clear(run_id)` : retention 정책이 run 을 제거할 때 호출.
    """

    def __init__(
        self,
        *,
        buffer_size: int = _BUFFER_SIZE,
        subscriber_queue_size: int = _SUBSCRIBER_QUEUE_SIZE,
    ) -> None:
        self._buffer_size = buffer_size
        self._subscriber_queue_size = subscriber_queue_size
        self._buffers: dict[str, deque[RunEvent]] = defaultdict(lambda: deque(maxlen=buffer_size))
        self._subscribers: dict[str, list[asyncio.Queue[RunEvent | None]]] = defaultdict(list)
        self._next_id: dict[str, int] = defaultdict(int)
        self._closed_runs: set[str] = set()
        # run_id -> first live id still in buffer; if last_event_id < overflow_from,
        # we have lost events.
        self._overflow_from: dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def emit(self, run_id: str, event: str, payload: dict[str, Any]) -> RunEvent:
        async with self._lock:
            self._next_id[run_id] += 1
            ev = RunEvent(
                id=self._next_id[run_id],
                run_id=run_id,
                event=event,
                payload=dict(payload),
            )
            buffer = self._buffers[run_id]
            # Detect overflow: buffer at maxlen before append -> oldest will drop.
            if buffer.maxlen is not None and len(buffer) == buffer.maxlen:
                # After append, oldest id will be dropped. The new oldest id =
                # the id that was second-oldest, i.e. buffer[1].id. Compute BEFORE
                # append.
                new_oldest_after = (
                    buffer[1].id if len(buffer) >= _MIN_BUFFER_FOR_OVERFLOW else ev.id
                )
                self._overflow_from[run_id] = new_oldest_after
            buffer.append(ev)
            if run_id not in self._overflow_from and buffer:
                self._overflow_from[run_id] = buffer[0].id
            queues = list(self._subscribers.get(run_id, ()))
            slow_to_drop: list[asyncio.Queue[RunEvent | None]] = []
        # per-subscriber dispatch — slow consumer never blocks emit.
        for q in queues:
            try:
                q.put_nowait(ev)
            except asyncio.QueueFull:
                slow_to_drop.append(q)
                _LOGGER.warning(
                    "sse.subscriber_dropped_slow",
                    extra={
                        "event": "sse.subscriber_dropped_slow",
                        "run_id": run_id,
                        "event_id": ev.id,
                    },
                )
            except Exception:  # pragma: no cover - defensive isolation
                slow_to_drop.append(q)
                _LOGGER.exception(
                    "sse.subscriber_put_failed",
                    extra={"event": "sse.subscriber_put_failed", "run_id": run_id},
                )
        if slow_to_drop:
            async with self._lock:
                listeners = self._subscribers.get(run_id, [])
                for q in slow_to_drop:
                    if q in listeners:
                        listeners.remove(q)
                    # Signal termination so the reader exits its loop cleanly.
                    with contextlib.suppress(Exception):  # pragma: no cover
                        q.put_nowait(None)
        return ev

    async def subscribe(
        self,
        run_id: str,
        *,
        last_event_id: int | None = None,
    ) -> AsyncIterator[RunEvent]:
        queue: asyncio.Queue[RunEvent | None] = asyncio.Queue(maxsize=self._subscriber_queue_size)
        async with self._lock:
            buffered = list(self._buffers.get(run_id, ()))
            already_closed = run_id in self._closed_runs
            overflow_from = self._overflow_from.get(run_id)
            if not already_closed:
                self._subscribers[run_id].append(queue)

        try:
            # H5: If the client reconnects with a last_event_id older than the
            # oldest event remaining in the buffer, we have lost events. Emit a
            # synthetic `run.gap` frame first so the client can reconcile.
            if (
                last_event_id is not None
                and overflow_from is not None
                and last_event_id + 1 < overflow_from
            ):
                yield RunEvent(
                    id=overflow_from - 1 if overflow_from > 1 else 1,
                    run_id=run_id,
                    event="run.gap",
                    payload={
                        "dropped_from": last_event_id + 1,
                        "dropped_to": overflow_from - 1,
                    },
                )

            # Replay buffered events first (after last_event_id if given)
            for ev in buffered:
                if last_event_id is not None and ev.id <= last_event_id:
                    continue
                yield ev

            # If the run already finished before subscribe, terminate after replay.
            if already_closed:
                return

            # Then live events until the caller unsubscribes or run closes
            while True:
                item = await queue.get()
                if item is None:
                    return
                yield item
        finally:
            async with self._lock:
                listeners = self._subscribers.get(run_id, [])
                if queue in listeners:
                    listeners.remove(queue)
                if not listeners:
                    self._subscribers.pop(run_id, None)

    async def close_run(self, run_id: str, *, clear_buffer: bool = False) -> None:
        async with self._lock:
            queues = list(self._subscribers.get(run_id, ()))
            self._closed_runs.add(run_id)
            if clear_buffer:
                self._buffers.pop(run_id, None)
                self._next_id.pop(run_id, None)
                self._overflow_from.pop(run_id, None)
        for q in queues:
            try:
                q.put_nowait(None)
            except asyncio.QueueFull:  # pragma: no cover
                # Force delivery: overflow + drop old
                with contextlib.suppress(Exception):
                    q.get_nowait()
                with contextlib.suppress(Exception):
                    q.put_nowait(None)

    def snapshot(self, run_id: str) -> list[RunEvent]:
        return list(self._buffers.get(run_id, ()))

    def clear(self, run_id: str) -> None:
        self._buffers.pop(run_id, None)
        self._next_id.pop(run_id, None)
        self._closed_runs.discard(run_id)
        self._overflow_from.pop(run_id, None)
