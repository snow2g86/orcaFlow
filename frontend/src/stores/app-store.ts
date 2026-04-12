import { create } from 'zustand'

import { fetchAppStatus, fetchConfig } from '@/lib/api/app'
import { setSidecarEndpoint } from '@/lib/api/http'
import type { AppConfig, AppStatus, SidecarEndpoint } from '@/types/app.types'

type AppStore = {
  status: AppStatus | null
  config: AppConfig | null
  endpoint: SidecarEndpoint | null
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
}

export const useAppStore = create<AppStore>((set) => ({
  status: null,
  config: null,
  endpoint: null,
  loading: false,
  error: null,
  refresh: async () => {
    set({ loading: true, error: null })
    try {
      const status = await fetchAppStatus()
      let config: AppConfig | null = null
      const ep = status.endpoint
      if (status.sidecar.state === 'ready') {
        config = await fetchConfig()
      }
      setSidecarEndpoint(ep)
      set({ status, config, endpoint: ep, loading: false })
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e)
      set({ error: message, loading: false })
    }
  },
}))
