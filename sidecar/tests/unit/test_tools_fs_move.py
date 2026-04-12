"""fs.move 툴 테스트 — multi-path policy 매칭 포함."""

from __future__ import annotations

from pathlib import Path

import pytest

from orca_core.errors import PolicyViolationError
from orca_core.schema import Policy, PolicyRule
from orca_core.tools import InMemoryEventEmitter, ToolRuntime
from orca_core.tools.fs import FsMoveTool

from ._m3_helpers import (
    InMemoryTransactionFactory,
    make_audit_log_path,
    make_journal_base,
)


@pytest.fixture
def runtime(tmp_path: Path):
    factory = InMemoryTransactionFactory()
    rt = ToolRuntime(
        transaction_factory=factory,
        audit_log_path=make_audit_log_path(tmp_path),
        journal_base_dir=make_journal_base(tmp_path),
        events=InMemoryEventEmitter(),
    )
    return rt, factory


def _allow_move_policy() -> Policy:
    return Policy(
        name="allow-move",
        mode="ask",
        rules=[
            PolicyRule(priority=10, scope="tool_id", matcher="fs.move", effect="allow"),
        ],
    )


async def test_default_dry_run_stops_without_moving(tmp_path: Path, runtime):
    rt, _factory = runtime
    src = tmp_path / "src.txt"
    dst = tmp_path / "dst.txt"
    src.write_text("hi")

    result = await rt.invoke(
        FsMoveTool(),
        args={"src": str(src), "dst": str(dst)},
        policy=_allow_move_policy(),
        run_id="r1",
        run_step_id="s1",
    )
    assert result.outcome == "dry_run"
    assert src.exists()
    assert not dst.exists()


async def test_move_succeeds_when_default_dry_run_off(tmp_path: Path, runtime):
    rt, factory = runtime
    src = tmp_path / "src.txt"
    dst = tmp_path / "dst.txt"
    src.write_text("hi")

    class _AutoMove(FsMoveTool):
        default_dry_run: bool = False

    result = await rt.invoke(
        _AutoMove(),
        args={"src": str(src), "dst": str(dst)},
        policy=_allow_move_policy(),
        run_id="r1",
        run_step_id="s1",
    )
    assert result.outcome == "succeeded"
    assert not src.exists()
    assert dst.read_text() == "hi"
    # Journal recorded with both src and dst
    assert len(factory.journal.entries) == 1


async def test_conflict_reported_in_dry_preview(tmp_path: Path, runtime):
    rt, _ = runtime
    src = tmp_path / "src.txt"
    dst = tmp_path / "dst.txt"
    src.write_text("one")
    dst.write_text("two")

    result = await rt.invoke(
        FsMoveTool(),
        args={"src": str(src), "dst": str(dst)},
        policy=_allow_move_policy(),
        run_id="r1",
        run_step_id="s1",
    )
    preview = result.result.diff_preview
    assert preview["conflict"] is True


async def test_overwrite_preserves_old_dst_in_trash_for_recovery(tmp_path: Path, runtime):
    """H9 regression: fs.move with overwrite=True previously clobbered the
    existing dst without journaling it, so undo could not restore the
    original dst content. After fix, the existing dst is moved to trash
    first and `dst_trash_ref` is recorded in both the before-snapshot and
    the output, enabling a two-step restore: (1) dst → src, (2) trash → dst.
    """
    rt, factory = runtime
    src = tmp_path / "src.txt"
    dst = tmp_path / "dst.txt"
    src.write_text("new-content")
    dst.write_text("old-content-must-not-be-lost")

    class _AutoMove(FsMoveTool):
        default_dry_run: bool = False

    result = await rt.invoke(
        _AutoMove(),
        args={"src": str(src), "dst": str(dst), "overwrite": True},
        policy=_allow_move_policy(),
        run_id="run-ov",
        run_step_id="step-ov",
    )
    assert result.outcome == "succeeded"
    assert not src.exists()
    assert dst.read_text() == "new-content"

    # The old dst must live in trash and be reachable via dst_trash_ref.
    trash_ref = result.result.output["dst_trash_ref"]
    assert trash_ref is not None
    trashed_path = Path(trash_ref)
    assert trashed_path.exists()
    assert trashed_path.read_text() == "old-content-must-not-be-lost"

    # Journal entry's before-snapshot also carries the trash ref.
    assert len(factory.journal.entries) == 1
    before = factory.journal.entries[0].before or {}
    assert before.get("dst_existed") is True

    # Simulate an undo: restore src from dst, then restore old dst from trash.
    io = rt._io  # type: ignore[attr-defined]
    await io.restore_from_trash(dst, src)  # dst → src
    await io.restore_from_trash(trashed_path, dst)  # trash → dst
    assert src.read_text() == "new-content"
    assert dst.read_text() == "old-content-must-not-be-lost"


async def test_multi_path_policy_denies_when_dst_protected(tmp_path: Path, runtime):
    """H7 regression: PolicyEngine should evaluate BOTH src and dst.

    Here the dst lives under a protected path — the deny rule must fire.
    """
    rt, factory = runtime
    src = tmp_path / "src.txt"
    protected_dir = tmp_path / "protected"
    protected_dir.mkdir()
    dst = protected_dir / "dst.txt"
    src.write_text("secret")

    policy = Policy(
        name="multi-path",
        mode="ask",
        rules=[
            # Deny: anything under protected/**
            PolicyRule(
                priority=5,
                scope="fs_path",
                matcher=f"{protected_dir}/**",
                effect="deny",
            ),
            # Otherwise allow fs.move
            PolicyRule(
                priority=100,
                scope="tool_id",
                matcher="fs.move",
                effect="allow",
            ),
        ],
    )

    with pytest.raises(PolicyViolationError):
        await rt.invoke(
            FsMoveTool(),
            args={"src": str(src), "dst": str(dst)},
            policy=policy,
            run_id="r1",
            run_step_id="s1",
        )
    # Audit recorded blocked
    assert factory.audit.records[-1].status == "blocked"
    # src was not moved
    assert src.exists()
    assert not dst.exists()
