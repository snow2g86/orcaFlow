"""E2E 시나리오 3: 웹 탐색 후 요약 저장.

Workflow: lister(http_request) -> writer(write_file) (2-node)
Agent tools: web.http_request, fs.write_file
검증: httpx MockTransport 로 fake 웹 응답 -> agent 가 요약을 파일로 저장
(실제 외부 호출 금지, mock 사용)

Note: GraphRunner 은 노드당 1회 LLM 호출. 2-node 워크플로우로 분리.
"""

from __future__ import annotations

from pathlib import Path

import httpx

from orca_core.orchestrator import (
    EventBus,
    GraphRunner,
    OrchestratorServices,
    RunCancellation,
    RunContext,
    RunState,
)
from orca_core.providers._base import (
    ChatMessage,
    ChatResponse,
    ChatToolCall,
    ChatUsage,
)
from orca_core.providers.fake import FakeProviderAdapter
from orca_core.providers.registry import ProviderRegistry
from orca_core.schema.agent import AgentRole
from orca_core.schema.llm import LLMProfile, Provider
from orca_core.schema.policy import Policy
from orca_core.schema.workflow import AgentNode, Edge, Position, Workflow
from orca_core.tools.fs import FsWriteFileTool
from orca_core.tools.registry import ToolRegistry
from orca_core.tools.runtime import ToolRuntime
from orca_core.tools.web import WebHttpRequestTool
from tests.unit._m3_helpers import InMemoryTransactionFactory


def _make_mock_transport() -> httpx.MockTransport:
    """Fake web response."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="<html><body><h1>Python 3.12 Release</h1>"
            "<p>Python 3.12 includes performance improvements and new features.</p>"
            "</body></html>",
        )

    return httpx.MockTransport(handler)


async def test_web_researcher_fetches_and_saves_summary(tmp_path: Path):
    """Mock 웹 응답 fetch + 요약 파일 저장. 2-node 워크플로우."""
    output_file = tmp_path / "summary.txt"

    # Prepare mock HTTP tool
    transport = _make_mock_transport()

    class MockAsyncClient(httpx.AsyncClient):
        def __init__(self, **kwargs):
            super().__init__(transport=transport, **kwargs)

    http_tool = WebHttpRequestTool()
    http_tool._client_factory = MockAsyncClient

    # Node 1 (fetcher): http_request
    # Node 2 (writer): write_file
    responses = [
        # Node 1: fetch web page
        ChatResponse(
            model="fake",
            message=ChatMessage(
                role="assistant",
                content="Fetching page",
                tool_calls=[
                    ChatToolCall(
                        id="c1",
                        name="web.http_request",
                        arguments={
                            "method": "GET",
                            "url": "https://python.org/releases",
                        },
                    ),
                ],
            ),
            finish_reason="tool_calls",
            usage=ChatUsage(),
        ),
        # Node 2: write summary
        ChatResponse(
            model="fake",
            message=ChatMessage(
                role="assistant",
                content="Writing summary",
                tool_calls=[
                    ChatToolCall(
                        id="c2",
                        name="fs.write_file",
                        arguments={
                            "path": str(output_file),
                            "content": "Summary: Python 3.12 includes performance improvements.",
                        },
                    ),
                ],
            ),
            finish_reason="tool_calls",
            usage=ChatUsage(),
        ),
    ]

    fake = FakeProviderAdapter(responses=responses)

    provider = Provider(id="p1", name="fake", kind="openai_compatible", base_url="x")
    provider_reg = ProviderRegistry()
    provider_reg.register(provider, fake)

    profile = LLMProfile(
        id="prof-1",
        name="prof-1",
        provider_id="p1",
        model="fake",
        is_tool_capable=True,
        is_default=True,
    )

    tool_registry = ToolRegistry()
    tool_registry.register(http_tool)
    write_tool = FsWriteFileTool()
    write_tool.default_dry_run = False  # E2E: trusted policy, skip dry_run
    tool_registry.register(write_tool)

    txn = InMemoryTransactionFactory()
    runtime = ToolRuntime(
        transaction_factory=txn,
        audit_log_path=tmp_path / "audit.log",
        journal_base_dir=tmp_path / "journal",
    )

    services = OrchestratorServices(
        tool_runtime=runtime,
        tool_registry=tool_registry,
        provider_registry=provider_reg,
        event_bus=EventBus(),
        roles={
            "fetcher": AgentRole(
                name="fetcher",
                role_type="worker",
                system_prompt="Fetch web pages.",
                tools=["web.http_request"],
                llm_profile_id="prof-1",
            ),
            "writer": AgentRole(
                name="writer",
                role_type="worker",
                system_prompt="Write summaries to files.",
                tools=["fs.write_file"],
                llm_profile_id="prof-1",
            ),
        },
        llm_profiles={profile.id: profile},
    )

    wf = Workflow(
        name="web-researcher",
        nodes=[
            AgentNode(id="fetch", role="fetcher", position=Position(x=0, y=0)),
            AgentNode(id="write", role="writer", position=Position(x=200, y=0)),
        ],
        edges=[
            Edge.model_validate({"from": "fetch", "to": "write", "condition": None}),
        ],
        entrypoint="fetch",
    )

    ctx = RunContext(
        run_id="run-e2e-3",
        workflow=wf,
        policy=Policy(name="trusted", mode="trusted"),
        services=services,
        cancellation=RunCancellation(),
        initial_state=RunState(),
        inputs={"task": "research Python 3.12"},
        dry_run=False,
    )

    runner = GraphRunner()
    await runner.run(ctx)

    # Verify: summary file was created
    assert output_file.exists(), "summary.txt should be created"
    content = output_file.read_text()
    assert "Python 3.12" in content

    # Verify: tool calls recorded
    http_calls = [tc for tc in txn.tool_calls.calls if tc.tool_id == "web.http_request"]
    write_calls = [tc for tc in txn.tool_calls.calls if tc.tool_id == "fs.write_file"]
    assert len(http_calls) == 1
    assert len(write_calls) == 1
