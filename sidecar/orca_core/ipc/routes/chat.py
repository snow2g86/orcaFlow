"""Chat sessions + turns routes — in-memory planner interface."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ...errors import NotFoundError
from ...orchestrator import Planner
from ...schema._base import generate_uuid_v7
from ...schema.policy import Policy
from ...schema.run import ConversationTurn
from ..dependencies import (
    SYNTHETIC_FALLBACK_POLICY,
    AppServices,
    ChatSession,
    get_services,
)

router = APIRouter(tags=["chat"])

_logger = logging.getLogger("orca_core.ipc.chat")


class TurnBody(BaseModel):
    user_text: str = Field(..., min_length=1)


@router.post("/sessions", summary="create chat session", status_code=201)
async def create_session(services: AppServices = Depends(get_services)) -> dict[str, Any]:
    session = ChatSession(id=generate_uuid_v7())
    services.chat_sessions[session.id] = session
    return {"session_id": session.id}


@router.post("/sessions/{session_id}/turns", summary="send a planner turn")
async def send_turn(
    session_id: str,
    body: TurnBody,
    services: AppServices = Depends(get_services),
) -> dict[str, Any]:
    session = services.chat_sessions.get(session_id)
    if session is None:
        raise NotFoundError(f"chat session not found: {session_id}")
    profile = _select_planner_profile(services)
    adapter = services.provider_registry.get(profile.provider_id)

    planner = Planner(adapter=adapter, profile=profile)
    policy = _default_policy(services)
    turn = ConversationTurn(session_id=session_id, user_text=body.user_text)
    # M8: guard against races where `list_ids()` returns an id that is
    # evicted before `get()` is called. Keep only successfully-fetched tools.
    tools_map: dict[str, Any] = {}
    for tid in services.tool_registry.list_ids():
        try:
            tool = services.tool_registry.get(tid)
        except Exception:
            _logger.debug(
                "chat.tool_lookup_missing",
                extra={"event": "chat.tool_lookup_missing", "tool_id": tid},
            )
            continue
        if tool is not None:
            tools_map[tid] = tool
    output = await planner.plan(
        turn,
        roles=services.roles,
        tools=tools_map,
        policy=policy,
    )
    session.turns.append({"user": body.user_text, "planner": output.model_dump()})
    return output.model_dump()


def _select_planner_profile(services: AppServices) -> Any:
    planner = [p for p in services.llm_profiles.values() if p.is_planner]
    if planner:
        return planner[0]
    default = [p for p in services.llm_profiles.values() if p.is_default]
    if default:
        return default[0]
    if services.llm_profiles:
        return next(iter(services.llm_profiles.values()))
    raise NotFoundError("no llm_profile configured")


def _default_policy(services: AppServices) -> Policy:
    if services.default_policy_id and services.default_policy_id in services.policies:
        return services.policies[services.default_policy_id]
    if services.policies:
        return next(iter(services.policies.values()))
    # H9: identical fallback to runs.resolve_policy — strict, not ask.
    _logger.warning(
        "policy.synthetic_fallback_used",
        extra={"event": "policy.synthetic_fallback_used", "caller": "chat._default_policy"},
    )
    return SYNTHETIC_FALLBACK_POLICY
