// React Flow nodes/edges -> Workflow definition + YAML conversion.
// js-yaml 을 사용해 YAML 직렬화.

import yaml from 'js-yaml'

import type {
  AgentFlowEdge,
  AgentFlowNode,
  WorkflowDefinition,
  WorkflowEdgeDef,
  WorkflowNodeDef,
} from '@/features/editor/types'

export function flowToWorkflow(
  nodes: AgentFlowNode[],
  edges: AgentFlowEdge[],
  meta: {
    id?: string | undefined
    name: string
    description?: string | undefined
    version?: number | undefined
    author?: string | undefined
    policyId?: string | undefined
    defaultLlmProfileId?: string | undefined
  },
): WorkflowDefinition {
  const entryNode = nodes.find((n) => (n.data).isEntrypoint)
  const entrypointNodeId = entryNode?.id ?? nodes[0]?.id ?? ''

  const workflowNodes: WorkflowNodeDef[] = nodes.map((n) => {
    const data = n.data
    const def: WorkflowNodeDef = {
      id: n.id,
      roleId: data.roleId,
      position: { x: n.position.x, y: n.position.y },
    }
    if (data.label && data.label !== data.roleId) {
      def.label = data.label
    }
    if (Object.keys(data.overrides).length > 0) {
      def.overrides = data.overrides
    }
    return def
  })

  const workflowEdges: WorkflowEdgeDef[] = edges.map((e) => {
    const def: WorkflowEdgeDef = {
      fromNodeId: e.source,
      toNodeId: e.target,
    }
    if (e.data?.condition) {
      def.condition = e.data.condition
    }
    if (e.data?.label && e.data.label !== e.data.condition) {
      def.label = e.data.label
    }
    return def
  })

  return {
    id: meta.id,
    name: meta.name,
    description: meta.description,
    version: meta.version ?? 1,
    author: meta.author,
    nodes: workflowNodes,
    edges: workflowEdges,
    entrypointNodeId,
    policyId: meta.policyId,
    defaultLlmProfileId: meta.defaultLlmProfileId,
  }
}

/**
 * Workflow definition -> YAML string (snake_case keys for backend).
 */
export function workflowToYaml(workflow: WorkflowDefinition): string {
  // Convert camelCase keys to snake_case for YAML output
  const snakeObj = {
    version: workflow.version,
    name: workflow.name,
    ...(workflow.description ? { description: workflow.description } : {}),
    ...(workflow.author ? { author: workflow.author } : {}),
    ...(workflow.policyId ? { policy_id: workflow.policyId } : {}),
    ...(workflow.defaultLlmProfileId
      ? { default_llm_profile: workflow.defaultLlmProfileId }
      : {}),
    nodes: workflow.nodes.map((n) => ({
      id: n.id,
      role: n.roleId,
      position: n.position,
      ...(n.label ? { label: n.label } : {}),
      ...(n.overrides && Object.keys(n.overrides).length > 0
        ? { overrides: n.overrides }
        : {}),
    })),
    edges: workflow.edges.map((e) => ({
      from: e.fromNodeId,
      to: e.toNodeId,
      ...(e.condition ? { condition: e.condition } : {}),
      ...(e.label ? { label: e.label } : {}),
    })),
    entrypoint: workflow.entrypointNodeId,
  }

  return yaml.dump(snakeObj, { indent: 2, lineWidth: 120, noRefs: true })
}

/**
 * YAML string -> Workflow definition (snake_case -> camelCase).
 */
export function yamlToWorkflow(yamlStr: string): WorkflowDefinition {
  const raw = yaml.load(yamlStr) as Record<string, unknown>
  const rawNodes = (raw['nodes'] as Array<Record<string, unknown>>) ?? []
  const rawEdges = (raw['edges'] as Array<Record<string, unknown>>) ?? []

  return {
    id: raw['id'] as string | undefined,
    name: (raw['name'] as string) ?? 'Untitled',
    description: raw['description'] as string | undefined,
    version: (raw['version'] as number) ?? 1,
    author: raw['author'] as string | undefined,
    policyId: raw['policy_id'] as string | undefined,
    defaultLlmProfileId: raw['default_llm_profile'] as string | undefined,
    entrypointNodeId: (raw['entrypoint'] as string) ?? '',
    nodes: rawNodes.map((n) => ({
      id: n['id'] as string,
      roleId: (n['role'] as string) ?? (n['role_id'] as string) ?? '',
      label: n['label'] as string | undefined,
      position: (n['position'] as { x: number; y: number }) ?? { x: 0, y: 0 },
      overrides: n['overrides'] as Record<string, unknown> | undefined,
    })),
    edges: rawEdges.map((e) => ({
      fromNodeId: (e['from'] as string) ?? (e['from_node_id'] as string) ?? '',
      toNodeId: (e['to'] as string) ?? (e['to_node_id'] as string) ?? '',
      condition: e['condition'] as string | undefined,
      label: e['label'] as string | undefined,
    })),
  }
}
