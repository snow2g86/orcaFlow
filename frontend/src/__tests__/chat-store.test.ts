import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

import { setSidecarEndpoint } from '@/lib/api/http'
import { useChatStore } from '@/stores/chat-store'

describe('stores/chat-store', () => {
  beforeEach(() => {
    setSidecarEndpoint({ port: 9999, token: 'test-token', version: '0.1.0' })
    useChatStore.setState({
      sessionId: null,
      turns: [],
      latestPlanner: null,
      pending: false,
      error: null,
    })
  })

  afterEach(() => {
    setSidecarEndpoint(null)
    vi.restoreAllMocks()
  })

  it('newSession creates a session', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ session_id: 'sess-1' }),
      }),
    )

    await useChatStore.getState().newSession()

    expect(useChatStore.getState().sessionId).toBe('sess-1')
    expect(useChatStore.getState().turns).toHaveLength(0)
  })

  it('sendTurn adds turn with planner output', async () => {
    useChatStore.setState({ sessionId: 'sess-1' })

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            intent: 'organize files',
            reasoning: 'user wants to sort files',
            workflow_yaml: 'nodes:\n  - id: n1',
            expected_effects: ['files moved'],
            confidence: 'high',
            questions: [],
          }),
      }),
    )

    await useChatStore.getState().sendTurn('organize my files')

    const state = useChatStore.getState()
    expect(state.turns).toHaveLength(1)
    expect(state.turns[0]?.userText).toBe('organize my files')
    expect(state.latestPlanner).not.toBeNull()
    expect(state.latestPlanner?.intent).toBe('organize files')
    expect(state.latestPlanner?.confidence).toBe('high')
    expect(state.pending).toBe(false)
  })

  it('sendTurn sets error without session', async () => {
    await useChatStore.getState().sendTurn('test')
    expect(useChatStore.getState().error).toBe('no active session')
  })

  it('sendTurn sets error on API failure', async () => {
    useChatStore.setState({ sessionId: 'sess-1' })

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        json: () =>
          Promise.resolve({
            error: { code: 'internal', message: 'planner failed' },
          }),
      }),
    )

    await useChatStore.getState().sendTurn('fail')

    expect(useChatStore.getState().error).toBe('planner failed')
    expect(useChatStore.getState().pending).toBe(false)
  })
})
