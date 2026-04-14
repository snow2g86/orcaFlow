// LLM Profile editor — Supabase-style card with footer actions.

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

  useEffect(() => {
    if (providerId && !(providerId in providerModels)) {
      void fetchModels(providerId)
    }
  }, [providerId, providerModels, fetchModels])

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
    <div className="settings-card">
      <div className="settings-card__header">
        <div>
          <h3 className="settings-card__title">Create LLM Profile</h3>
          <p className="settings-card__desc">Define model + parameters for agents</p>
        </div>
      </div>
      <div className="settings-card__body">
        <div className="settings-form">
          <div className="settings-field">
            <label className="settings-field__label">Profile Name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="settings-field__input"
              placeholder="my-model-profile"
            />
          </div>
          <div className="settings-field">
            <label className="settings-field__label">Provider</label>
            <select
              value={providerId}
              onChange={(e) => handleProviderChange(e.target.value)}
              className="settings-field__select"
            >
              <option value="" disabled>Select provider...</option>
              {providers.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
          <div className="settings-field">
            <label className="settings-field__label">Model</label>
            {models && models.length > 0 ? (
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="settings-field__select"
              >
                <option value="" disabled>Select model...</option>
                {models.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            ) : (
              <input
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="settings-field__input"
                placeholder={modelsLoading ? 'Loading models...' : 'Enter model name'}
                disabled={modelsLoading}
              />
            )}
          </div>
          <div className="settings-field">
            <label className="settings-field__label">Temperature</label>
            <input
              type="number"
              step="0.1"
              min="0"
              max="2"
              value={temperature}
              onChange={(e) => setTemperature(e.target.value)}
              className="settings-field__input"
            />
          </div>
          <div className="settings-field">
            <label className="settings-field__label">Max Tokens</label>
            <input
              type="number"
              min="1"
              value={maxTokens}
              onChange={(e) => setMaxTokens(e.target.value)}
              className="settings-field__input"
            />
          </div>
          <div className="settings-field__checkbox-row">
            <label className="settings-field__checkbox">
              <input
                type="checkbox"
                checked={isPlanner}
                onChange={(e) => setIsPlanner(e.target.checked)}
              />
              Planner
            </label>
            <label className="settings-field__checkbox">
              <input
                type="checkbox"
                checked={isDefault}
                onChange={(e) => setIsDefault(e.target.checked)}
              />
              Default
            </label>
          </div>
          {formError && <p className="settings-form__error">{formError}</p>}
        </div>
      </div>
      <div className="settings-card__footer">
        <Button size="sm" variant="primary" onClick={() => void handleCreate()} disabled={creating}>
          {creating ? 'Creating...' : 'Create Profile'}
        </Button>
      </div>
    </div>
  )
}
