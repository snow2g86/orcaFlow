// LLM Profile list — displays profiles with is_planner, is_default badges.

import { useEffect } from 'react'

import { Badge } from '@/components/ui/badge'
import { useSettingsStore } from '@/features/settings/store'

export function LLMProfileList() {
  const { profiles, providers, loadProfiles } = useSettingsStore()
  const providerName = (id: string) =>
    providers.find((p) => p.id === id)?.name ?? id

  useEffect(() => {
    void loadProfiles()
  }, [loadProfiles])

  return (
    <div className="llm-profile-list">
      <h3>LLM Profiles</h3>
      <table className="policy-rule-list__table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Model</th>
            <th>Provider</th>
            <th>Flags</th>
          </tr>
        </thead>
        <tbody>
          {profiles.map((p) => (
            <tr key={p.id}>
              <td>{p.name}</td>
              <td>
                <code>{p.model}</code>
              </td>
              <td>{providerName(p.providerId)}</td>
              <td>
                {p.isDefault && <Badge variant="success">Default</Badge>}
                {p.isPlanner && <Badge variant="info">Planner</Badge>}
              </td>
            </tr>
          ))}
          {profiles.length === 0 && (
            <tr>
              <td colSpan={4} className="muted" style={{ textAlign: 'center' }}>
                No profiles configured
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
