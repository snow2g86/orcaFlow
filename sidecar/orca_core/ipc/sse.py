"""FastAPI StreamingResponse 기반 SSE 구현.

design.md 4.3 의 SSE 스트림 요구를 외부 의존 추가 없이 자체 구현한다.
- 프레임 포맷: `event: <name>\\ndata: <json>\\nid: <seq>\\n\\n`
- keep-alive: 15 초마다 `: ping` 코멘트 라인.
- Last-Event-ID 헤더 -> EventBus.subscribe 의 last_event_id 인자로 전달.

H6 (M4 review):
- 생산자 task 예외는 `contextlib.suppress` 로 삼키지 않고 구조화 로그.
- 치명적 예외 발생 시 클라이언트에 `event: stream.error` 최종 프레임 1개 전송.
- `_format_event` 의 `json.dumps` 에 `default=str` 추가 — datetime 등 복잡
  페이로드가 UnicodeError/TypeError 를 던지지 않도록.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import contextlib
import json
import logging

from fastapi import Request
from fastapi.responses import StreamingResponse

from ..orchestrator import EventBus, RunEvent

__all__ = ["run_event_source"]


_KEEPALIVE_S = 15.0

_logger = logging.getLogger("orca_core.ipc.sse")


def _parse_last_event_id(request: Request) -> int | None:
    raw = request.headers.get("last-event-id") or request.headers.get("Last-Event-ID")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


async def _iter_events(
    request: Request,
    run_id: str,
    bus: EventBus,
    last_event_id: int | None,
) -> AsyncIterator[bytes]:
    # Initial comment frame so browsers know the stream is open
    yield b": stream open\n\n"
    queue: asyncio.Queue[RunEvent | None | _ProducerError] = asyncio.Queue()

    async def produce() -> None:
        try:
            async for ev in bus.subscribe(run_id, last_event_id=last_event_id):
                await queue.put(ev)
        except Exception as exc:
            _logger.exception(
                "sse.producer_failed",
                extra={"event": "sse.producer_failed", "run_id": run_id},
            )
            with contextlib.suppress(Exception):
                await queue.put(_ProducerError(str(exc)))
        finally:
            with contextlib.suppress(Exception):
                await queue.put(None)

    producer = asyncio.create_task(produce())
    try:
        while True:
            if await request.is_disconnected():
                return
            try:
                item = await asyncio.wait_for(queue.get(), timeout=_KEEPALIVE_S)
            except TimeoutError:
                yield b": ping\n\n"
                continue
            if item is None:
                return
            if isinstance(item, _ProducerError):
                # H6: surface a terminal stream.error frame and end the stream.
                yield _format_stream_error(item.message)
                return
            yield _format_event(item)
    finally:
        producer.cancel()
        # H6: do NOT swallow arbitrary exceptions here — only CancelledError.
        with contextlib.suppress(asyncio.CancelledError):
            try:
                await producer
            except Exception:  # pragma: no cover - already logged inside produce()
                _logger.exception(
                    "sse.producer_cleanup_failed",
                    extra={"event": "sse.producer_cleanup_failed", "run_id": run_id},
                )


class _ProducerError:
    __slots__ = ("message",)

    def __init__(self, message: str) -> None:
        self.message = message


def _format_event(ev: RunEvent) -> bytes:
    # H6: default=str so datetime / Decimal / UUID payloads don't explode.
    data = json.dumps(ev.payload, ensure_ascii=False, separators=(",", ":"), default=str)
    frame = f"id: {ev.id}\nevent: {ev.event}\ndata: {data}\n\n"
    return frame.encode("utf-8")


def _format_stream_error(message: str) -> bytes:
    data = json.dumps({"error": message}, ensure_ascii=False, separators=(",", ":"))
    frame = f"event: stream.error\ndata: {data}\n\n"
    return frame.encode("utf-8")


def run_event_source(request: Request, run_id: str, bus: EventBus) -> StreamingResponse:
    last_id = _parse_last_event_id(request)
    return StreamingResponse(
        _iter_events(request, run_id, bus, last_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
