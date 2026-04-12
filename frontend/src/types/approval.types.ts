// schema.md §3.14 — ApprovalRequest 타입 (camelCase 내부 표현)

export type ApprovalState = 'pending' | 'approved' | 'rejected' | 'expired'

export type ApprovalRequest = {
  id: string
  runStepId: string
  toolCallId?: string
  reason: string
  diffPreview?: Record<string, unknown>
  state: ApprovalState
  decidedAt?: string
  decidedBy?: string
  ttlSeconds: number
}
