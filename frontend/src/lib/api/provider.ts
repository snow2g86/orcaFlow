// Provider API — GET/POST /providers, GET /providers/{id}/health

import { sidecarFetch, sidecarPost } from '@/lib/api/http'

export type ProviderKind =
  | 'ollama'
  | 'vllm'
  | 'llama_cpp'
  | 'lm_studio'
  | 'tgi'
  | 'openai_compatible'
  | 'together'
  | 'groq'
  | 'fireworks'

export type ProviderSummary = {
  id: string
  name: string
  kind: ProviderKind
  baseUrl: string
}

export type ProviderHealthResult = {
  ok: boolean
  message?: string | undefined
}

export async function listProviders(): Promise<ProviderSummary[]> {
  return sidecarFetch<ProviderSummary[]>('/providers')
}

export async function addProvider(data: {
  name: string
  kind: ProviderKind
  baseUrl: string
  apiKey?: string | undefined
}): Promise<ProviderSummary> {
  return sidecarPost<ProviderSummary>('/providers', data as Record<string, unknown>)
}

export async function checkProviderHealth(
  providerId: string,
): Promise<ProviderHealthResult> {
  return sidecarFetch<ProviderHealthResult>(`/providers/${providerId}/health`)
}
