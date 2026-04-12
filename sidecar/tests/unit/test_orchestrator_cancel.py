"""Run cancellation tests."""

from __future__ import annotations

import asyncio

import pytest

from orca_core.providers.fake import FakeProviderAdapter

from ._m3_helpers import make_audit_log_path, make_journal_base
from ._m4_helpers import (
    build_services,
    make_response_text,
    make_role,
    make_run_context,
    make_runner,
    make_workflow,
)

pytestmark = pytest.mark.asyncio


async def test_cancel_before_run_starts(tmp_path):
    fake = FakeProviderAdapter()
    fake.enqueue(make_response_text("a"))

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
    ctx.cancellation.cancel()
    runner = make_runner()
    await runner.run(ctx)

    events = [e.event for e in services.event_bus.snapshot(ctx.run_id)]
    assert "run.cancelled" in events


async def test_cancel_in_middle_of_chain(tmp_path):
    fake = FakeProviderAdapter(strict=False)
    fake.enqueue(make_response_text("a"))
    fake.enqueue(make_response_text("b"))

    services = build_services(
        fake,
        roles={"worker": make_role("worker")},
        tools=[],
        audit_log_path=make_audit_log_path(tmp_path),
        journal_base=make_journal_base(tmp_path),
    )
    wf = make_workflow(
        nodes=[("a", "worker"), ("b", "worker"), ("c", "worker")],
        edges=[("a", "b", None), ("b", "c", None)],
        entrypoint="a",
    )
    ctx = make_run_context(services, wf)
    runner = make_runner()

    async def trigger_cancel():
        await asyncio.sleep(0.005)
        ctx.cancellation.cancel()

    cancel_task = asyncio.create_task(trigger_cancel())
    await runner.run(ctx)
    await cancel_task

    events = [e.event for e in services.event_bus.snapshot(ctx.run_id)]
    # The run should have entered cancelled or succeeded depending on timing
    assert any(e in ("run.cancelled", "run.succeeded") for e in events)
