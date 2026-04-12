// Policy manager — policy list + select + rule editor + simulator.

import { useEffect } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { PolicyRuleEditor } from '@/features/policy/components/PolicyRuleEditor'
import { PolicyRuleList } from '@/features/policy/components/PolicyRuleList'
import { PolicySimulator } from '@/features/policy/components/PolicySimulator'
import { usePolicyStore } from '@/features/policy/store'

export function PolicyManager() {
  const {
    policies,
    selectedPolicyId,
    detail,
    loading,
    saving,
    error,
    loadPolicies,
    selectPolicy,
    savePolicy,
  } = usePolicyStore()

  useEffect(() => {
    void loadPolicies()
  }, [loadPolicies])

  const handleSelectChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const id = e.target.value
    if (id) {
      void selectPolicy(id)
    }
  }

  return (
    <div className="policy-manager">
      <div className="policy-manager__header">
        <h2>Policy Manager</h2>
        <div className="policy-manager__controls">
          <select
            className="editor-toolbar__select"
            value={selectedPolicyId ?? ''}
            onChange={handleSelectChange}
          >
            <option value="" disabled>
              Select policy...
            </option>
            {policies.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.mode})
              </option>
            ))}
          </select>
          {detail && (
            <Button
              size="sm"
              variant="primary"
              disabled={saving}
              onClick={() => void savePolicy()}
            >
              {saving ? 'Saving...' : 'Save Policy'}
            </Button>
          )}
        </div>
      </div>

      {error && (
        <div className="policy-manager__error">
          <Badge variant="error">{error}</Badge>
        </div>
      )}

      {loading && <p className="muted">Loading policy...</p>}

      {detail && !loading && (
        <div className="policy-manager__body">
          <div className="policy-manager__info">
            <Badge variant="info">{detail.mode}</Badge>
            <span className="muted">
              {detail.rules.length.toString()} rule(s)
            </span>
          </div>

          <PolicyRuleList />
          <PolicyRuleEditor />
          <PolicySimulator />
        </div>
      )}

      {!detail && !loading && (
        <p className="muted" style={{ padding: '24px', textAlign: 'center' }}>
          Select a policy to manage
        </p>
      )}
    </div>
  )
}
