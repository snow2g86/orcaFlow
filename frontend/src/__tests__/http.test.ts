import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

import {
  setSidecarEndpoint,
  getSidecarEndpoint,
  sidecarFetch,
  SidecarHttpError,
} from '@/lib/api/http'

describe('lib/api/http', () => {
  beforeEach(() => {
    setSidecarEndpoint({ port: 9999, token: 'test-token', version: '0.1.0' })
  })

  afterEach(() => {
    setSidecarEndpoint(null)
    vi.restoreAllMocks()
  })

  it('throws when endpoint not set', () => {
    setSidecarEndpoint(null)
    expect(() => getSidecarEndpoint()).toThrow('sidecar endpoint not ready')
  })

  it('returns endpoint when set', () => {
    const ep = getSidecarEndpoint()
    expect(ep.port).toBe(9999)
    expect(ep.token).toBe('test-token')
  })

  it('sends X-Orca-Token header', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ data: 'ok' }),
    })
    vi.stubGlobal('fetch', mockFetch)

    await sidecarFetch('/test')

    expect(mockFetch).toHaveBeenCalledOnce()
    const [url, init] = mockFetch.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('http://127.0.0.1:9999/test')
    const headers = init.headers as Headers
    expect(headers.get('X-Orca-Token')).toBe('test-token')
    expect(headers.get('Content-Type')).toBe('application/json')
  })

  it('converts snake_case response to camelCase', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ run_id: '123', started_at: '2026-01-01' }),
      }),
    )

    const result = await sidecarFetch<{ runId: string; startedAt: string }>('/runs')
    expect(result.runId).toBe('123')
    expect(result.startedAt).toBe('2026-01-01')
  })

  it('throws SidecarHttpError on non-ok response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        json: () =>
          Promise.resolve({
            error: { code: 'not_found', message: 'run not found' },
          }),
      }),
    )

    await expect(sidecarFetch('/runs/bad')).rejects.toThrow(SidecarHttpError)
    try {
      await sidecarFetch('/runs/bad')
    } catch (e) {
      expect(e).toBeInstanceOf(SidecarHttpError)
      const err = e as SidecarHttpError
      expect(err.status).toBe(404)
      expect(err.code).toBe('not_found')
    }
  })

  it('handles json parse failure on error response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        json: () => Promise.reject(new Error('parse fail')),
      }),
    )

    await expect(sidecarFetch('/fail')).rejects.toThrow(SidecarHttpError)
  })
})
