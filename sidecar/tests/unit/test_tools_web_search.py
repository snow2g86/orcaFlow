"""web.search 툴 테스트."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from orca_core.schema import Policy
from orca_core.tools import InMemoryEventEmitter, ToolRuntime
from orca_core.tools.web import WebSearchTool

from ._m3_helpers import InMemoryTransactionFactory, make_audit_log_path, make_journal_base


@pytest.fixture
def runtime(tmp_path: Path) -> tuple[ToolRuntime, InMemoryTransactionFactory]:
    factory = InMemoryTransactionFactory()
    rt = ToolRuntime(
        transaction_factory=factory,
        audit_log_path=make_audit_log_path(tmp_path),
        journal_base_dir=make_journal_base(tmp_path),
        events=InMemoryEventEmitter(),
    )
    return rt, factory


_DDG_RESPONSE = {
    "Abstract": "Python is a programming language.",
    "AbstractSource": "Wikipedia",
    "AbstractURL": "https://en.wikipedia.org/wiki/Python",
    "RelatedTopics": [
        {"Text": "Python (programming language)", "FirstURL": "https://duckduckgo.com/Python"},
        {"Text": "CPython", "FirstURL": "https://duckduckgo.com/CPython"},
    ],
}


def _make_mock_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_DDG_RESPONSE)

    return httpx.MockTransport(handler)


def _make_mock_client_factory(transport: httpx.MockTransport):
    class MockAsyncClient(httpx.AsyncClient):
        def __init__(self, **kwargs):
            super().__init__(transport=transport, **kwargs)

    return MockAsyncClient


async def test_dry_run(tmp_path: Path, runtime):
    rt, _ = runtime
    result = await rt.invoke(
        WebSearchTool(),
        args={"query": "Python programming"},
        policy=Policy(name="t", mode="trusted"),
        run_id="r1",
        run_step_id="s1",
        dry_run=True,
    )
    assert result.outcome == "dry_run"
    assert result.result.output["query"] == "Python programming"


async def test_search_with_mock(tmp_path: Path, runtime):
    rt, _ = runtime
    transport = _make_mock_transport()
    tool = WebSearchTool()
    tool._client_factory = _make_mock_client_factory(transport)

    result = await rt.invoke(
        tool,
        args={"query": "Python"},
        policy=Policy(name="t", mode="trusted"),
        run_id="r1",
        run_step_id="s1",
    )
    assert result.outcome == "succeeded"
    out = result.result.output
    assert out["abstract"] == "Python is a programming language."
    assert out["source"] == "Wikipedia"
    assert len(out["results"]) == 2
    assert out["results"][0]["text"] == "Python (programming language)"


async def test_search_error(tmp_path: Path, runtime):
    rt, _ = runtime

    def error_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("DNS lookup failed")

    transport = httpx.MockTransport(error_handler)
    tool = WebSearchTool()
    tool._client_factory = _make_mock_client_factory(transport)

    result = await rt.invoke(
        tool,
        args={"query": "test"},
        policy=Policy(name="t", mode="trusted"),
        run_id="r1",
        run_step_id="s1",
    )
    assert result.outcome == "failed"
