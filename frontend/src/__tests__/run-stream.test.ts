import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

import { setSidecarEndpoint } from '@/lib/api/http'
import { subscribeRunEvents } from '@/lib/ipc/run-stream'
import type { RunEvent } from '@/types/event.types'

function createMockSSEResponse(frames: string): {
  ok: boolean
  status: number
  body: ReadableStream<Uint8Array>
} {
  const encoder = new TextEncoder()
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(encoder.encode(frames))
      controller.close()
    },
  })
  return { ok: true, status: 200, body: stream }
}

describe('lib/ipc/run-stream', () => {
  beforeEach(() => {
    setSidecarEndpoint({ port: 9999, token: 'test-token', version: '0.1.0' })
  })

  afterEach(() => {
    setSidecarEndpoint(null)
    vi.restoreAllMocks()
  })

  it('parses id, event, data frames', async () => {
    const sseData = [
      ': stream open',
      '',
      'id: 1',
      'event: run.started',
      'data: {"run_id":"r1"}',
      '',
      'id: 2',
      'event: run_step.started',
      'data: {"step_id":"s1","kind":"tool_call"}',
      '',
    ].join('\n')

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(createMockSSEResponse(sseData)))

    const events: RunEvent[] = []
    const unsub = subscribeRunEvents('r1', {
      onEvent: (e) => events.push(e),
    })

    // Wait for stream processing
    await new Promise((resolve) => setTimeout(resolve, 100))
    unsub()

    expect(events).toHaveLength(2)
    expect(events[0]?.event).toBe('run.started')
    expect(events[0]?.id).toBe(1)
    expect(events[1]?.event).toBe('run_step.started')
    expect(events[1]?.id).toBe(2)
  })

  it('skips keep-alive comment lines', async () => {
    const sseData = [
      ': stream open',
      '',
      ': ping',
      '',
      'id: 1',
      'event: run.started',
      'data: {"run_id":"r1"}',
      '',
      ': ping',
      '',
    ].join('\n')

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(createMockSSEResponse(sseData)))

    const events: RunEvent[] = []
    const unsub = subscribeRunEvents('r1', {
      onEvent: (e) => events.push(e),
    })

    await new Promise((resolve) => setTimeout(resolve, 100))
    unsub()

    expect(events).toHaveLength(1)
    expect(events[0]?.event).toBe('run.started')
  })

  it('parses run.gap event correctly', async () => {
    const sseData = [
      'id: 5',
      'event: run.gap',
      'data: {"from":2,"to":5,"reason":"buffer_overflow"}',
      '',
    ].join('\n')

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(createMockSSEResponse(sseData)))

    const events: RunEvent[] = []
    const unsub = subscribeRunEvents('r1', {
      onEvent: (e) => events.push(e),
    })

    await new Promise((resolve) => setTimeout(resolve, 100))
    unsub()

    expect(events).toHaveLength(1)
    expect(events[0]?.event).toBe('run.gap')
    expect(events[0]?.payload['reason']).toBe('buffer_overflow')
  })

  it('parses run_step.failed event correctly', async () => {
    const sseData = [
      'id: 3',
      'event: run_step.failed',
      'data: {"step_id":"s1","error":"timeout"}',
      '',
    ].join('\n')

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(createMockSSEResponse(sseData)))

    const events: RunEvent[] = []
    const unsub = subscribeRunEvents('r1', {
      onEvent: (e) => events.push(e),
    })

    await new Promise((resolve) => setTimeout(resolve, 100))
    unsub()

    expect(events).toHaveLength(1)
    expect(events[0]?.event).toBe('run_step.failed')
  })

  it('parses approval.expired event correctly', async () => {
    const sseData = [
      'id: 4',
      'event: approval.expired',
      'data: {"approval_id":"a1","tool_id":"fs.delete"}',
      '',
    ].join('\n')

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(createMockSSEResponse(sseData)))

    const events: RunEvent[] = []
    const unsub = subscribeRunEvents('r1', {
      onEvent: (e) => events.push(e),
    })

    await new Promise((resolve) => setTimeout(resolve, 100))
    unsub()

    expect(events).toHaveLength(1)
    expect(events[0]?.event).toBe('approval.expired')
    expect(events[0]?.payload['approval_id']).toBe('a1')
  })

  it('retries on fetch failure with backoff', async () => {
    let callCount = 0
    const mockFetch = vi.fn().mockImplementation(() => {
      callCount++
      if (callCount <= 2) {
        return Promise.reject(new Error('network error'))
      }
      return Promise.resolve(
        createMockSSEResponse(
          ['id: 1', 'event: run.started', 'data: {"run_id":"r1"}', ''].join('\n'),
        ),
      )
    })
    vi.stubGlobal('fetch', mockFetch)

    const events: RunEvent[] = []
    const unsub = subscribeRunEvents('r1', {
      onEvent: (e) => events.push(e),
    })

    // Wait for retries (1s + 2s + processing)
    await new Promise((resolve) => setTimeout(resolve, 4000))
    unsub()

    expect(callCount).toBe(3)
    expect(events).toHaveLength(1)
  }, 10000)

  it('calls onClose when stream ends normally', async () => {
    const sseData = ['id: 1', 'event: run.succeeded', 'data: {"run_id":"r1"}', ''].join(
      '\n',
    )

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(createMockSSEResponse(sseData)))

    const onClose = vi.fn()
    const unsub = subscribeRunEvents('r1', {
      onEvent: () => {},
      onClose,
    })

    await new Promise((resolve) => setTimeout(resolve, 100))
    unsub()

    expect(onClose).toHaveBeenCalled()
  })

  it('sends token as query parameter', async () => {
    const mockFetch = vi.fn().mockResolvedValue(
      createMockSSEResponse(''),
    )
    vi.stubGlobal('fetch', mockFetch)

    const unsub = subscribeRunEvents('r1', {
      onEvent: () => {},
    })

    await new Promise((resolve) => setTimeout(resolve, 100))
    unsub()

    expect(mockFetch).toHaveBeenCalled()
    const [url] = mockFetch.mock.calls[0] as [string]
    expect(url).toContain('token=test-token')
  })
})
