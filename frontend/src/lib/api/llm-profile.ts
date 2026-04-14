// LLM Profile API — GET/POST/PUT /llm-profiles

import { sidecarFetch, sidecarPost } from '@/lib/api/http'

export type LlmProfileSummary = {
  id: string
  name: string
  providerId: string
  model: string
  isPlanner: boolean
  isDefault: boolean
}

export type LlmProfileDetail = {
  id: string
  name: string
  providerId: string
  model: string
  params: {
    temperature?: number | undefined
    maxTokens?: number | undefined
    topP?: number | undefined
  }
  isToolCapable: boolean
  isPlanner: boolean
  isDefault: boolean
}

export async function listLlmProfiles(): Promise<LlmProfileSummary[]> {
  return sidecarFetch<LlmProfileSummary[]>('/llm-profiles')
}

export async function getLlmProfile(id: string): Promise<LlmProfileDetail> {
  return sidecarFetch<LlmProfileDetail>(`/llm-profiles/${id}`)
}

export async function createLlmProfile(
  data: Omit<LlmProfileDetail, 'id'>,
): Promise<LlmProfileDetail> {
  return sidecarPost<LlmProfileDetail>('/llm-profiles', data as Record<string, unknown>)
}

export async function deleteLlmProfile(id: string): Promise<void> {
  await sidecarFetch(`/llm-profiles/${id}`, { method: 'DELETE' })
}

export async function updateLlmProfile(
  id: string,
  data: Partial<Omit<LlmProfileDetail, 'id'>>,
): Promise<LlmProfileDetail> {
  return sidecarFetch<LlmProfileDetail>(`/llm-profiles/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}
