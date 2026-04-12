"""Approval routes — list pending + decide."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...errors import NotFoundError
from ..dependencies import AppServices, get_services

router = APIRouter(tags=["approvals"])


class ApprovalDecisionBody(BaseModel):
    decision: Literal["approve", "reject"]
    note: str | None = Field(default=None)


@router.get("/pending", summary="list pending approvals")
async def list_pending(
    services: AppServices = Depends(get_services),
) -> list[dict[str, Any]]:
    return [a.model_dump(mode="json") for a in services.approvals.values() if a.state == "pending"]


@router.post("/{approval_id}/decide", summary="approve or reject an approval")
async def decide(
    approval_id: str,
    body: ApprovalDecisionBody,
    services: AppServices = Depends(get_services),
) -> dict[str, Any]:
    approval = services.approvals.get(approval_id)
    if approval is None:
        raise NotFoundError(f"approval not found: {approval_id}")
    # H13: guard against double-decide / expired. Only pending can transition.
    if approval.state != "pending":
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "approval.already_decided",
                    "message": f"approval is in state {approval.state}",
                    "details": {"state": approval.state},
                }
            },
        )
    # Locate the owning run handle
    target_handle = None
    target_run_id: str | None = None
    for rid, handle in services.runs.items():
        if approval_id in handle.pending_approvals:
            target_handle = handle
            target_run_id = rid
            break
    if target_handle is None:
        raise NotFoundError(f"no run is awaiting approval: {approval_id}")

    new_state: str = "approved" if body.decision == "approve" else "rejected"
    # H13: update state + dict BEFORE setting the event so any racing
    # observer sees a consistent post-decision snapshot.
    updated = approval.model_copy(
        update={
            "state": new_state,
            "decided_at": datetime.now(tz=UTC),
            "decided_by": "user",
        }
    )
    services.approvals[approval_id] = updated
    if body.decision == "approve":
        target_handle.approve(approval_id)
    else:
        target_handle.reject(approval_id)
    return {"ok": True, "state": new_state, "resumes_run": target_run_id}
