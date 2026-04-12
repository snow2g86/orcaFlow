"""E2E 시나리오 1: 로컬 폴더 정리/이름 변경.

Workflow: planner(list) -> organizer(move)
Agent tools: fs.list, fs.move
Policy: trusted
검증: tmp_path 에 5개 파일 생성 -> 워크플로우 실행 -> 파일이 하위 폴더로 이동됨

Note: GraphRunner 은 노드당 1회 LLM 호출. 다단계 작업은 다중 노드 워크플로우로
구성하거나, 단일 LLM 응답에 모든 tool_call 을 포함해야 한다.
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
from orca_core.tools.fs import FsListTool, FsMoveTool
from orca_core.tools.registry import ToolRegistry
from orca_core.tools.runtime import ToolRuntime
from tests.unit._m3_helpers import InMemoryTransactionFactory


async def test_file_organizer_moves_files_to_subfolder(tmp_path: Path):
    """5개 파일 생성 -> agent 가 fs.move 호출 -> 파일이 하위 폴더로 이동."""
    # Setup: create 5 files
    for i in range(5):
        (tmp_path / f"doc_{i}.txt").write_text(f"content {i}")

    organized_dir = tmp_path / "organized"

    # Single node workflow: the LLM returns all move calls in one response
    responses = [
        # Single LLM call returns all 5 moves at once
        ChatResponse(
            model="fake",
            message=ChatMessage(
                role="assistant",
                content="Moving files to organized/",
                tool_calls=[
                    ChatToolCall(
                        id=f"mv{i}",
                        name="fs.move",
                        arguments={
                            "src": str(tmp_path / f"doc_{i}.txt"),
                            "dst": str(organized_dir / f"doc_{i}.txt"),
                        },
                    )
                    for i in range(5)
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
        model="fake-model",
        is_tool_capable=True,
        is_default=True,
    )

    tool_registry = ToolRegistry()
    tool_registry.register(FsListTool())
    move_tool = FsMoveTool()
    move_tool.default_dry_run = False  # E2E: trusted policy, skip dry_run
    tool_registry.register(move_tool)

    txn = InMemoryTransactionFactory()
    runtime = ToolRuntime(
        transaction_factory=txn,
        audit_log_path=tmp_path / "logs" / "audit.log",
        journal_base_dir=tmp_path / "journal",
    )

    services = OrchestratorServices(
        tool_runtime=runtime,
        tool_registry=tool_registry,
        provider_registry=provider_reg,
        event_bus=EventBus(),
        roles={
            "file_organizer": AgentRole(
                name="file_organizer",
                role_type="worker",
                system_prompt="You are a file organizer.",
                tools=["fs.list", "fs.move"],
                llm_profile_id="prof-1",
            ),
        },
        llm_profiles={profile.id: profile},
    )

    wf = Workflow(
        name="file-organizer",
        nodes=[
            AgentNode(id="organizer", role="file_organizer", position=Position(x=0, y=0)),
        ],
        edges=[],
        entrypoint="organizer",
    )

    ctx = RunContext(
        run_id="run-e2e-1",
        workflow=wf,
        policy=Policy(name="trusted", mode="trusted"),
        services=services,
        cancellation=RunCancellation(),
        initial_state=RunState(),
        inputs={"task": "organize files"},
        dry_run=False,
    )

    runner = GraphRunner()
    await runner.run(ctx)

    # Verify: all 5 files moved to organized/
    assert organized_dir.exists(), "organized/ directory should be created"
    moved_files = list(organized_dir.iterdir())
    assert len(moved_files) == 5, f"Expected 5 files, got {len(moved_files)}"
    for i in range(5):
        assert (organized_dir / f"doc_{i}.txt").exists()
        assert not (tmp_path / f"doc_{i}.txt").exists()

    # Verify: 5 tool calls recorded (all fs.move)
    move_calls = [tc for tc in txn.tool_calls.calls if tc.tool_id == "fs.move"]
    assert len(move_calls) == 5
