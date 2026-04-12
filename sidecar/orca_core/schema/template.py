"""WorkflowTemplate / Plugin (schema.md sections 3.18-3.19)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from ._base import OrcaModel, generate_uuid_v7, utc_now

__all__ = ["Plugin", "PluginKind", "WorkflowTemplate"]

PluginKind = Literal["tool", "provider", "role", "policy"]


class WorkflowTemplate(OrcaModel):
    """공유·재사용 위한 워크플로우 템플릿 (schema.md §3.18)."""

    id: str = Field(default_factory=generate_uuid_v7)
    name: str
    description: str | None = None
    author: str | None = None
    yaml: str
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class Plugin(OrcaModel):
    """외부 플러그인 (schema.md §3.19)."""

    id: str = Field(default_factory=generate_uuid_v7)
    name: str
    version: str
    kind: PluginKind
    entrypoint: str
    manifest_path: str
    enabled: bool = True
