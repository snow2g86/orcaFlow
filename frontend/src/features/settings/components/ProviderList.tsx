// Provider list with health status — card layout.

import { useEffect } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useSettingsStore } from '@/features/settings/store'

const HEALTH_BADGE: Record<string, 'default' | 'success' | 'error' | 'info'> = {
  unknown: 'default',
  checking: 'info',
  ok: 'success',
  fail: 'error',
}

export function ProviderList() {
  const { providers, providerHealth, providerModels, loading, loadProviders, checkHealth, fetchModels, deleteProvider } =
    useSettingsStore()

  useEffect(() => {
    void loadProviders().then(() => {
      const current = useSettingsStore.getState().providers
      for (const p of current) {
        void checkHealth(p.id)
        void fetchModels(p.id)
      }
    })
  }, [loadProviders, checkHealth, fetchModels])

  if (loading) return <p className="muted">Loading providers...</p>

  return (
    <div className="settings-card">
      <div className="settings-card__header">
        <h3 className="settings-card__title">Providers</h3>
        <Badge variant="default">{providers.length}</Badge>
      </div>
      {providers.length === 0 ? (
        <div className="settings-card__body">
          <p className="muted" style={{ textAlign: 'center', margin: 0 }}>
            No providers configured. Add one below.
          </p>
        </div>
      ) : (
        <table className="settings-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Kind</th>
              <th>Endpoint</th>
              <th>Models</th>
              <th>Health</th>
              <th style={{ width: 1 }}></th>
            </tr>
          </thead>
          <tbody>
            {providers.map((p) => {
              const models = providerModels[p.id] ?? []
              return (
                <tr key={p.id}>
                  <td style={{ fontWeight: 500 }}>{p.name}</td>
                  <td><code>{p.kind}</code></td>
                  <td><code>{p.baseUrl}</code></td>
                  <td>
                    <span className="muted">{models.length > 0 ? `${models.length} models` : '-'}</span>
                  </td>
                  <td>
                    <Badge variant={HEALTH_BADGE[providerHealth[p.id] ?? 'unknown'] ?? 'default'}>
                      {providerHealth[p.id] ?? 'unknown'}
                    </Badge>
                  </td>
                  <td>
                    <div className="settings-table__actions">
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => {
                          void checkHealth(p.id)
                          void fetchModels(p.id)
                        }}
                        disabled={providerHealth[p.id] === 'checking'}
                      >
                        Test
                      </Button>
                      <button
                        className="settings-delete-btn"
                        onClick={() => void deleteProvider(p.id)}
                        title="Delete provider"
                      >
                        &#x2715;
                      </button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}
