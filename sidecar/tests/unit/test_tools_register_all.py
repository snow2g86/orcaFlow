"""register_all — 전체 내장 툴 등록 테스트."""

from __future__ import annotations

from orca_core.tools.register_all import create_default_registry


def test_registers_17_tools():
    registry = create_default_registry()
    assert len(registry) == 17  # 5 fs + 1 shell + 4 browser + 5 os + 2 web


def test_all_tool_ids():
    registry = create_default_registry()
    ids = registry.list_ids()
    expected = [
        "browser.click",
        "browser.navigate",
        "browser.open",
        "browser.scrape",
        "fs.delete",
        "fs.list",
        "fs.move",
        "fs.read_file",
        "fs.write_file",
        "os.applescript",
        "os.clipboard_read",
        "os.clipboard_write",
        "os.notify",
        "os.powershell",
        "shell.exec",
        "web.http_request",
        "web.search",
    ]
    assert ids == expected


def test_all_tools_have_required_attributes():
    registry = create_default_registry()
    for tool in registry.values():
        assert hasattr(tool, "id")
        assert hasattr(tool, "namespace")
        assert hasattr(tool, "side_effect")
        assert hasattr(tool, "reversible")
        assert hasattr(tool, "default_dry_run")
        assert hasattr(tool, "timeout_ms")
        assert hasattr(tool, "max_output_bytes")
        assert callable(tool.input_schema)
        assert callable(tool.output_schema)
        assert callable(tool.permissions)
        assert callable(tool.run)
        assert callable(tool.dry_run)
