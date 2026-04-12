// Entrypoint 노드 — 특수 스타일 (accent border).

import { Handle, Position } from '@xyflow/react'

import type { AgentNodeData } from '@/features/editor/types'

import type { NodeProps } from '@xyflow/react'

export function EntrypointNodeView({ data, selected }: NodeProps) {
  const nodeData = data as unknown as AgentNodeData
  const errorClass = nodeData.hasError ? ' entrypoint-node--error' : ''
  const selectedClass = selected ? ' entrypoint-node--selected' : ''

  return (
    <div className={`entrypoint-node${errorClass}${selectedClass}`}>
      <div className="entrypoint-node__marker">ENTRY</div>
      <div className="entrypoint-node__header">
        <span className="entrypoint-node__label">{nodeData.label}</span>
      </div>
      <div className="entrypoint-node__role">{nodeData.roleId}</div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  )
}
