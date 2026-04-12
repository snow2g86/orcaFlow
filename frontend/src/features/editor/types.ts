// Editor-specific types — React Flow node/edge data.
// schema.md §3.3 AgentNode, §3.4 Edge 대응.
// 글로벌 types/ 오염 금지 규칙에 따라 여기에 정의.

import type { Node, Edge } from '@xyflow/react'

export type AgentNodeData = {
  roleId: string
  label: string
  overrides: Record<string, unknown>
  isEntrypoint: boolean
  tools: string[]
  hasError: boolean
}

export type AgentFlowNode = Node<AgentNodeData, 'agent' | 'entrypoint'>

export type FlowEdgeData = {
  condition: string
  label: string
  hasError: boolean
}

export type AgentFlowEdge = Edge<FlowEdgeData>

/** Workflow JSON representation for editor (camelCase). */
export type WorkflowDefinition = {
  id?: string | undefined
  name: string
  description?: string | undefined
  version: number
  author?: string | undefined
  tags?: string[] | undefined
  nodes: WorkflowNodeDef[]
  edges: WorkflowEdgeDef[]
  entrypointNodeId: string
  policyId?: string | undefined
  defaultLlmProfileId?: string | undefined
}

export type WorkflowNodeDef = {
  id: string
  roleId: string
  label?: string | undefined
  position: { x: number; y: number }
  overrides?: Record<string, unknown> | undefined
}

export type WorkflowEdgeDef = {
  fromNodeId: string
  toNodeId: string
  condition?: string | undefined
  label?: string | undefined
}

export type ValidationError = {
  nodeId?: string | undefined
  edgeIndex?: number | undefined
  message: string
}

export type EditorMode = 'visual' | 'yaml'
