"""GraphRunner — 선형 워크플로우 성공 + 노드 + 라우팅 + 실패 경로."""

from __future__ import annotations

import pytest

from orca_core.orchestrator.errors import OrchestratorError
from orca_core.providers.fake import FakeProviderAdapter

from ._m3_helpers import make_audit_log_path, make_journal_base
from ._m4_helpers import (
    MockTool,
    build_services,
    make_response_text,
    make_response_with_tool_call,
    make_role,
    make_run_context,
    make_runner,
    make_workflow,
)

pytestmark = pytest.mark.asyncio


async def test_single_node_no_tool_call(tmp_path):
    fake = FakeProviderAdapter()
    fake.enqueue(make_response_text("done"))

    services = build_services(
        fake,
        roles={"worker": make_role("worker")},
        tools=[],
        audit_log_path=make_audit_log_path(tmp_path),
        journal_base=make_journal_base(tmp_path),
    )
    wf = make_workflow(nodes=[("a", "worker")], edges=[], entrypoint="a")
    ctx = make_run_context(services, wf)
    runner = make_runner()
    await runner.run(ctx)

    events = [e.event for e in services.event_bus.snapshot(ctx.run_id)]
    assert "run.started" in events
    assert "run.succeeded" in events
    assert ctx.initial_state.messages[0]["content"] == "done"


async def test_two_node_chain_with_tool_call(tmp_path):
    tool = MockTool(id="fs.read_file", returns={"content": "hello"})
    fake = FakeProviderAdapter()
    fake.enqueue(make_response_with_tool_call("fs.read_file", {"path": "/x"}, call_id="c1"))
    fake.enqueue(make_response_text("ok"))

    services = build_services(
        fake,
        roles={"worker": make_role("worker", tools=["fs.read_file"])},
        tools=[tool],
        audit_log_path=make_audit_log_path(tmp_path),
        journal_base=make_journal_base(tmp_path),
    )
    wf = make_workflow(
        nodes=[("a", "worker"), ("b", "worker")],
        edges=[("a", "b", None)],
        entrypoint="a",
    )
    ctx = make_run_context(services, wf)
    runner = make_runner()
    await runner.run(ctx)

    events = [e.event for e in services.event_bus.snapshot(ctx.run_id)]
    assert events[0] == "run.started"
    assert "run.succeeded" in events
    assert tool.invocations == [{"path": "/x"}]


async def test_routing_condition_filters_edges(tmp_path):
    """If condition is False, the edge is not taken."""
    fake = FakeProviderAdapter()
    # Node 'a' returns no tool call - state.plan stays None
    fake.enqueue(make_response_text("first"))
    # Node 'c' (the unconditional path) - never reached because state.plan is None
    # Edge a -> b: condition state.plan != None is False, skipped
    # Edge a -> c: no condition, taken

    services = build_services(
        fake,
        roles={"worker": make_role("worker")},
        tools=[],
        audit_log_path=make_audit_log_path(tmp_path),
        journal_base=make_journal_base(tmp_path),
    )
    fake.enqueue(make_response_text("c"))
    wf = make_workflow(
        nodes=[("a", "worker"), ("b", "worker"), ("c", "worker")],
        edges=[
            ("a", "b", "state.plan != None"),
            ("a", "c", None),
        ],
        entrypoint="a",
    )
    ctx = make_run_context(services, wf)
    runner = make_runner()
    await runner.run(ctx)

    # 2 step succeeded events (a, c) - b is filtered
    succeeded = [
        e for e in services.event_bus.snapshot(ctx.run_id) if e.event == "run_step.succeeded"
    ]
    assert len(succeeded) == 2


async def test_tool_failure_propagates_run_failed(tmp_path):
    """H1: tool failure must emit run_step.failed and fail the run."""
    tool = MockTool(id="fs.read_file", fail=True)
    fake = FakeProviderAdapter()
    fake.enqueue(make_response_with_tool_call("fs.read_file", {"path": "/x"}))

    services = build_services(
        fake,
        roles={"worker": make_role("worker", tools=["fs.read_file"])},
        tools=[tool],
        audit_log_path=make_audit_log_path(tmp_path),
        journal_base=make_journal_base(tmp_path),
    )
    wf = make_workflow(nodes=[("a", "worker")], edges=[], entrypoint="a")
    ctx = make_run_context(services, wf)
    runner = make_runner()

    with pytest.raises(OrchestratorError):
        await runner.run(ctx)
    events = [e.event for e in services.event_bus.snapshot(ctx.run_id)]
    assert "run_step.failed" in events
    assert "run.failed" in events
    assert "run.succeeded" not in events


async def test_unknown_role_raises_resolution_error(tmp_path):
    fake = FakeProviderAdapter()
    services = build_services(
        fake,
        roles={},
        tools=[],
        audit_log_path=make_audit_log_path(tmp_path),
        journal_base=make_journal_base(tmp_path),
    )
    wf = make_workflow(nodes=[("a", "missing-role")], edges=[], entrypoint="a")
    ctx = make_run_context(services, wf)
    runner = make_runner()

    with pytest.raises(OrchestratorError):
        await runner.run(ctx)
    events = [e.event for e in services.event_bus.snapshot(ctx.run_id)]
    assert "run.failed" in events


async def test_unknown_llm_profile_raises(tmp_path):
    fake = FakeProviderAdapter()
    services = build_services(
        fake,
        roles={"worker": make_role("worker", llm_profile_id="missing-profile")},
        tools=[],
        audit_log_path=make_audit_log_path(tmp_path),
        journal_base=make_journal_base(tmp_path),
    )
    wf = make_workflow(nodes=[("a", "worker")], edges=[], entrypoint="a")
    ctx = make_run_context(services, wf)
    runner = make_runner()
    with pytest.raises(OrchestratorError):
        await runner.run(ctx)


async def test_tool_call_unknown_tool_id_raises(tmp_path):
    """LLM responds with a tool_call referencing an id not registered."""
    from orca_core.providers._base import ChatMessage, ChatResponse, ChatToolCall, ChatUsage

    fake = FakeProviderAdapter()
    fake.enqueue(
        ChatResponse(
            model="fake-model",
            message=ChatMessage(
                role="assistant",
                content="",
                tool_calls=[ChatToolCall(id="c1", name="unknown.tool", arguments={})],
            ),
            finish_reason="tool_calls",
            usage=ChatUsage(),
        )
    )
    services = build_services(
        fake,
        roles={"worker": make_role("worker", tools=["unknown.tool"])},
        tools=[],
        audit_log_path=make_audit_log_path(tmp_path),
        journal_base=make_journal_base(tmp_path),
    )
    wf = make_workflow(nodes=[("a", "worker")], edges=[], entrypoint="a")
    ctx = make_run_context(services, wf)
    runner = make_runner()
    with pytest.raises(OrchestratorError):
        await runner.run(ctx)


async def test_tool_call_not_in_role_tools_raises(tmp_path):
    from orca_core.providers._base import ChatMessage, ChatResponse, ChatToolCall, ChatUsage

    tool = MockTool(id="fs.read_file")
    fake = FakeProviderAdapter()
    fake.enqueue(
        ChatResponse(
            model="fake-model",
            message=ChatMessage(
                role="assistant",
                content="",
                tool_calls=[ChatToolCall(id="c1", name="fs.read_file", arguments={"path": "/x"})],
            ),
            finish_reason="tool_calls",
            usage=ChatUsage(),
        )
    )
    services = build_services(
        fake,
        # role does NOT include the tool
        roles={"worker": make_role("worker", tools=[])},
        tools=[tool],
        audit_log_path=make_audit_log_path(tmp_path),
        journal_base=make_journal_base(tmp_path),
    )
    wf = make_workflow(nodes=[("a", "worker")], edges=[], entrypoint="a")
    ctx = make_run_context(services, wf)
    runner = make_runner()
    with pytest.raises(OrchestratorError):
        await runner.run(ctx)


async def test_messages_carried_to_next_node(tmp_path):
    """state.messages is preserved across node transitions."""
    fake = FakeProviderAdapter()
    fake.enqueue(make_response_text("first"))
    fake.enqueue(make_response_text("second"))

    services = build_services(
        fake,
        roles={"worker": make_role("worker")},
        tools=[],
        audit_log_path=make_audit_log_path(tmp_path),
        journal_base=make_journal_base(tmp_path),
    )
    wf = make_workflow(
        nodes=[("a", "worker"), ("b", "worker")],
        edges=[("a", "b", None)],
        entrypoint="a",
    )
    ctx = make_run_context(services, wf)
    runner = make_runner()
    await runner.run(ctx)
    # 2 assistant messages should be in state
    assert len(ctx.initial_state.messages) == 2
    assert ctx.initial_state.messages[0]["content"] == "first"
    assert ctx.initial_state.messages[1]["content"] == "second"


async def test_tool_failure_emits_run_step_failed_and_fails_run(tmp_path):
    """H1: failed tool outcome must emit run_step.failed BEFORE run.failed."""
    tool = MockTool(id="fs.read_file", fail=True)
    fake = FakeProviderAdapter()
    fake.enqueue(make_response_with_tool_call("fs.read_file", {"path": "/x"}))

    services = build_services(
        fake,
        roles={"worker": make_role("worker", tools=["fs.read_file"])},
        tools=[tool],
        audit_log_path=make_audit_log_path(tmp_path),
        journal_base=make_journal_base(tmp_path),
    )
    wf = make_workflow(nodes=[("a", "worker")], edges=[], entrypoint="a")
    ctx = make_run_context(services, wf)
    runner = make_runner()
    with pytest.raises(OrchestratorError):
        await runner.run(ctx)
    names = [e.event for e in services.event_bus.snapshot(ctx.run_id)]
    assert "run_step.started" in names
    assert "run_step.failed" in names
    assert "run.failed" in names
    # Order: run_step.failed precedes run.failed
    assert names.index("run_step.failed") < names.index("run.failed")
    # run_step.succeeded must NOT appear
    assert "run_step.succeeded" not in names


async def test_status_sink_failure_fails_run_mid_execution(tmp_path):
    """H7: a mid-execution status_sink failure must escalate to run.failed."""
    from orca_core.orchestrator.runner import GraphRunner

    fake = FakeProviderAdapter()
    fake.enqueue(make_response_text("ok"))

    services = build_services(
        fake,
        roles={"worker": make_role("worker")},
        tools=[],
        audit_log_path=make_audit_log_path(tmp_path),
        journal_base=make_journal_base(tmp_path),
    )

    class BrokenSink:
        def __init__(self) -> None:
            self.calls = 0

        async def set_run_status(
            self, run_id: str, status: str, *, ended_at=None, error=None
        ) -> None:
            self.calls += 1
            # Fail on the initial `running` transition only.
            if status == "running":
                raise RuntimeError("DB down")

    sink = BrokenSink()
    runner = GraphRunner(status_sink=sink)
    wf = make_workflow(nodes=[("a", "worker")], edges=[], entrypoint="a")
    ctx = make_run_context(services, wf)
    with pytest.raises(OrchestratorError):
        await runner.run(ctx)
    names = [e.event for e in services.event_bus.snapshot(ctx.run_id)]
    assert "run.failed" in names


async def test_status_sink_failure_on_terminal_is_logged_only(tmp_path):
    """H7: once we are emitting the terminal transition, sink failures are
    swallowed (no escalation possible). Still reaches run.succeeded event."""
    from orca_core.orchestrator.runner import GraphRunner

    fake = FakeProviderAdapter()
    fake.enqueue(make_response_text("ok"))

    services = build_services(
        fake,
        roles={"worker": make_role("worker")},
        tools=[],
        audit_log_path=make_audit_log_path(tmp_path),
        journal_base=make_journal_base(tmp_path),
    )

    class TerminalBrokenSink:
        async def set_run_status(
            self, run_id: str, status: str, *, ended_at=None, error=None
        ) -> None:
            # Succeed for initial running, fail only on terminal statuses.
            if status in ("succeeded", "failed", "cancelled"):
                raise RuntimeError("DB flaky")

    runner = GraphRunner(status_sink=TerminalBrokenSink())
    wf = make_workflow(nodes=[("a", "worker")], edges=[], entrypoint="a")
    ctx = make_run_context(services, wf)
    # Should NOT raise — terminal sink failure is logged and swallowed.
    await runner.run(ctx)
    names = [e.event for e in services.event_bus.snapshot(ctx.run_id)]
    assert "run.succeeded" in names


async def test_tool_returns_recorded_in_state_artifacts(tmp_path):
    tool = MockTool(id="fs.read_file", returns={"content": "abc"})
    from orca_core.providers._base import ChatMessage, ChatResponse, ChatToolCall, ChatUsage

    fake = FakeProviderAdapter()
    fake.enqueue(
        ChatResponse(
            model="fake-model",
            message=ChatMessage(
                role="assistant",
                content="",
                tool_calls=[ChatToolCall(id="c1", name="fs.read_file", arguments={"path": "/x"})],
            ),
            finish_reason="tool_calls",
            usage=ChatUsage(),
        )
    )
    services = build_services(
        fake,
        roles={"worker": make_role("worker", tools=["fs.read_file"])},
        tools=[tool],
        audit_log_path=make_audit_log_path(tmp_path),
        journal_base=make_journal_base(tmp_path),
    )
    wf = make_workflow(nodes=[("a", "worker")], edges=[], entrypoint="a")
    ctx = make_run_context(services, wf)
    runner = make_runner()
    await runner.run(ctx)
    assert ctx.initial_state.artifacts.get("c1") == {"content": "abc"}
