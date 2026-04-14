// Provider list with health status.

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
  const { providers, providerHealth, loading, loadProviders, checkHealth, fetchModels, deleteProvider } =
    useSettingsStore()

  useEffect(() => {
    void loadProviders().then(() => {
      // 로드 후 모든 provider 자동 헬스체크 + 모델 fetch
      const current = useSettingsStore.getState().providers
      for (const p of current) {
        void checkHealth(p.id)
        void fetchModels(p.id)
      }
    })
  }, [loadProviders, checkHealth, fetchModels])

  if (loading) return <p className="muted">Loading providers...</p>

  return (
    <div className="provider-list">
      <h3>Providers</h3>
      <table className="policy-rule-list__table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Kind</th>
            <th>Base URL</th>
            <th>Health</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {providers.map((p) => (
            <tr key={p.id}>
              <td>{p.name}</td>
              <td>
                <code>{p.kind}</code>
              </td>
              <td>
                <code>{p.baseUrl}</code>
              </td>
              <td>
                <Badge
                  variant={HEALTH_BADGE[providerHealth[p.id] ?? 'unknown'] ?? 'default'}
                >
                  {providerHealth[p.id] ?? 'unknown'}
                </Badge>
              </td>
              <td>
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
                  onClick={() => void deleteProvider(p.id)}
                  title="Delete"
                  style={{
                    background: 'none', border: 'none', cursor: 'pointer',
                    color: 'var(--color-error, #e53e3e)', fontSize: '1.1rem',
                    padding: '0.25rem', marginLeft: '0.25rem',
                  }}
                >
                  &#x2715;
                </button>
              </td>
            </tr>
          ))}
          {providers.length === 0 && (
            <tr>
              <td colSpan={5} className="muted" style={{ textAlign: 'center' }}>
                No providers configured
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
