// Provider add form — kind, base_url, api_key input.

import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { useSettingsStore } from '@/features/settings/store'
import type { ProviderKind } from '@/lib/api/provider'

const KINDS: ProviderKind[] = [
  'ollama',
  'vllm',
  'llama_cpp',
  'lm_studio',
  'tgi',
  'openai_compatible',
  'together',
  'groq',
  'fireworks',
]

export function ProviderAddForm() {
  const { addProvider } = useSettingsStore()
  const [name, setName] = useState('')
  const [kind, setKind] = useState<ProviderKind>('ollama')
  const [baseUrl, setBaseUrl] = useState('http://127.0.0.1:11434')
  const [apiKey, setApiKey] = useState('')

  const handleAdd = () => {
    if (!name.trim() || !baseUrl.trim()) return
    void addProvider({
      name: name.trim(),
      kind,
      baseUrl: baseUrl.trim(),
      apiKey: apiKey.trim() || undefined,
    })
    setName('')
    setBaseUrl('http://127.0.0.1:11434')
    setApiKey('')
  }

  return (
    <div className="provider-add-form">
      <h4>Add Provider</h4>
      <div className="policy-rule-editor__row">
        <div className="policy-rule-editor__field">
          <label>Name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="node-inspector__input"
            placeholder="My Ollama"
          />
        </div>
        <div className="policy-rule-editor__field">
          <label>Kind</label>
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value as ProviderKind)}
            className="editor-toolbar__select"
          >
            {KINDS.map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
        </div>
        <div className="policy-rule-editor__field">
          <label>Base URL</label>
          <input
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            className="node-inspector__input"
            placeholder="http://127.0.0.1:11434"
          />
        </div>
        <div className="policy-rule-editor__field">
          <label>API Key</label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            className="node-inspector__input"
            placeholder="optional"
          />
        </div>
        <Button size="sm" variant="primary" onClick={handleAdd}>
          Add
        </Button>
      </div>
    </div>
  )
}
