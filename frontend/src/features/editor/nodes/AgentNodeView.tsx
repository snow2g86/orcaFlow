// AgentNode 렌더러 — role 이름, tools 아이콘, override badge.

import { Handle, Position } from '@xyflow/react'

import type { AgentNodeData } from '@/features/editor/types'

import type { NodeProps } from '@xyflow/react'

export function AgentNodeView({ data, selected }: NodeProps) {
  const nodeData = data as unknown as AgentNodeData
  const hasOverrides = Object.keys(nodeData.overrides).length > 0
  const errorClass = nodeData.hasError ? ' agent-node--error' : ''
  const selectedClass = selected ? ' agent-node--selected' : ''

  return (
    <div className={`agent-node${errorClass}${selectedClass}`}>
      <Handle type="target" position={Position.Top} />
      <div className="agent-node__header">
        <span className="agent-node__label">{nodeData.label}</span>
        {hasOverrides && <span className="agent-node__badge">OVR</span>}
      </div>
      <div className="agent-node__role">{nodeData.roleId}</div>
      {nodeData.tools.length > 0 && (
        <div className="agent-node__tools">
          {nodeData.tools.slice(0, 3).map((t) => (
            <span key={t} className="agent-node__tool-tag">
              {t}
            </span>
          ))}
          {nodeData.tools.length > 3 && (
            <span className="agent-node__tool-tag">+{(nodeData.tools.length - 3).toString()}</span>
          )}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} />
    </div>
  )
}
