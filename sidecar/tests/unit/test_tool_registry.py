"""ToolRegistry 커버리지 보강 테스트."""

from __future__ import annotations

import pytest

from orca_core.errors import NotFoundError
from orca_core.tools import ToolRegistry
from orca_core.tools.fs import FsReadFileTool, FsWriteFileTool


def test_register_and_get():
    reg = ToolRegistry()
    tool = FsReadFileTool()
    reg.register(tool)
    assert "fs.read_file" in reg
    assert reg.get("fs.read_file") is tool
    assert len(reg) == 1
    assert reg.list_ids() == ["fs.read_file"]
    assert list(reg.values()) == [tool]


def test_contains_non_string_returns_false():
    reg = ToolRegistry()
    assert (42 in reg) is False


def test_get_missing_raises_not_found():
    reg = ToolRegistry()
    with pytest.raises(NotFoundError):
        reg.get("fs.nonexistent")


def test_multiple_tools_listed_sorted():
    reg = ToolRegistry()
    reg.register(FsWriteFileTool())
    reg.register(FsReadFileTool())
    assert reg.list_ids() == ["fs.read_file", "fs.write_file"]
