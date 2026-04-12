// Sidecar HTTP client singleton.
// Frontend 가 sidecar (127.0.0.1:<port>) 에 직접 fetch 호출한다.
// 토큰은 in-memory 만 보관 (localStorage/sessionStorage 저장 금지).

import { keysToCamel, keysToSnake } from '@/lib/utils/case'
import type { SidecarEndpoint } from '@/types/app.types'

let endpoint: SidecarEndpoint | null = null

export function setSidecarEndpoint(ep: SidecarEndpoint | null): void {
  endpoint = ep
}

export function getSidecarEndpoint(): SidecarEndpoint {
  if (!endpoint) throw new Error('sidecar endpoint not ready')
  return endpoint
}

export class SidecarHttpError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message)
    this.name = 'SidecarHttpError'
  }
}

export async function sidecarFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const ep = getSidecarEndpoint()
  const url = `http://127.0.0.1:${ep.port.toString()}${path}`
  const headers = new Headers(init.headers ?? {})
  headers.set('X-Orca-Token', ep.token)
  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const reqInit: RequestInit = { headers }
  if (init.method) reqInit.method = init.method
  if (init.body !== null && init.body !== undefined) reqInit.body = init.body
  if (init.signal) reqInit.signal = init.signal
  const response = await fetch(url, reqInit)
  if (!response.ok) {
    const body = (await response.json().catch(() => ({
      error: { code: 'unknown', message: response.statusText },
    }))) as { error?: { code?: string; message?: string } }
    throw new SidecarHttpError(
      response.status,
      body.error?.code ?? 'unknown',
      body.error?.message ?? 'error',
    )
  }
  const raw: unknown = await response.json()
  return keysToCamel<T>(raw)
}

/**
 * POST 요청에 body 를 snake_case 로 변환해 전송.
 */
export async function sidecarPost<T>(
  path: string,
  body: Record<string, unknown>,
  init: RequestInit = {},
): Promise<T> {
  return sidecarFetch<T>(path, {
    method: 'POST',
    body: JSON.stringify(keysToSnake(body)),
    signal: init.signal ?? null,
  })
}
