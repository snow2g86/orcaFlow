// Approval API — GET /approvals/pending, POST /approvals/{id}/decide

import { sidecarFetch, sidecarPost } from '@/lib/api/http'
import type { ApprovalRequest } from '@/types/approval.types'

export async function listPendingApprovals(): Promise<ApprovalRequest[]> {
  return sidecarFetch<ApprovalRequest[]>('/approvals/pending')
}

export async function decideApproval(
  id: string,
  decision: 'approve' | 'reject',
  note?: string,
): Promise<{ ok: boolean; state: string; resumesRun: string | null }> {
  return sidecarPost<{ ok: boolean; state: string; resumesRun: string | null }>(
    `/approvals/${id}/decide`,
    { decision, note },
  )
}
