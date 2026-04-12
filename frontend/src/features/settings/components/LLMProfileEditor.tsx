// LLM Profile editor — create/edit profile form.
// For M6 this is a simple placeholder; full editing to follow in M7.

import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { useSettingsStore } from '@/features/settings/store'

export function LLMProfileEditor() {
  const { providers } = useSettingsStore()
  const [name, setName] = useState('')
  const [model, setModel] = useState('')
  const [providerId, setProviderId] = useState('')
  const [temperature, setTemperature] = useState('0.7')
  const [maxTokens, setMaxTokens] = useState('4096')
  const [isPlanner, setIsPlanner] = useState(false)
  const [isDefault, setIsDefault] = useState(false)

  const handleCreate = () => {
    if (!name.trim() || !model.trim() || !providerId) return
    // In M6 we show the form; actual creation via API would need createLlmProfile.
    // For now this is a visual placeholder.
    setName('')
    setModel('')
    setTemperature('0.7')
    setMaxTokens('4096')
  }

  return (
    <div className="llm-profile-editor">
      <h4>Add LLM Profile</h4>
      <div className="policy-rule-editor__row" style={{ flexWrap: 'wrap' }}>
        <div className="policy-rule-editor__field">
          <label>Name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="node-inspector__input"
            placeholder="ollama-qwen2.5-14b"
          />
        </div>
        <div className="policy-rule-editor__field">
          <label>Provider</label>
          <select
            value={providerId}
            onChange={(e) => setProviderId(e.target.value)}
            className="editor-toolbar__select"
          >
            <option value="" disabled>
              Select...
            </option>
            {providers.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
        <div className="policy-rule-editor__field">
          <label>Model</label>
          <input
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="node-inspector__input"
            placeholder="qwen2.5:14b"
          />
        </div>
        <div className="policy-rule-editor__field">
          <label>Temperature</label>
          <input
            type="number"
            step="0.1"
            value={temperature}
            onChange={(e) => setTemperature(e.target.value)}
            className="node-inspector__input"
          />
        </div>
        <div className="policy-rule-editor__field">
          <label>Max Tokens</label>
          <input
            type="number"
            value={maxTokens}
            onChange={(e) => setMaxTokens(e.target.value)}
            className="node-inspector__input"
          />
        </div>
        <div className="policy-rule-editor__field">
          <label>
            <input
              type="checkbox"
              checked={isPlanner}
              onChange={(e) => setIsPlanner(e.target.checked)}
            />{' '}
            Planner
          </label>
        </div>
        <div className="policy-rule-editor__field">
          <label>
            <input
              type="checkbox"
              checked={isDefault}
              onChange={(e) => setIsDefault(e.target.checked)}
            />{' '}
            Default
          </label>
        </div>
        <Button size="sm" variant="primary" onClick={handleCreate}>
          Create
        </Button>
      </div>
    </div>
  )
}
