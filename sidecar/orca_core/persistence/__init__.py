"""Persistence 레이어 — aiosqlite 기반 저장소.

Domain layer (schema/policy/audit/journal) + aiosqlite 만 의존한다.
외부 HTTP/FastAPI 등 의존 금지.
"""

from __future__ import annotations

from .db import Database
from .migrations import CURRENT_VERSION, run_migrations
from .repo import (
    AgentRolesRepository,
    ApprovalsRepository,
    AuditLogsRepository,
    JournalEntriesRepository,
    LLMProfilesRepository,
    PoliciesRepository,
    ProvidersRepository,
    RunsRepository,
    RunStepsRepository,
    ToolCallsRepository,
    WorkflowRow,
    WorkflowsRepository,
)

__all__ = [
    "CURRENT_VERSION",
    "AgentRolesRepository",
    "ApprovalsRepository",
    "AuditLogsRepository",
    "Database",
    "JournalEntriesRepository",
    "LLMProfilesRepository",
    "PoliciesRepository",
    "ProvidersRepository",
    "RunStepsRepository",
    "RunsRepository",
    "ToolCallsRepository",
    "WorkflowRow",
    "WorkflowsRepository",
    "run_migrations",
]
