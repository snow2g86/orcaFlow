// Policy rule add/edit form.

import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { usePolicyStore } from '@/features/policy/store'
import type { PolicyRuleEffect, PolicyRuleScope } from '@/features/policy/types'

const SCOPES: PolicyRuleScope[] = [
  'fs_path',
  'shell_command',
  'network_host',
  'os_api',
  'tool_id',
]

const EFFECTS: PolicyRuleEffect[] = ['allow', 'deny', 'ask', 'dry_run_only']

export function PolicyRuleEditor() {
  const { addRule } = usePolicyStore()
  const [scope, setScope] = useState<PolicyRuleScope>('fs_path')
  const [matcher, setMatcher] = useState('')
  const [effect, setEffect] = useState<PolicyRuleEffect>('allow')
  const [reason, setReason] = useState('')
  const [priority, setPriority] = useState(50)

  const handleAdd = () => {
    if (!matcher.trim()) return
    const trimmedReason = reason.trim()
    addRule({
      priority,
      scope,
      matcher: matcher.trim(),
      effect,
      ...(trimmedReason ? { reason: trimmedReason } : {}),
    })
    setMatcher('')
    setReason('')
    setPriority(50)
  }

  return (
    <div className="policy-rule-editor">
      <h4>Add Rule</h4>
      <div className="policy-rule-editor__row">
        <div className="policy-rule-editor__field">
          <label>Priority</label>
          <input
            type="number"
            value={priority.toString()}
            onChange={(e) => setPriority(Number(e.target.value))}
            className="node-inspector__input"
            min={1}
          />
        </div>
        <div className="policy-rule-editor__field">
          <label>Scope</label>
          <select
            value={scope}
            onChange={(e) => setScope(e.target.value as PolicyRuleScope)}
            className="editor-toolbar__select"
          >
            {SCOPES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div className="policy-rule-editor__field">
          <label>Matcher</label>
          <input
            value={matcher}
            onChange={(e) => setMatcher(e.target.value)}
            className="node-inspector__input"
            placeholder="glob/regex/literal"
          />
        </div>
        <div className="policy-rule-editor__field">
          <label>Effect</label>
          <select
            value={effect}
            onChange={(e) => setEffect(e.target.value as PolicyRuleEffect)}
            className="editor-toolbar__select"
          >
            {EFFECTS.map((eff) => (
              <option key={eff} value={eff}>
                {eff}
              </option>
            ))}
          </select>
        </div>
        <div className="policy-rule-editor__field">
          <label>Reason</label>
          <input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="node-inspector__input"
            placeholder="optional"
          />
        </div>
        <Button size="sm" variant="primary" onClick={handleAdd}>
          Add Rule
        </Button>
      </div>
    </div>
  )
}
