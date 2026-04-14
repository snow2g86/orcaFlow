// LLM Profile editor — create/edit profile form.

import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import * as llmProfileApi from '@/lib/api/llm-profile'
import { useSettingsStore } from '@/features/settings/store'

export function LLMProfileEditor() {
  const { providers, providerModels, fetchModels, loadProfiles } = useSettingsStore()
  const [name, setName] = useState('')
  const [model, setModel] = useState('')
  const [providerId, setProviderId] = useState('')
  const [temperature, setTemperature] = useState('0.7')
  const [maxTokens, setMaxTokens] = useState('4096')
  const [isPlanner, setIsPlanner] = useState(false)
  const [isDefault, setIsDefault] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  const models = providerId ? providerModels[providerId] ?? null : null
  const modelsLoading = providerId !== '' && models === null

  // Provider 선택 시 자동으로 모델 목록 fetch
  useEffect(() => {
    if (providerId && !(providerId in providerModels)) {
      void fetchModels(providerId)
    }
  }, [providerId, providerModels, fetchModels])

  // Provider 변경 시 model 초기화
  const handleProviderChange = (id: string) => {
    setProviderId(id)
    setModel('')
  }

  const handleCreate = async () => {
    if (!name.trim() || !model.trim() || !providerId) return
    setFormError(null)
    setCreating(true)
    try {
      await llmProfileApi.createLlmProfile({
        name: name.trim(),
        providerId,
        model: model.trim(),
        params: {
          temperature: parseFloat(temperature) || 0.7,
          maxTokens: parseInt(maxTokens, 10) || 4096,
        },
        isToolCapable: true,
        isPlanner,
        isDefault,
      })
      setName('')
      setModel('')
      setTemperature('0.7')
      setMaxTokens('4096')
      setIsPlanner(false)
      setIsDefault(false)
      await loadProfiles()
    } catch (e) {
      setFormError(e instanceof Error ? e.message : 'Failed to create profile')
    } finally {
      setCreating(false)
    }
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
            onChange={(e) => handleProviderChange(e.target.value)}
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
          {models && models.length > 0 ? (
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="editor-toolbar__select"
            >
              <option value="" disabled>
                {modelsLoading ? 'Loading...' : 'Select model...'}
              </option>
              {models.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          ) : (
            <input
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="node-inspector__input"
              placeholder={modelsLoading ? 'Loading models...' : 'model name'}
            />
          )}
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
        <Button size="sm" variant="primary" onClick={() => void handleCreate()} disabled={creating}>
          {creating ? 'Creating...' : 'Create'}
        </Button>
      </div>
      {formError && (
        <p style={{ color: 'var(--color-error, #e53e3e)', marginTop: '0.5rem', fontSize: '0.85rem' }}>
          {formError}
        </p>
      )}
    </div>
  )
}
