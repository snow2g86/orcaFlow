// LLM Profile list — Vercel-style table in card.

import { useEffect } from 'react'

import { Badge } from '@/components/ui/badge'
import { useSettingsStore } from '@/features/settings/store'

export function LLMProfileList() {
  const { profiles, providers, loadProfiles, deleteProfile } = useSettingsStore()
  const providerName = (id: string) =>
    providers.find((p) => p.id === id)?.name ?? id.slice(0, 8) + '...'

  useEffect(() => {
    void loadProfiles()
  }, [loadProfiles])

  return (
    <div className="settings-card">
      <div className="settings-card__header">
        <div>
          <h3 className="settings-card__title">LLM Profiles</h3>
          <p className="settings-card__desc">Model configurations for agents and chat</p>
        </div>
      </div>
      <div className="settings-card__body--flush">
        {profiles.length === 0 ? (
          <p className="settings-table__empty">No profiles configured</p>
        ) : (
          <table className="settings-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Model</th>
                <th>Provider</th>
                <th>Flags</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {profiles.map((p) => (
                <tr key={p.id}>
                  <td className="cell-name">{p.name}</td>
                  <td className="cell-mono">{p.model}</td>
                  <td>{providerName(p.providerId)}</td>
                  <td>
                    <div style={{ display: 'flex', gap: 4 }}>
                      {p.isDefault && <Badge variant="success">Default</Badge>}
                      {p.isPlanner && <Badge variant="info">Planner</Badge>}
                      {!p.isDefault && !p.isPlanner && <span className="muted">-</span>}
                    </div>
                  </td>
                  <td className="cell-actions">
                    <button
                      className="settings-delete-btn"
                      onClick={() => void deleteProfile(p.id)}
                      title="Delete profile"
                    >
                      &#x2715;
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
