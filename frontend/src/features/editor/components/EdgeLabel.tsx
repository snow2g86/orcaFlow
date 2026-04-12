// Edge condition display/edit — click to edit condition.

import { useState } from 'react'

import { useEditorStore } from '@/features/editor/store'

type EdgeLabelProps = {
  edgeId: string
  condition: string
}

export function EdgeLabel({ edgeId, condition }: EdgeLabelProps) {
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState(condition)
  const { updateEdgeCondition } = useEditorStore()

  const handleSave = () => {
    updateEdgeCondition(edgeId, value)
    setEditing(false)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSave()
    }
    if (e.key === 'Escape') {
      setValue(condition)
      setEditing(false)
    }
  }

  if (editing) {
    return (
      <div className="edge-label edge-label--editing">
        <input
          className="edge-label__input"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onBlur={handleSave}
          onKeyDown={handleKeyDown}
          autoFocus
          placeholder="condition expression"
        />
      </div>
    )
  }

  return (
    <div
      className="edge-label"
      onClick={() => setEditing(true)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter') setEditing(true)
      }}
    >
      {condition || 'click to add condition'}
    </div>
  )
}
