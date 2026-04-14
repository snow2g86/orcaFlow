// Provider add form — card layout with grid form.

import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { useSettingsStore } from '@/features/settings/store'
import type { ProviderKind } from '@/lib/api/provider'

const KINDS: { value: ProviderKind; label: string }[] = [
  { value: 'ollama', label: 'Ollama' },
  { value: 'lm_studio', label: 'LM Studio' },
  { value: 'vllm', label: 'vLLM' },
  { value: 'llama_cpp', label: 'llama.cpp' },
  { value: 'tgi', label: 'TGI' },
  { value: 'openai_compatible', label: 'OpenAI Compatible' },
  { value: 'together', label: 'Together' },
  { value: 'groq', label: 'Groq' },
  { value: 'fireworks', label: 'Fireworks' },
]

const DEFAULT_URLS: Partial<Record<ProviderKind, string>> = {
  ollama: 'http://127.0.0.1:11434',
  lm_studio: 'http://127.0.0.1:1234',
  vllm: 'http://127.0.0.1:8000',
  llama_cpp: 'http://127.0.0.1:8080',
  tgi: 'http://127.0.0.1:8080',
}

export function ProviderAddForm() {
  const { addProvider, error } = useSettingsStore()
  const [name, setName] = useState('')
  const [kind, setKind] = useState<ProviderKind>('ollama')
  const [baseUrl, setBaseUrl] = useState('http://127.0.0.1:11434')
  const [apiKey, setApiKey] = useState('')
  const [adding, setAdding] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)

  const handleKindChange = (k: ProviderKind) => {
    setKind(k)
    const defaultUrl = DEFAULT_URLS[k]
    if (defaultUrl) setBaseUrl(defaultUrl)
  }

  const handleAdd = async () => {
    if (!name.trim() || !baseUrl.trim()) return
    setAdding(true)
    setLocalError(null)
    try {
      await addProvider({
        name: name.trim(),
        kind,
        baseUrl: baseUrl.trim(),
        apiKey: apiKey.trim() || undefined,
      })
      setName('')
      setBaseUrl(DEFAULT_URLS[kind] ?? 'http://127.0.0.1:11434')
      setApiKey('')
    } catch (e) {
      setLocalError(e instanceof Error ? e.message : 'Failed to add provider')
    } finally {
      setAdding(false)
    }
  }

  return (
    <div className="settings-card">
      <div className="settings-card__header">
        <h3 className="settings-card__title">Add Provider</h3>
      </div>
      <div className="settings-card__body">
        <div className="settings-form">
          <div className="settings-field">
            <label className="settings-field__label">Name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="settings-field__input"
              placeholder="My Ollama"
            />
          </div>
          <div className="settings-field">
            <label className="settings-field__label">Kind</label>
            <select
              value={kind}
              onChange={(e) => handleKindChange(e.target.value as ProviderKind)}
              className="settings-field__select"
            >
              {KINDS.map((k) => (
                <option key={k.value} value={k.value}>{k.label}</option>
              ))}
            </select>
          </div>
          <div className="settings-field settings-field--wide">
            <label className="settings-field__label">Base URL</label>
            <input
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              className="settings-field__input"
              placeholder="http://127.0.0.1:11434"
            />
          </div>
          <div className="settings-field">
            <label className="settings-field__label">API Key</label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              className="settings-field__input"
              placeholder="optional"
            />
          </div>
          <div className="settings-form__actions">
            <Button size="sm" variant="primary" onClick={() => void handleAdd()} disabled={adding}>
              {adding ? 'Adding...' : 'Add Provider'}
            </Button>
          </div>
          {(localError ?? error) && (
            <p className="settings-form__error">{localError ?? error}</p>
          )}
        </div>
      </div>
    </div>
  )
}
