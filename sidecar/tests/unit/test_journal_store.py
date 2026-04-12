"""JournalStore — before/after, 대용량 spill, restore planning."""

from __future__ import annotations

from pathlib import Path

import pytest

from orca_core.journal import (
    SPILL_THRESHOLD_BYTES,
    JournalStore,
    JournalWriteError,
    plan_restore,
)


@pytest.fixture
def store(tmp_path: Path) -> JournalStore:
    return JournalStore(base_dir=tmp_path / "journal")


async def test_record_before_small_inline(store: JournalStore):
    entry = await store.record_before(
        run_id="r1",
        run_step_id="s1",
        tool_call_id="t1",
        kind="fs_write",
        before={"path": "/tmp/x", "content": "hello"},
        reversible=True,
    )
    assert entry.reversible is True
    assert entry.before == {"path": "/tmp/x", "content": "hello"}
    assert entry.before_storage_ref is None
    assert entry.after_storage_ref is None


async def test_record_before_spills_large(store: JournalStore, tmp_path: Path):
    big = {"content": "x" * (SPILL_THRESHOLD_BYTES + 10)}
    entry = await store.record_before(
        run_id="r1",
        run_step_id="s1",
        tool_call_id="t1",
        kind="fs_write",
        before=big,
        reversible=True,
    )
    assert entry.before is None
    assert entry.before_storage_ref is not None
    assert Path(entry.before_storage_ref).exists()
    loaded = store.load_payload(entry.before_storage_ref)
    assert loaded == big


async def test_record_after_updates_entry(store: JournalStore):
    entry = await store.record_before(
        run_id="r1",
        run_step_id="s1",
        tool_call_id="t1",
        kind="fs_write",
        before={"path": "/tmp/x"},
        reversible=True,
    )
    updated = await store.record_after(
        entry, run_id="r1", after={"path": "/tmp/x", "content": "new"}
    )
    assert updated.after == {"path": "/tmp/x", "content": "new"}


async def test_record_before_db_failure_raises(tmp_path: Path):
    class BadWriter:
        async def insert(self, entry):  # type: ignore[no-untyped-def]
            raise RuntimeError("fail")

        async def update_after(self, entry_id, *, after, after_storage_ref):  # type: ignore[no-untyped-def]
            pass

        async def mark_restored(self, entry_id):  # type: ignore[no-untyped-def]
            pass

        async def list_for_run(self, run_id):  # type: ignore[no-untyped-def]
            return []

    store = JournalStore(base_dir=tmp_path / "journal", db_writer=BadWriter())  # type: ignore[arg-type]
    with pytest.raises(JournalWriteError):
        await store.record_before(
            run_id="r",
            run_step_id="s",
            tool_call_id="t",
            kind="fs_write",
            before={"x": 1},
            reversible=True,
        )


async def test_restore_plan_ready(store: JournalStore):
    entry = await store.record_before(
        run_id="r1",
        run_step_id="s1",
        tool_call_id="t1",
        kind="fs_write",
        before={"content": "original"},
        reversible=True,
    )
    entry_after = await store.record_after(entry, run_id="r1", after={"content": "modified"})
    plan = plan_restore(store, entry_after, current_state={"content": "modified"})
    assert plan.status == "ready"
    assert plan.target_payload == {"content": "original"}


async def test_restore_plan_conflict_on_checksum_mismatch(store: JournalStore):
    entry = await store.record_before(
        run_id="r1",
        run_step_id="s1",
        tool_call_id="t1",
        kind="fs_write",
        before={"content": "original"},
        reversible=True,
    )
    entry_after = await store.record_after(entry, run_id="r1", after={"content": "modified"})
    plan = plan_restore(store, entry_after, current_state={"content": "tampered"})
    assert plan.status == "conflict"
    assert plan.target_payload is None


async def test_restore_plan_not_reversible(store: JournalStore):
    entry = await store.record_before(
        run_id="r1",
        run_step_id="s1",
        tool_call_id="t1",
        kind="custom",
        before={"x": 1},
        reversible=False,
    )
    plan = plan_restore(store, entry)
    assert plan.status == "not_reversible"


async def test_checksum_is_order_independent():
    a = JournalStore.checksum({"x": 1, "y": 2})
    b = JournalStore.checksum({"y": 2, "x": 1})
    assert a == b


# ---------------------------------------------------------------------------
# Regression: H1 — record_after must NOT overwrite before_storage_ref
# (previously the spill path of before was reused for after, so restore
#  would load the after payload and reapply destructive change).
# ---------------------------------------------------------------------------


async def test_record_after_preserves_before_storage_ref_when_spilled(
    store: JournalStore, tmp_path: Path
):
    big_before = {"content": "A" * (SPILL_THRESHOLD_BYTES + 10)}
    big_after = {"content": "B" * (SPILL_THRESHOLD_BYTES + 10)}
    entry = await store.record_before(
        run_id="r-regress",
        run_step_id="s1",
        tool_call_id="t1",
        kind="fs_write",
        before=big_before,
        reversible=True,
    )
    before_ref = entry.before_storage_ref
    assert before_ref is not None
    updated = await store.record_after(entry, run_id="r-regress", after=big_after)
    # before_storage_ref preserved across record_after
    assert updated.before_storage_ref == before_ref
    # after_storage_ref is a different file
    assert updated.after_storage_ref is not None
    assert updated.after_storage_ref != before_ref
    # Files contain distinct payloads
    assert store.load_payload(updated.before_storage_ref) == big_before  # type: ignore[arg-type]
    assert store.load_payload(updated.after_storage_ref) == big_after

    # restore plan loads the *before* payload (not after)
    plan = plan_restore(store, updated, current_state=big_after)
    assert plan.status == "ready"
    assert plan.target_payload == big_before


async def test_record_before_missing_run_id_raises(store: JournalStore):
    with pytest.raises(JournalWriteError, match="run_id"):
        await store.record_before(
            run_id="",
            run_step_id="s1",
            tool_call_id="t1",
            kind="fs_write",
            before={"x": 1},
            reversible=True,
        )


async def test_record_after_missing_run_id_raises(store: JournalStore):
    entry = await store.record_before(
        run_id="r1",
        run_step_id="s1",
        tool_call_id="t1",
        kind="fs_write",
        before={"x": 1},
        reversible=True,
    )
    with pytest.raises(JournalWriteError, match="run_id"):
        await store.record_after(entry, run_id="", after={"x": 2})
