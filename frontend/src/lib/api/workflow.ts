// Workflow API — POST /workflows, GET /workflows, POST /workflows/validate

import { sidecarFetch, sidecarPost } from '@/lib/api/http'
import type { WorkflowSummary } from '@/types/workflow.types'

export type WorkflowDetailRaw = {
  id: string
  name: string
  description?: string | undefined
  version: number
  author?: string | undefined
  tags?: string[] | undefined
  nodes: Array<{
    id: string
    roleId: string
    label?: string | undefined
    position: { x: number; y: number }
    overrides?: Record<string, unknown> | undefined
  }>
  edges: Array<{
    fromNodeId: string
    toNodeId: string
    condition?: string | undefined
    label?: string | undefined
  }>
  entrypointNodeId: string
  policyId?: string | undefined
  defaultLlmProfileId?: string | undefined
}

export type ValidateResult = {
  ok: boolean
  name: string
  nodes: number
  errors?: Array<{
    nodeId?: string | undefined
    edgeIndex?: number | undefined
    message: string
  }> | undefined
}

export async function createWorkflow(yaml: string): Promise<WorkflowDetailRaw> {
  return sidecarPost<WorkflowDetailRaw>('/workflows', { yaml })
}

export async function listWorkflows(): Promise<WorkflowSummary[]> {
  return sidecarFetch<WorkflowSummary[]>('/workflows')
}

export async function getWorkflow(id: string): Promise<WorkflowDetailRaw> {
  return sidecarFetch<WorkflowDetailRaw>(`/workflows/${id}`)
}

export async function validateWorkflow(
  yaml: string,
): Promise<ValidateResult> {
  return sidecarPost<ValidateResult>('/workflows/validate', { yaml })
}
