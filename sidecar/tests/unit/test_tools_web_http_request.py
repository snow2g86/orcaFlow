"""web.http_request 툴 테스트."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from orca_core.schema import Policy
from orca_core.tools import InMemoryEventEmitter, ToolRuntime
from orca_core.tools.web import WebHttpRequestTool
from orca_core.tools.web.http_request import _scrub_url

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


def _make_mock_transport(
    status_code: int = 200,
    json_body: dict | None = None,
    text_body: str = "",
) -> httpx.MockTransport:
    """httpx MockTransport factory."""

    def handler(request: httpx.Request) -> httpx.Response:
        if json_body is not None:
            return httpx.Response(status_code, json=json_body)
        return httpx.Response(status_code, text=text_body)

    return httpx.MockTransport(handler)


def _make_mock_client_factory(transport: httpx.MockTransport):
    """MockTransport 를 사용하는 AsyncClient factory."""

    class MockAsyncClient(httpx.AsyncClient):
        def __init__(self, **kwargs):
            super().__init__(transport=transport, **kwargs)

    return MockAsyncClient


# --- URL scrubbing ---


def test_scrub_url_removes_api_key():
    url = "https://example.com/api?api_key=secret123&q=hello"
    scrubbed = _scrub_url(url)
    assert "secret123" not in scrubbed
    assert "SCRUBBED" in scrubbed
    assert "q=hello" in scrubbed


def test_scrub_url_removes_token():
    url = "https://example.com?auth_token=xyz&page=1"
    scrubbed = _scrub_url(url)
    assert "xyz" not in scrubbed
    assert "page=1" in scrubbed


def test_scrub_url_no_query():
    url = "https://example.com/path"
    assert _scrub_url(url) == url


# --- Tool tests ---


async def test_dry_run(tmp_path: Path, runtime):
    rt, _ = runtime
    result = await rt.invoke(
        WebHttpRequestTool(),
        args={"method": "GET", "url": "https://example.com"},
        policy=Policy(name="t", mode="trusted"),
        run_id="r1",
        run_step_id="s1",
        dry_run=True,
    )
    assert result.outcome == "dry_run"
    assert result.result.output["method"] == "GET"


async def test_get_request_with_mock(tmp_path: Path, runtime):
    rt, _ = runtime
    transport = _make_mock_transport(status_code=200, text_body="Hello World")
    tool = WebHttpRequestTool()
    tool._client_factory = _make_mock_client_factory(transport)

    result = await rt.invoke(
        tool,
        args={"method": "GET", "url": "https://example.com/data"},
        policy=Policy(name="t", mode="trusted"),
        run_id="r1",
        run_step_id="s1",
    )
    assert result.outcome == "succeeded"
    assert result.result.output["status_code"] == 200
    assert result.result.output["body"] == "Hello World"


async def test_post_request_with_body(tmp_path: Path, runtime):
    rt, _ = runtime
    transport = _make_mock_transport(status_code=201, json_body={"id": 1})
    tool = WebHttpRequestTool()
    tool._client_factory = _make_mock_client_factory(transport)

    result = await rt.invoke(
        tool,
        args={
            "method": "POST",
            "url": "https://api.example.com/items",
            "headers": {"Content-Type": "application/json"},
            "body": '{"name": "test"}',
        },
        policy=Policy(name="t", mode="trusted"),
        run_id="r1",
        run_step_id="s1",
    )
    assert result.outcome == "succeeded"
    assert result.result.output["status_code"] == 201


async def test_response_truncation(tmp_path: Path, runtime):
    rt, _ = runtime
    large_body = "x" * 2_000_000
    transport = _make_mock_transport(status_code=200, text_body=large_body)
    tool = WebHttpRequestTool()
    tool._client_factory = _make_mock_client_factory(transport)
    tool.max_output_bytes = 1000

    result = await rt.invoke(
        tool,
        args={"method": "GET", "url": "https://example.com/large"},
        policy=Policy(name="t", mode="trusted"),
        run_id="r1",
        run_step_id="s1",
    )
    assert result.outcome == "succeeded"
    assert result.result.output["truncated"] is True
    assert len(result.result.output["body"]) == 1000


async def test_network_error_fails(tmp_path: Path, runtime):
    rt, _ = runtime

    def error_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    transport = httpx.MockTransport(error_handler)
    tool = WebHttpRequestTool()
    tool._client_factory = _make_mock_client_factory(transport)

    result = await rt.invoke(
        tool,
        args={"method": "GET", "url": "https://unreachable.example.com"},
        policy=Policy(name="t", mode="trusted"),
        run_id="r1",
        run_step_id="s1",
    )
    assert result.outcome == "failed"
