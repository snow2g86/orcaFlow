"""GraphRunner — 분기/조인 토폴로지."""

from __future__ import annotations

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


async def test_diamond_topology_visits_join_once(tmp_path):
    """A -> {B, C} -> D : D should be visited exactly once even if both B and C
    enqueue it."""
    fake = FakeProviderAdapter()
    # 4 nodes -> 4 chat responses
    for label in ("a", "b", "c", "d"):
        fake.enqueue(make_response_text(label))

    services = build_services(
        fake,
        roles={"worker": make_role("worker")},
        tools=[],
        audit_log_path=make_audit_log_path(tmp_path),
        journal_base=make_journal_base(tmp_path),
    )
    wf = make_workflow(
        nodes=[("a", "worker"), ("b", "worker"), ("c", "worker"), ("d", "worker")],
        edges=[
            ("a", "b", None),
            ("a", "c", None),
            ("b", "d", None),
            ("c", "d", None),
        ],
        entrypoint="a",
    )
    ctx = make_run_context(services, wf)
    runner = make_runner()
    await runner.run(ctx)

    succeeded = [
        e for e in services.event_bus.snapshot(ctx.run_id) if e.event == "run_step.succeeded"
    ]
    visited_nodes = [e.payload["node_id"] for e in succeeded]
    # Each node visited exactly once
    assert sorted(visited_nodes) == ["a", "b", "c", "d"]
