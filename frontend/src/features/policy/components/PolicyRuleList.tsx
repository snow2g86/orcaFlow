// Policy rule table — priority 순, scope/matcher/effect/reason 컬럼.

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { usePolicyStore } from '@/features/policy/store'
import type { PolicyRuleEffect } from '@/features/policy/types'

const EFFECT_VARIANT: Record<PolicyRuleEffect, 'success' | 'error' | 'warning' | 'info'> = {
  allow: 'success',
  deny: 'error',
  ask: 'warning',
  dry_run_only: 'info',
}

export function PolicyRuleList() {
  const { detail, removeRule } = usePolicyStore()

  if (!detail) return null

  return (
    <div className="policy-rule-list">
      <table className="policy-rule-list__table">
        <thead>
          <tr>
            <th>Priority</th>
            <th>Scope</th>
            <th>Matcher</th>
            <th>Effect</th>
            <th>Reason</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {detail.rules.map((rule) => (
            <tr key={rule.id}>
              <td>{rule.priority.toString()}</td>
              <td>
                <code>{rule.scope}</code>
              </td>
              <td>
                <code>{rule.matcher}</code>
              </td>
              <td>
                <Badge variant={EFFECT_VARIANT[rule.effect]}>{rule.effect}</Badge>
              </td>
              <td>{rule.reason ?? '-'}</td>
              <td>
                <Button
                  size="sm"
                  variant="danger"
                  onClick={() => removeRule(rule.id)}
                >
                  Delete
                </Button>
              </td>
            </tr>
          ))}
          {detail.rules.length === 0 && (
            <tr>
              <td colSpan={6} className="muted" style={{ textAlign: 'center' }}>
                No rules defined
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
