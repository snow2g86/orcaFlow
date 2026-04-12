"""Workflows CRUD + validate 라우트."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
import yaml

from ...errors import NotFoundError, ValidationError
from ...schema.workflow import Workflow
from ..dependencies import AppServices, get_services

router = APIRouter(tags=["workflows"])


class WorkflowYamlBody(BaseModel):
    yaml: str = Field(..., min_length=1)


class WorkflowSummary(BaseModel):
    id: str
    name: str
    version: int
    entrypoint: str


def _parse(workflow_yaml: str) -> Workflow:
    try:
        data = yaml.safe_load(workflow_yaml)
    except yaml.YAMLError as exc:
        raise ValidationError(
            f"invalid workflow YAML: {exc}",
            details={"kind": "yaml"},
        ) from exc
    if not isinstance(data, dict):
        raise ValidationError("workflow YAML root must be a mapping")
    try:
        return Workflow.model_validate(data)
    except Exception as exc:  # pydantic ValidationError
        raise ValidationError(f"workflow schema invalid: {exc}") from exc


@router.post("", summary="create workflow from YAML")
async def create_workflow(
    body: WorkflowYamlBody, services: AppServices = Depends(get_services)
) -> dict[str, Any]:
    workflow = _parse(body.yaml)
    services.workflows[workflow.id] = (workflow, body.yaml)
    return workflow.model_dump(by_alias=True, mode="json")


@router.post("/validate", summary="validate workflow YAML")
async def validate_workflow(body: WorkflowYamlBody) -> dict[str, Any]:
    workflow = _parse(body.yaml)
    return {"ok": True, "name": workflow.name, "nodes": len(workflow.nodes)}


@router.get("", summary="list workflows")
async def list_workflows(
    services: AppServices = Depends(get_services),
) -> list[dict[str, Any]]:
    return [
        WorkflowSummary(
            id=wf.id,
            name=wf.name,
            version=wf.version,
            entrypoint=wf.entrypoint_node_id,
        ).model_dump()
        for (wf, _yaml) in services.workflows.values()
    ]


@router.get("/{workflow_id}", summary="get workflow by id")
async def get_workflow(
    workflow_id: str, services: AppServices = Depends(get_services)
) -> dict[str, Any]:
    entry = services.workflows.get(workflow_id)
    if entry is None:
        raise NotFoundError(f"workflow not found: {workflow_id}")
    workflow, yaml_text = entry
    return {
        "yaml": yaml_text,
        "parsed": workflow.model_dump(by_alias=True, mode="json"),
    }


@router.delete("/{workflow_id}", summary="delete workflow")
async def delete_workflow(
    workflow_id: str, services: AppServices = Depends(get_services)
) -> dict[str, Any]:
    if workflow_id not in services.workflows:
        raise NotFoundError(f"workflow not found: {workflow_id}")
    services.workflows.pop(workflow_id)
    return {"ok": True}


# Suppress unused import warning when running tests in isolation
_ = Request
