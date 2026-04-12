"""Tool·Permission 관련 Pydantic 모델 (schema.md §3.5)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from ._base import OrcaModel

__all__ = [
    "Permission",
    "PermissionAction",
    "PermissionKind",
    "SideEffect",
    "Tool",
    "ToolNamespace",
]

ToolNamespace = Literal["fs", "shell", "browser", "os", "web", "custom"]
"""툴 네임스페이스 (schema.md §3.5)."""

SideEffect = Literal["none", "read", "write", "destructive", "network"]
"""툴 부작용 분류."""

PermissionKind = Literal[
    "fs_path",
    "shell_command",
    "network_host",
    "os_api",
    "clipboard",
]
"""툴이 요구하는 권한 종류."""

PermissionAction = Literal["read", "write", "delete", "execute"]
"""권한 동작."""


class Permission(OrcaModel):
    """툴이 요구하는 단일 권한 엔트리.

    schema.md §3.5 의 Permission 구조:

    ```yaml
    permissions:
      - kind: fs_path
        scope: "~/Documents/**"
        action: read
    ```
    """

    kind: PermissionKind
    scope: str
    action: PermissionAction


class Tool(OrcaModel):
    """Tool 정의 (내장 + 사용자 플러그인).

    주의: schema.md §3.5 에서 `id = namespace.name` 형식을 요구하므로
    `model_validator` 로 ID 일관성을 강제한다.
    """

    id: str = Field(..., description="`<namespace>.<name>` (예: fs.read_file)")
    namespace: ToolNamespace
    name: str
    display_name: str | None = None
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] | None = None
    permissions: list[Permission] = Field(default_factory=list)
    side_effect: SideEffect
    reversible: bool
    default_dry_run: bool
    plugin_id: str | None = None

    @model_validator(mode="after")
    def _validate_id_matches_namespace_name(self) -> Tool:
        expected = f"{self.namespace}.{self.name}"
        if self.id != expected:
            raise ValueError(
                f"Tool.id must be '{expected}' (got '{self.id}'); format is '<namespace>.<name>'"
            )
        return self

    @model_validator(mode="after")
    def _validate_destructive_requires_dry_run(self) -> Tool:
        if self.side_effect in ("write", "destructive") and not self.default_dry_run:
            raise ValueError(
                f"Tool '{self.id}' with side_effect='{self.side_effect}' must have "
                "default_dry_run=True (invariant: destructive/write tools must default "
                "to dry-run)."
            )
        return self
