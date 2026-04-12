import { create } from 'zustand'

import { createChatSession, sendChatTurn } from '@/lib/api/chat'
import type { ConversationTurn, PlannerOutput } from '@/types/chat.types'

type ChatStore = {
  sessionId: string | null
  turns: ConversationTurn[]
  latestPlanner: PlannerOutput | null
  pending: boolean
  error: string | null
  newSession: () => Promise<void>
  sendTurn: (text: string) => Promise<void>
}

export const useChatStore = create<ChatStore>((set, get) => ({
  sessionId: null,
  turns: [],
  latestPlanner: null,
  pending: false,
  error: null,

  newSession: async () => {
    try {
      const { sessionId } = await createChatSession()
      set({ sessionId, turns: [], latestPlanner: null, error: null })
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      set({ error: msg })
    }
  },

  sendTurn: async (text) => {
    const { sessionId } = get()
    if (!sessionId) {
      set({ error: 'no active session' })
      return
    }
    set({ pending: true, error: null })
    try {
      const plannerOutput = await sendChatTurn(sessionId, text)
      const turn: ConversationTurn = {
        id: crypto.randomUUID(),
        sessionId,
        userText: text,
        plannerOutput,
        createdAt: new Date().toISOString(),
      }
      set((s) => ({
        turns: [...s.turns, turn],
        latestPlanner: plannerOutput,
        pending: false,
      }))
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      set({ pending: false, error: msg })
    }
  },
}))
