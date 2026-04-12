// Editor toolbar — Save/Load/Validate/YAML toggle/Auto Layout buttons.

import { useEffect } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useEditorStore } from '@/features/editor/store'

export function EditorToolbar() {
  const {
    mode,
    setMode,
    dirty,
    saving,
    workflowName,
    setWorkflowName,
    workflows,
    loadWorkflowList,
    loadWorkflow,
    saveWorkflow,
    validateWorkflow,
    autoLayout,
    newWorkflow,
    validationErrors,
    error,
  } = useEditorStore()

  useEffect(() => {
    void loadWorkflowList()
  }, [loadWorkflowList])

  const handleLoadChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const id = e.target.value
    if (id) {
      void loadWorkflow(id)
    }
  }

  return (
    <div className="editor-toolbar">
      <div className="editor-toolbar__left">
        <input
          className="editor-toolbar__name-input"
          value={workflowName}
          onChange={(e) => setWorkflowName(e.target.value)}
          placeholder="Workflow name"
        />
        {dirty && <Badge variant="warning">Unsaved</Badge>}
        {validationErrors.length > 0 && (
          <Badge variant="error">{validationErrors.length.toString()} errors</Badge>
        )}
        {error && <Badge variant="error">Error</Badge>}
      </div>
      <div className="editor-toolbar__right">
        <select
          className="editor-toolbar__select"
          onChange={handleLoadChange}
          defaultValue=""
        >
          <option value="" disabled>
            Load workflow...
          </option>
          {workflows.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}
            </option>
          ))}
        </select>
        <Button size="sm" variant="ghost" onClick={newWorkflow}>
          New
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => setMode(mode === 'visual' ? 'yaml' : 'visual')}
        >
          {mode === 'visual' ? 'YAML' : 'Visual'}
        </Button>
        {mode === 'visual' && (
          <Button size="sm" variant="ghost" onClick={autoLayout}>
            Auto Layout
          </Button>
        )}
        <Button
          size="sm"
          variant="secondary"
          onClick={() => void validateWorkflow()}
        >
          Validate
        </Button>
        <Button
          size="sm"
          variant="primary"
          disabled={saving}
          onClick={() => void saveWorkflow()}
        >
          {saving ? 'Saving...' : 'Save'}
        </Button>
      </div>
    </div>
  )
}
