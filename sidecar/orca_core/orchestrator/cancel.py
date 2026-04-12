"""RunCancellation — asyncio.Event 래퍼 + 전역 레지스트리.

`ToolRuntime` 은 M3 에서 `CancelToken` 을 이미 받지만, Orchestrator 는
Run 레벨 취소도 필요하다. `RunCancellation.token` 이 바로 `CancelToken` 이므로
ToolRuntime 으로 그대로 넘겨줄 수 있다.
"""

from __future__ import annotations

import asyncio

from ..tools import CancelToken

__all__ = ["RunCancellation"]


class RunCancellation:
    """Run 단위 취소 신호.

    - `token` : M3 `CancelToken`. ToolRuntime 에 그대로 전달.
    - `cancel()` : run 전체 취소 요청. 이 이후 runner 루프는 다음 노드로
      진행하지 않고 Run.status = cancelled 로 정리한다.
    - `is_cancelled()` : 내부 상태 조회.
    """

    def __init__(self) -> None:
        self._event = asyncio.Event()
        self._token = CancelToken()

    @property
    def token(self) -> CancelToken:
        return self._token

    def cancel(self) -> None:
        self._event.set()
        self._token.cancel()

    def is_cancelled(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> None:
        await self._event.wait()
