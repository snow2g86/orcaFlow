"""Workflow / AgentNode / Edge / Position (schema.md sections 3.1-3.4)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from ._base import OrcaModel, generate_uuid_v7, utc_now

__all__ = [
    "AgentNode",
    "Edge",
    "Position",
    "Workflow",
]


class Position(OrcaModel):
    """노드 에디터 좌표."""

    x: int
    y: int


class AgentNode(OrcaModel):
    """Workflow 그래프상의 에이전트 인스턴스 (schema.md §3.3).

    `role` 은 AgentRole.name 을 참조한다 (YAML 표기와 일치).
    """

    id: str
    role: str
    label: str | None = None
    position: Position
    overrides: dict[str, Any] = Field(default_factory=dict)
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None


class Edge(OrcaModel):
    """노드 간 유향 간선 (schema.md §3.4).

    `from` 은 Python 예약어라 alias 로 처리한다.
    """

    from_: str = Field(alias="from")
    to: str
    condition: str | None = None
    label: str | None = None


def _collect_unique_node_ids(nodes: list[AgentNode]) -> set[str]:
    if not nodes:
        raise ValueError("Workflow.nodes must be non-empty")
    seen: set[str] = set()
    for node in nodes:
        if node.id in seen:
            raise ValueError(f"Workflow.nodes has duplicate id: {node.id}")
        seen.add(node.id)
    return seen


def _validate_edges(edges: list[Edge], node_ids: set[str]) -> None:
    for edge in edges:
        if edge.from_ not in node_ids:
            raise ValueError(f"Edge.from '{edge.from_}' is not a known node id")
        if edge.to not in node_ids:
            raise ValueError(f"Edge.to '{edge.to}' is not a known node id")
        if edge.from_ == edge.to:
            raise ValueError(
                f"Workflow has self-loop edge on node '{edge.from_}'; Workflow graph must be a DAG"
            )


def _check_acyclic(node_ids: set[str], edges: list[Edge]) -> None:
    """Kahn's algorithm: 사이클 존재 시 ValueError."""
    adjacency: dict[str, list[str]] = {nid: [] for nid in node_ids}
    indegree: dict[str, int] = dict.fromkeys(node_ids, 0)
    for edge in edges:
        adjacency[edge.from_].append(edge.to)
        indegree[edge.to] += 1
    queue: list[str] = [n for n, d in indegree.items() if d == 0]
    visited = 0
    while queue:
        current = queue.pop()
        visited += 1
        for successor in adjacency[current]:
            indegree[successor] -= 1
            if indegree[successor] == 0:
                queue.append(successor)
    if visited != len(node_ids):
        raise ValueError("Workflow graph contains a cycle; Workflow must be a DAG")


class Workflow(OrcaModel):
    """Workflow (schema.md §3.1).

    YAML 직렬화를 1차 포맷으로 삼는다. DB 는 원본 YAML + 정규화 레코드를
    함께 저장한다.
    """

    id: str = Field(default_factory=generate_uuid_v7)
    name: str
    description: str | None = None
    version: Literal[1] = 1
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    author: str | None = None
    tags: list[str] = Field(default_factory=list)
    nodes: list[AgentNode]
    edges: list[Edge]
    entrypoint_node_id: str = Field(alias="entrypoint")
    policy_id: str | None = Field(default=None, alias="policy")
    default_llm_profile_id: str | None = Field(default=None, alias="default_llm_profile")

    @model_validator(mode="after")
    def _validate_graph(self) -> Workflow:
        node_ids = _collect_unique_node_ids(self.nodes)
        if self.entrypoint_node_id not in node_ids:
            raise ValueError(f"Workflow.entrypoint '{self.entrypoint_node_id}' is not in nodes")
        _validate_edges(self.edges, node_ids)
        _check_acyclic(node_ids, self.edges)
        return self
