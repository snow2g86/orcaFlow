import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

import { setSidecarEndpoint } from '@/lib/api/http'
import { useApprovalStore } from '@/stores/approval-store'

describe('stores/approval-store', () => {
  beforeEach(() => {
    setSidecarEndpoint({ port: 9999, token: 'test-token', version: '0.1.0' })
    useApprovalStore.setState({ pending: [], error: null })
  })

  afterEach(() => {
    setSidecarEndpoint(null)
    vi.restoreAllMocks()
  })

  it('decide removes approval from pending', async () => {
    useApprovalStore.setState({
      pending: [
        {
          id: 'a-1',
          runStepId: 's-1',
          reason: 'destructive action',
          state: 'pending',
          ttlSeconds: 300,
        },
      ],
    })

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            ok: true,
            state: 'approved',
            resumes_run: 'run-1',
          }),
      }),
    )

    await useApprovalStore.getState().decide('a-1', 'approve')

    expect(useApprovalStore.getState().pending).toHaveLength(0)
    expect(useApprovalStore.getState().error).toBeNull()
  })

  it('refresh fetches pending approvals', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve([
            {
              id: 'a-2',
              run_step_id: 's-2',
              reason: 'needs review',
              state: 'pending',
              ttl_seconds: 60,
            },
          ]),
      }),
    )

    await useApprovalStore.getState().refresh()

    expect(useApprovalStore.getState().pending).toHaveLength(1)
    expect(useApprovalStore.getState().pending[0]?.id).toBe('a-2')
  })

  it('addPending adds without duplicates', () => {
    useApprovalStore.getState().addPending({
      id: 'a-3',
      runStepId: 's-3',
      reason: 'test',
      state: 'pending',
      ttlSeconds: 300,
    })
    expect(useApprovalStore.getState().pending).toHaveLength(1)

    // Add same again
    useApprovalStore.getState().addPending({
      id: 'a-3',
      runStepId: 's-3',
      reason: 'test',
      state: 'pending',
      ttlSeconds: 300,
    })
    expect(useApprovalStore.getState().pending).toHaveLength(1)
  })

  it('removePending removes by id', () => {
    useApprovalStore.setState({
      pending: [
        {
          id: 'a-4',
          runStepId: 's-4',
          reason: 'test',
          state: 'pending',
          ttlSeconds: 300,
        },
      ],
    })

    useApprovalStore.getState().removePending('a-4')
    expect(useApprovalStore.getState().pending).toHaveLength(0)
  })
})
