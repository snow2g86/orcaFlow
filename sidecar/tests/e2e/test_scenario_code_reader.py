"""E2E 시나리오 2: 코드베이스 읽고 요약.

Workflow: code_reader (single node)
Agent tools: fs.list, fs.read_file
검증: tmp_path 에 Python 파일 3개 생성 -> agent 가 읽고 tool result 기록

Note: GraphRunner 은 노드당 1회 LLM 호출. 단일 응답에 모든 tool_call 포함.
"""

from __future__ import annotations

from pathlib import Path

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
from orca_core.schema.workflow import AgentNode, Position, Workflow
from orca_core.tools.fs import FsListTool, FsReadFileTool
from orca_core.tools.registry import ToolRegistry
from orca_core.tools.runtime import ToolRuntime
from tests.unit._m3_helpers import InMemoryTransactionFactory


async def test_code_reader_reads_and_summarizes(tmp_path: Path):
    """3개 Python 파일 생성 -> agent 가 단일 LLM 호출에서 3개 read_file 호출."""
    # Setup: create 3 Python files
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text("def main():\n    print('hello')\n")
    (src_dir / "utils.py").write_text("def add(a, b):\n    return a + b\n")
    (src_dir / "config.py").write_text("DB_URL = 'sqlite:///db.sqlite'\n")

    responses = [
        # Single LLM call reads all 3 files
        ChatResponse(
            model="fake",
            message=ChatMessage(
                role="assistant",
                content="Reading source files",
                tool_calls=[
                    ChatToolCall(
                        id="r1",
                        name="fs.read_file",
                        arguments={"path": str(src_dir / "main.py")},
                    ),
                    ChatToolCall(
                        id="r2",
                        name="fs.read_file",
                        arguments={"path": str(src_dir / "utils.py")},
                    ),
                    ChatToolCall(
                        id="r3",
                        name="fs.read_file",
                        arguments={"path": str(src_dir / "config.py")},
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
    tool_registry.register(FsListTool())
    tool_registry.register(FsReadFileTool())

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
            "code_reader": AgentRole(
                name="code_reader",
                role_type="worker",
                system_prompt="Read code and summarize.",
                tools=["fs.list", "fs.read_file"],
                llm_profile_id="prof-1",
            ),
        },
        llm_profiles={profile.id: profile},
    )

    wf = Workflow(
        name="code-reader",
        nodes=[AgentNode(id="reader", role="code_reader", position=Position(x=0, y=0))],
        edges=[],
        entrypoint="reader",
    )

    ctx = RunContext(
        run_id="run-e2e-2",
        workflow=wf,
        policy=Policy(name="trusted", mode="trusted"),
        services=services,
        cancellation=RunCancellation(),
        initial_state=RunState(),
        inputs={"task": "read and summarize src/"},
        dry_run=False,
    )

    runner = GraphRunner()
    await runner.run(ctx)

    # Verify: 3 read_file tool calls recorded
    read_calls = [tc for tc in txn.tool_calls.calls if tc.tool_id == "fs.read_file"]
    assert len(read_calls) == 3

    # Verify: each read returned actual file content
    for tc in read_calls:
        assert tc.result is not None
        assert "content" in tc.result
        assert tc.result["encoding"] == "utf-8"
