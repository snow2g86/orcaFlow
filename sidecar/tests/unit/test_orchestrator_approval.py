"""Approval flow — ask -> waiter -> approve / reject -> resume / fail."""

from __future__ import annotations

import pytest

from orca_core.orchestrator.errors import OrchestratorError
from orca_core.providers.fake import FakeProviderAdapter

from ._m3_helpers import make_audit_log_path, make_journal_base
from ._m4_helpers import (
    MockTool,
    build_services,
    make_ask_policy,
    make_response_with_tool_call,
    make_role,
    make_run_context,
    make_runner,
    make_workflow,
)

pytestmark = pytest.mark.asyncio


async def test_approval_approved_resumes_with_override(tmp_path):
    """Tool with side_effect=write triggers ask, approve resumes."""
    tool = MockTool(
        id="fs.read_file",
        side_effect="write",
        returns={"wrote": True},
    )
    fake = FakeProviderAdapter()
    fake.enqueue(make_response_with_tool_call("fs.read_file", {"path": "/x"}))

    services = build_services(
        fake,
        roles={"worker": make_role("worker", tools=["fs.read_file"])},
        tools=[tool],
        audit_log_path=make_audit_log_path(tmp_path),
        journal_base=make_journal_base(tmp_path),
    )
    policy = make_ask_policy()
    ctx = make_run_context(services, make_workflow([("a", "worker")], [], "a"), policy=policy)

    async def waiter(approval):
        return True

    runner = make_runner(approval_waiter=waiter)
    await runner.run(ctx)

    # Tool actually ran (because override was used)
    assert tool.invocations == [{"path": "/x"}]
    events = [e.event for e in services.event_bus.snapshot(ctx.run_id)]
    assert "approval.approved" in events
    assert "run.succeeded" in events


async def test_approval_rejected_fails_run(tmp_path):
    tool = MockTool(id="fs.read_file", side_effect="write")
    fake = FakeProviderAdapter()
    fake.enqueue(make_response_with_tool_call("fs.read_file", {"path": "/x"}))

    services = build_services(
        fake,
        roles={"worker": make_role("worker", tools=["fs.read_file"])},
        tools=[tool],
        audit_log_path=make_audit_log_path(tmp_path),
        journal_base=make_journal_base(tmp_path),
    )
    policy = make_ask_policy()
    ctx = make_run_context(services, make_workflow([("a", "worker")], [], "a"), policy=policy)

    async def waiter(approval):
        return False

    runner = make_runner(approval_waiter=waiter)
    with pytest.raises(OrchestratorError):
        await runner.run(ctx)

    assert tool.invocations == []  # tool never executed
    events = [e.event for e in services.event_bus.snapshot(ctx.run_id)]
    assert "approval.rejected" in events
    assert "run.failed" in events


async def test_approval_ttl_expired_transitions_state_and_emits(tmp_path):
    """H2: waiter raising ApprovalExpiredError → run.failed + approval.expired.

    The waiter stub simulates the runs route behaviour: on TTL elapse it
    marks the approval as `expired`, emits `approval.expired` on the bus,
    and raises `ApprovalExpiredError`.
    """
    from orca_core.orchestrator.errors import ApprovalExpiredError

    tool = MockTool(id="fs.read_file", side_effect="write")
    fake = FakeProviderAdapter()
    fake.enqueue(make_response_with_tool_call("fs.read_file", {"path": "/x"}))

    services = build_services(
        fake,
        roles={"worker": make_role("worker", tools=["fs.read_file"])},
        tools=[tool],
        audit_log_path=make_audit_log_path(tmp_path),
        journal_base=make_journal_base(tmp_path),
    )
    policy = make_ask_policy()
    ctx = make_run_context(services, make_workflow([("a", "worker")], [], "a"), policy=policy)

    async def expired_waiter(approval):
        # Mirror production behaviour: emit approval.expired on the bus
        # before raising so the event is observable in the snapshot.
        await services.event_bus.emit(
            ctx.run_id,
            "approval.expired",
            {"approval_id": approval.id, "tool_id": tool.id},
        )
        raise ApprovalExpiredError(
            f"approval {approval.id} expired",
            details={"approval_id": approval.id},
        )

    runner = make_runner(approval_waiter=expired_waiter)
    with pytest.raises(OrchestratorError):
        await runner.run(ctx)

    assert tool.invocations == []  # tool never executed
    events = [e.event for e in services.event_bus.snapshot(ctx.run_id)]
    assert "approval.expired" in events
    assert "run.failed" in events
    assert "approval.rejected" not in events  # distinct from reject


async def test_cancel_during_approval_distinguishes_from_reject(tmp_path):
    """H4: when the run is cancelled while an approval is pending, the
    waiter surfaces ApprovalCancelledError which maps to run.cancelled,
    NOT run.failed / approval.rejected."""
    from orca_core.orchestrator.errors import ApprovalCancelledError

    tool = MockTool(id="fs.read_file", side_effect="write")
    fake = FakeProviderAdapter()
    fake.enqueue(make_response_with_tool_call("fs.read_file", {"path": "/x"}))

    services = build_services(
        fake,
        roles={"worker": make_role("worker", tools=["fs.read_file"])},
        tools=[tool],
        audit_log_path=make_audit_log_path(tmp_path),
        journal_base=make_journal_base(tmp_path),
    )
    policy = make_ask_policy()
    ctx = make_run_context(services, make_workflow([("a", "worker")], [], "a"), policy=policy)

    async def cancel_waiter(approval):
        raise ApprovalCancelledError(
            f"approval {approval.id} cancelled",
            details={"approval_id": approval.id},
        )

    runner = make_runner(approval_waiter=cancel_waiter)
    # ApprovalCancelledError is translated to RunCancelledError inside the
    # runner and run() returns cleanly with run.cancelled emitted.
    await runner.run(ctx)

    assert tool.invocations == []
    events = [e.event for e in services.event_bus.snapshot(ctx.run_id)]
    assert "run.cancelled" in events
    assert "run.failed" not in events
    assert "approval.rejected" not in events


async def test_approval_waiter_receives_approval_object(tmp_path):
    tool = MockTool(id="fs.read_file", side_effect="write")
    fake = FakeProviderAdapter()
    fake.enqueue(make_response_with_tool_call("fs.read_file", {"path": "/x"}))

    services = build_services(
        fake,
        roles={"worker": make_role("worker", tools=["fs.read_file"])},
        tools=[tool],
        audit_log_path=make_audit_log_path(tmp_path),
        journal_base=make_journal_base(tmp_path),
    )
    policy = make_ask_policy()
    ctx = make_run_context(services, make_workflow([("a", "worker")], [], "a"), policy=policy)

    captured: list = []

    async def waiter(approval):
        captured.append(approval)
        return True

    runner = make_runner(approval_waiter=waiter)
    await runner.run(ctx)
    assert len(captured) == 1
    assert captured[0].state == "pending"
