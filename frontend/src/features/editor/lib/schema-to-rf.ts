// Workflow definition -> React Flow nodes/edges conversion.
// Position 보존. entrypoint 노드에 isEntrypoint 플래그 설정.

import type {
  AgentFlowEdge,
  AgentFlowNode,
  AgentNodeData,
  FlowEdgeData,
  WorkflowDefinition,
} from '@/features/editor/types'

export function workflowToFlowNodes(
  workflow: WorkflowDefinition,
): AgentFlowNode[] {
  return workflow.nodes.map((node) => {
    const data: AgentNodeData = {
      roleId: node.roleId,
      label: node.label ?? node.roleId,
      overrides: node.overrides ?? {},
      isEntrypoint: node.id === workflow.entrypointNodeId,
      tools: Array.isArray((node.overrides ?? {})['tools'])
        ? ((node.overrides ?? {})['tools'] as string[])
        : [],
      hasError: false,
    }
    return {
      id: node.id,
      type: node.id === workflow.entrypointNodeId ? 'entrypoint' : 'agent',
      position: { x: node.position.x, y: node.position.y },
      data,
    }
  })
}

export function workflowToFlowEdges(
  workflow: WorkflowDefinition,
): AgentFlowEdge[] {
  return workflow.edges.map((edge, index) => {
    const edgeData: FlowEdgeData = {
      condition: edge.condition ?? '',
      label: edge.label ?? edge.condition ?? '',
      hasError: false,
    }
    return {
      id: `e-${edge.fromNodeId}-${edge.toNodeId}-${index.toString()}`,
      source: edge.fromNodeId,
      target: edge.toNodeId,
      label: edge.condition ?? undefined,
      data: edgeData,
    }
  })
}

export function workflowToFlow(workflow: WorkflowDefinition): {
  nodes: AgentFlowNode[]
  edges: AgentFlowEdge[]
} {
  return {
    nodes: workflowToFlowNodes(workflow),
    edges: workflowToFlowEdges(workflow),
  }
}
