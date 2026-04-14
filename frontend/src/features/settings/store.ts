// Settings Zustand store — providers + LLM profiles.

import { create } from 'zustand'

import * as llmProfileApi from '@/lib/api/llm-profile'
import type { LlmProfileSummary } from '@/lib/api/llm-profile'
import * as providerApi from '@/lib/api/provider'
import type { ProviderKind, ProviderSummary } from '@/lib/api/provider'

type HealthStatus = 'unknown' | 'checking' | 'ok' | 'fail'

type SettingsState = {
  providers: ProviderSummary[]
  providerHealth: Record<string, HealthStatus>
  providerModels: Record<string, string[]>
  profiles: LlmProfileSummary[]
  loading: boolean
  error: string | null

  loadProviders: () => Promise<void>
  addProvider: (data: {
    name: string
    kind: ProviderKind
    baseUrl: string
    apiKey?: string | undefined
  }) => Promise<void>
  deleteProvider: (providerId: string) => Promise<void>
  checkHealth: (providerId: string) => Promise<void>
  fetchModels: (providerId: string) => Promise<void>
  loadProfiles: () => Promise<void>
  deleteProfile: (profileId: string) => Promise<void>
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
  providers: [],
  providerHealth: {},
  providerModels: {},
  profiles: [],
  loading: false,
  error: null,

  loadProviders: async () => {
    set({ loading: true, error: null })
    try {
      const providers = await providerApi.listProviders()
      set({ providers, loading: false })
    } catch (e) {
      set({
        error: e instanceof Error ? e.message : 'Failed to load providers',
        loading: false,
      })
    }
  },

  addProvider: async (data) => {
    set({ error: null })
    try {
      const provider = await providerApi.addProvider(data)
      const { providers } = get()
      set({ providers: [...providers, provider] })
      // Provider 추가 후 자동으로 모델 목록 fetch
      void get().fetchModels(provider.id)
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to add provider'
      set({ error: msg })
      throw e
    }
  },

  deleteProvider: async (providerId) => {
    try {
      await providerApi.deleteProvider(providerId)
      const { providers } = get()
      set({ providers: providers.filter((p) => p.id !== providerId), error: null })
    } catch (e) {
      set({ error: e instanceof Error ? e.message : 'Failed to delete provider' })
    }
  },

  fetchModels: async (providerId) => {
    try {
      const models = await providerApi.listProviderModels(providerId)
      const current = get().providerModels
      set({ providerModels: { ...current, [providerId]: models } })
    } catch {
      const current = get().providerModels
      set({ providerModels: { ...current, [providerId]: [] } })
    }
  },

  checkHealth: async (providerId) => {
    const { providerHealth } = get()
    set({ providerHealth: { ...providerHealth, [providerId]: 'checking' } })
    try {
      const result = await providerApi.checkProviderHealth(providerId)
      const current = get().providerHealth
      set({
        providerHealth: {
          ...current,
          [providerId]: result.ok ? 'ok' : 'fail',
        },
      })
    } catch {
      const current = get().providerHealth
      set({ providerHealth: { ...current, [providerId]: 'fail' } })
    }
  },

  deleteProfile: async (profileId) => {
    try {
      await llmProfileApi.deleteLlmProfile(profileId)
      const { profiles } = get()
      set({ profiles: profiles.filter((p) => p.id !== profileId), error: null })
    } catch (e) {
      set({ error: e instanceof Error ? e.message : 'Failed to delete profile' })
    }
  },

  loadProfiles: async () => {
    try {
      const profiles = await llmProfileApi.listLlmProfiles()
      set({ profiles })
    } catch (e) {
      set({
        error: e instanceof Error ? e.message : 'Failed to load profiles',
      })
    }
  },
}))
