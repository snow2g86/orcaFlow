import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

import { setSidecarEndpoint } from '@/lib/api/http'
import { useRunStore } from '@/stores/run-store'

describe('stores/run-store', () => {
  beforeEach(() => {
    setSidecarEndpoint({ port: 9999, token: 'test-token', version: '0.1.0' })
    // Reset store
    useRunStore.setState({
      runs: {},
      liveRun: null,
      error: null,
    })
  })

  afterEach(() => {
    setSidecarEndpoint(null)
    vi.restoreAllMocks()
  })

  it('startRun calls API and updates store', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            run_id: 'run-123',
            status: 'pending',
            started_at: '2026-01-01T00:00:00Z',
          }),
      }),
    )

    const runId = await useRunStore.getState().startRun({
      workflowId: 'wf-1',
    })

    expect(runId).toBe('run-123')
    const state = useRunStore.getState()
    expect(state.runs['run-123']).toBeDefined()
    expect(state.runs['run-123']?.status).toBe('pending')
    expect(state.runs['run-123']?.workflowId).toBe('wf-1')
  })

  it('startRun sets error on failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        json: () =>
          Promise.resolve({
            error: { code: 'not_found', message: 'workflow not found' },
          }),
      }),
    )

    await expect(
      useRunStore.getState().startRun({ workflowId: 'bad' }),
    ).rejects.toThrow()

    expect(useRunStore.getState().error).toBe('workflow not found')
  })

  it('cancelRun updates status', async () => {
    useRunStore.setState({
      runs: {
        'run-1': {
          runId: 'run-1',
          workflowId: 'wf-1',
          status: 'running',
          startedAt: '2026-01-01T00:00:00Z',
        },
      },
    })

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ ok: true, status: 'cancelling' }),
      }),
    )

    await useRunStore.getState().cancelRun('run-1')

    expect(useRunStore.getState().runs['run-1']?.status).toBe('cancelled')
  })

  it('fetchRun updates run summary', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            run_id: 'run-2',
            workflow_id: 'wf-2',
            status: 'succeeded',
            started_at: '2026-01-01T00:00:00Z',
            ended_at: '2026-01-01T00:01:00Z',
            events: [],
          }),
      }),
    )

    await useRunStore.getState().fetchRun('run-2')

    const run = useRunStore.getState().runs['run-2']
    expect(run).toBeDefined()
    expect(run?.status).toBe('succeeded')
  })
})
