// YAML 직접 편집 뷰 — textarea + validation result.

import { useEffect, useState } from 'react'

import { useEditorStore } from '@/features/editor/store'

export function YamlEditor() {
  const { yamlText, syncFlowFromYaml, validationErrors, error } = useEditorStore()
  const [localYaml, setLocalYaml] = useState(yamlText)

  useEffect(() => {
    setLocalYaml(yamlText)
  }, [yamlText])

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setLocalYaml(e.target.value)
  }

  const handleApply = () => {
    syncFlowFromYaml(localYaml)
  }

  return (
    <div className="yaml-editor">
      <div className="yaml-editor__toolbar">
        <button
          className="orca-btn orca-btn--secondary orca-btn--sm"
          onClick={handleApply}
        >
          Apply YAML
        </button>
      </div>
      <textarea
        className="yaml-editor__textarea"
        value={localYaml}
        onChange={handleChange}
        spellCheck={false}
      />
      {error && <div className="yaml-editor__error">{error}</div>}
      {validationErrors.length > 0 && (
        <div className="yaml-editor__errors">
          {validationErrors.map((ve, i) => (
            <div key={i} className="yaml-editor__error-item">
              {ve.nodeId && <span>[Node: {ve.nodeId}] </span>}
              {ve.edgeIndex !== undefined && (
                <span>[Edge #{ve.edgeIndex.toString()}] </span>
              )}
              {ve.message}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
