// schema.md §3.10, §3.11 — Run / RunStep 타입 (camelCase 내부 표현)

export type RunStatus =
  | 'pending'
  | 'running'
  | 'awaiting_approval'
  | 'succeeded'
  | 'failed'
  | 'cancelled'

export type RunTrigger = 'chat' | 'manual' | 'scheduled' | 'api'

export type RunSummary = {
  runId: string
  workflowId: string
  status: RunStatus
  startedAt: string
  endedAt?: string
  error?: { code: string; message: string }
}

export type RunStepKind = 'llm_call' | 'tool_call' | 'route' | 'approval' | 'dry_run'
export type RunStepStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'blocked'

export type RunStepNode = {
  id: string
  runId: string
  parentStepId?: string
  nodeId?: string
  kind: RunStepKind
  status: RunStepStatus
  startedAt: string
  endedAt?: string
  durationMs?: number
  tokensIn?: number
  tokensOut?: number
  payload: Record<string, unknown>
  result?: Record<string, unknown>
  children: string[]
}

export type RunStartRequest = {
  workflowId: string
  input?: Record<string, unknown>
  dryRun?: boolean
  overridePolicyId?: string
}
