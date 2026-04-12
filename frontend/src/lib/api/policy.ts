// Policy API — GET/PUT /policies, POST /policies/simulate

import { sidecarFetch, sidecarPost } from '@/lib/api/http'
import type { PolicySummary } from '@/types/policy.types'

export type PolicyRuleRaw = {
  id: string
  policyId: string
  priority: number
  scope: string
  matcher: string
  effect: string
  reason?: string | undefined
}

export type PolicyDetailRaw = {
  id: string
  name: string
  mode: string
  rules: PolicyRuleRaw[]
  requireDryRunFor?: string[] | undefined
  autoApproveReversible?: boolean | undefined
}

export type SimulateRequest = {
  scenarios: Array<{
    toolId: string
    args: Record<string, unknown>
  }>
}

export type SimulateResult = {
  toolId: string
  effect: string
  ruleId: string | null
  reason: string
}

export async function listPolicies(): Promise<PolicySummary[]> {
  return sidecarFetch<PolicySummary[]>('/policies')
}

export async function getPolicy(id: string): Promise<PolicyDetailRaw> {
  return sidecarFetch<PolicyDetailRaw>(`/policies/${id}`)
}

export async function updatePolicy(
  id: string,
  yaml: string,
): Promise<PolicyDetailRaw> {
  return sidecarFetch<PolicyDetailRaw>(`/policies/${id}`, {
    method: 'PUT',
    body: JSON.stringify({ yaml }),
  })
}

export async function simulatePolicy(
  policyId: string,
  request: SimulateRequest,
): Promise<SimulateResult[]> {
  return sidecarPost<SimulateResult[]>(
    `/policies/${policyId}/simulate`,
    request as unknown as Record<string, unknown>,
  )
}
