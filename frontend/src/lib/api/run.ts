// Run API — POST /runs, GET /runs/{id}, POST /runs/{id}/cancel

import { sidecarFetch, sidecarPost } from '@/lib/api/http'
import type { RunStartRequest, RunSummary } from '@/types/run.types'

type StartRunResponse = {
  runId: string
  status: string
  startedAt: string
}

export async function startRun(req: RunStartRequest): Promise<StartRunResponse> {
  return sidecarPost<StartRunResponse>('/runs', {
    workflowId: req.workflowId,
    input: req.input ?? {},
    dryRun: req.dryRun ?? false,
    overridePolicyId: req.overridePolicyId,
  })
}

export async function getRun(runId: string): Promise<RunSummary & Record<string, unknown>> {
  return sidecarFetch<RunSummary & Record<string, unknown>>(`/runs/${runId}`)
}

export async function cancelRun(
  runId: string,
): Promise<{ ok: boolean; status: string }> {
  return sidecarPost<{ ok: boolean; status: string }>(`/runs/${runId}/cancel`, {})
}
