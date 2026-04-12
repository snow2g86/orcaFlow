// Chat API — POST /chat/sessions, POST /chat/sessions/{id}/turns

import { sidecarPost } from '@/lib/api/http'
import type { PlannerOutput } from '@/types/chat.types'

export async function createChatSession(): Promise<{ sessionId: string }> {
  return sidecarPost<{ sessionId: string }>('/chat/sessions', {})
}

export async function sendChatTurn(
  sessionId: string,
  userText: string,
): Promise<PlannerOutput> {
  return sidecarPost<PlannerOutput>(`/chat/sessions/${sessionId}/turns`, {
    userText,
  })
}
