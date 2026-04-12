// Policy simulator — scenario input + simulate button + results.

import { useState } from 'react'

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

export function PolicySimulator() {
  const { scenarios, simulationResults, simulating, addScenario, removeScenario, simulate } =
    usePolicyStore()
  const [toolId, setToolId] = useState('')
  const [argsJson, setArgsJson] = useState('{}')

  const handleAddScenario = () => {
    if (!toolId.trim()) return
    try {
      const args = JSON.parse(argsJson) as Record<string, unknown>
      addScenario({ toolId: toolId.trim(), args })
      setToolId('')
      setArgsJson('{}')
    } catch {
      // Invalid JSON — ignore
    }
  }

  return (
    <div className="policy-simulator">
      <h4>Simulator</h4>

      <div className="policy-simulator__add">
        <div className="policy-rule-editor__field">
          <label>Tool ID</label>
          <input
            value={toolId}
            onChange={(e) => setToolId(e.target.value)}
            className="node-inspector__input"
            placeholder="e.g. fs.write_file"
          />
        </div>
        <div className="policy-rule-editor__field">
          <label>Args (JSON)</label>
          <input
            value={argsJson}
            onChange={(e) => setArgsJson(e.target.value)}
            className="node-inspector__input"
            placeholder='{"path": "/tmp/test.txt"}'
          />
        </div>
        <Button size="sm" variant="secondary" onClick={handleAddScenario}>
          Add Scenario
        </Button>
      </div>

      {scenarios.length > 0 && (
        <div className="policy-simulator__scenarios">
          <table className="policy-rule-list__table">
            <thead>
              <tr>
                <th>#</th>
                <th>Tool ID</th>
                <th>Args</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {scenarios.map((s, i) => (
                <tr key={i}>
                  <td>{(i + 1).toString()}</td>
                  <td>
                    <code>{s.toolId}</code>
                  </td>
                  <td>
                    <code>{JSON.stringify(s.args)}</code>
                  </td>
                  <td>
                    <Button
                      size="sm"
                      variant="danger"
                      onClick={() => removeScenario(i)}
                    >
                      Remove
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <Button
            size="sm"
            variant="primary"
            disabled={simulating}
            onClick={() => void simulate()}
          >
            {simulating ? 'Simulating...' : 'Simulate'}
          </Button>
        </div>
      )}

      {simulationResults.length > 0 && (
        <div className="policy-simulator__results">
          <h4>Results</h4>
          <table className="policy-rule-list__table">
            <thead>
              <tr>
                <th>Tool ID</th>
                <th>Effect</th>
                <th>Rule ID</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {simulationResults.map((r, i) => (
                <tr key={i}>
                  <td>
                    <code>{r.toolId}</code>
                  </td>
                  <td>
                    <Badge variant={EFFECT_VARIANT[r.effect]}>{r.effect}</Badge>
                  </td>
                  <td>{r.ruleId ?? '-'}</td>
                  <td>{r.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
