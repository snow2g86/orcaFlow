// Provider list — Vercel-style table in card.

import { useEffect } from 'react'

import { Button } from '@/components/ui/button'
import { useSettingsStore } from '@/features/settings/store'

type HealthStatus = 'unknown' | 'checking' | 'ok' | 'fail'

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
        <div>
          <h3 className="settings-card__title">Providers</h3>
          <p className="settings-card__desc">Manage LLM provider connections</p>
        </div>
      </div>
      <div className="settings-card__body--flush">
        {providers.length === 0 ? (
          <p className="settings-table__empty">No providers configured</p>
        ) : (
          <table className="settings-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Endpoint</th>
                <th>Models</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {providers.map((p) => {
                const models = providerModels[p.id] ?? []
                const health = (providerHealth[p.id] ?? 'unknown') as HealthStatus
                return (
                  <tr key={p.id}>
                    <td className="cell-name">{p.name}</td>
                    <td className="cell-mono">{p.kind}</td>
                    <td className="cell-mono">{p.baseUrl}</td>
                    <td>{models.length > 0 ? <span className="muted">{models.length}</span> : <span className="muted">-</span>}</td>
                    <td>
                      <span className={`status-dot status-dot--${health}`}>
                        {health}
                      </span>
                    </td>
                    <td className="cell-actions">
                      <div className="settings-table__actions">
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => {
                            void checkHealth(p.id)
                            void fetchModels(p.id)
                          }}
                          disabled={health === 'checking'}
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
    </div>
  )
}
