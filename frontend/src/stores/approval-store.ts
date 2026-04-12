import { create } from 'zustand'

import { decideApproval, listPendingApprovals } from '@/lib/api/approval'
import type { ApprovalRequest } from '@/types/approval.types'

type ApprovalStore = {
  pending: ApprovalRequest[]
  error: string | null
  decide: (id: string, decision: 'approve' | 'reject', note?: string) => Promise<void>
  refresh: () => Promise<void>
  addPending: (approval: ApprovalRequest) => void
  removePending: (id: string) => void
}

export const useApprovalStore = create<ApprovalStore>((set) => ({
  pending: [],
  error: null,

  decide: async (id, decision, note) => {
    try {
      await decideApproval(id, decision, note)
      set((s) => ({
        pending: s.pending.filter((a) => a.id !== id),
        error: null,
      }))
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      set({ error: msg })
    }
  },

  refresh: async () => {
    try {
      const pending = await listPendingApprovals()
      set({ pending, error: null })
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      set({ error: msg })
    }
  },

  addPending: (approval) => {
    set((s) => {
      if (s.pending.some((a) => a.id === approval.id)) return s
      return { pending: [...s.pending, approval] }
    })
  },

  removePending: (id) => {
    set((s) => ({
      pending: s.pending.filter((a) => a.id !== id),
    }))
  },
}))
