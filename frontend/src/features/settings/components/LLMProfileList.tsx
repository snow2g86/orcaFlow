// LLM Profile list — card layout with badges.

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
        <h3 className="settings-card__title">LLM Profiles</h3>
        <Badge variant="default">{profiles.length}</Badge>
      </div>
      {profiles.length === 0 ? (
        <div className="settings-card__body">
          <p className="muted" style={{ textAlign: 'center', margin: 0 }}>
            No profiles configured. Create one below.
          </p>
        </div>
      ) : (
        <table className="settings-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Model</th>
              <th>Provider</th>
              <th>Flags</th>
              <th style={{ width: 1 }}></th>
            </tr>
          </thead>
          <tbody>
            {profiles.map((p) => (
              <tr key={p.id}>
                <td style={{ fontWeight: 500 }}>{p.name}</td>
                <td><code>{p.model}</code></td>
                <td>{providerName(p.providerId)}</td>
                <td>
                  <div style={{ display: 'flex', gap: 4 }}>
                    {p.isDefault && <Badge variant="success">Default</Badge>}
                    {p.isPlanner && <Badge variant="info">Planner</Badge>}
                    {!p.isDefault && !p.isPlanner && <span className="muted">-</span>}
                  </div>
                </td>
                <td>
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
  )
}
