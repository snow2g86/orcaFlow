"""Policies routes — list, upsert, simulate."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ...errors import NotFoundError
from ...policy.engine import PolicyEngine
from ...schema.policy import Policy
from ..dependencies import AppServices, get_services

router = APIRouter(tags=["policies"])


class Scenario(BaseModel):
    tool_id: str
    args: dict[str, Any] = Field(default_factory=dict)


class SimulateBody(BaseModel):
    policy_id: str
    scenarios: list[Scenario]


@router.get("", summary="list policies")
async def list_policies(
    services: AppServices = Depends(get_services),
) -> list[dict[str, Any]]:
    return [p.model_dump(mode="json") for p in services.policies.values()]


@router.put("/{policy_id}", summary="upsert policy")
async def upsert_policy(
    policy_id: str,
    policy: Policy,
    services: AppServices = Depends(get_services),
) -> dict[str, Any]:
    # Ensure id matches path
    updated = policy.model_copy(update={"id": policy_id})
    services.policies[policy_id] = updated
    return updated.model_dump(mode="json")


@router.post("/simulate", summary="simulate policy decisions")
async def simulate(
    body: SimulateBody,
    services: AppServices = Depends(get_services),
) -> dict[str, Any]:
    policy = services.policies.get(body.policy_id)
    if policy is None:
        raise NotFoundError(f"policy not found: {body.policy_id}")
    engine = PolicyEngine()
    results: list[dict[str, Any]] = []
    for scenario in body.scenarios:
        decision = engine.evaluate(policy, tool_id=scenario.tool_id, args=scenario.args)
        results.append(
            {
                "tool_id": scenario.tool_id,
                "effect": decision.effect,
                "rule_id": decision.rule_id,
                "reason": decision.reason,
            }
        )
    return {"policy_id": body.policy_id, "results": results}
