// SSE fetch+stream 파서 — browser ReadableStream 기반.
// M4 H14: ?token=<TOKEN> query 파라미터 전달.
// Last-Event-ID, 자동 재연결 (1s/2s/4s backoff, max 3), keep-alive skip.

import { getSidecarEndpoint } from '@/lib/api/http'
import type { RunEvent } from '@/types/event.types'

export type RunStreamOptions = {
  onEvent: (event: RunEvent) => void
  onError?: (error: Error) => void
  onClose?: () => void
  signal?: AbortSignal
}

const MAX_RETRIES = 3
const BACKOFF_BASE_MS = 1000

export function subscribeRunEvents(runId: string, opts: RunStreamOptions): () => void {
  const controller = new AbortController()
  let lastEventId: number | null = null
  let retryCount = 0
  let stopped = false

  // Chain external signal
  if (opts.signal) {
    opts.signal.addEventListener('abort', () => {
      stopped = true
      controller.abort()
    })
  }

  const connect = (): void => {
    if (stopped) return

    const ep = getSidecarEndpoint()
    const url = `http://127.0.0.1:${ep.port.toString()}/runs/${runId}/events?token=${encodeURIComponent(ep.token)}`

    const headers: Record<string, string> = {}
    if (lastEventId !== null) {
      headers['Last-Event-ID'] = lastEventId.toString()
    }

    fetch(url, {
      method: 'GET',
      headers,
      signal: controller.signal,
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`SSE response ${response.status.toString()}`)
        }
        if (!response.body) {
          throw new Error('SSE response has no body')
        }
        // Reset retry count on successful connection
        retryCount = 0
        return readStream(response.body)
      })
      .then(() => {
        if (!stopped) {
          opts.onClose?.()
        }
      })
      .catch((err: unknown) => {
        if (stopped || controller.signal.aborted) return
        const error = err instanceof Error ? err : new Error(String(err))
        if (retryCount < MAX_RETRIES) {
          retryCount++
          const delay = BACKOFF_BASE_MS * Math.pow(2, retryCount - 1)
          setTimeout(() => {
            connect()
          }, delay)
        } else {
          opts.onError?.(error)
        }
      })
  }

  const readStream = async (body: ReadableStream<Uint8Array>): Promise<void> => {
    const reader = body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    // SSE fields accumulator
    let eventId: string | null = null
    let eventType: string | null = null
    let dataLines: string[] = []

    const dispatchEvent = (): void => {
      if (dataLines.length === 0) return
      const dataStr = dataLines.join('\n')
      const id = eventId ? parseInt(eventId, 10) : 0
      try {
        const payload = JSON.parse(dataStr) as Record<string, unknown>
        const ev: RunEvent = {
          id,
          event: eventType ?? 'message',
          payload,
          at: typeof payload['at'] === 'string' ? payload['at'] : new Date().toISOString(),
        }
        if (!isNaN(id) && id > 0) {
          lastEventId = id
        }
        opts.onEvent(ev)
      } catch {
        // Skip unparseable frames
      }
      // Reset
      eventId = null
      eventType = null
      dataLines = []
    }

    try {
      while (true) {
        if (stopped) break
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        // Last element may be incomplete
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (line === '') {
            // Empty line = end of event
            dispatchEvent()
          } else if (line.startsWith(':')) {
            // Comment (keep-alive `: ping`) — skip
            continue
          } else if (line.startsWith('id:')) {
            eventId = line.slice(3).trim()
          } else if (line.startsWith('event:')) {
            eventType = line.slice(6).trim()
          } else if (line.startsWith('data:')) {
            dataLines.push(line.slice(5).trim())
          }
        }
      }
      // Flush any remaining event
      dispatchEvent()
    } finally {
      reader.releaseLock()
    }
  }

  connect()

  return () => {
    stopped = true
    controller.abort()
  }
}
