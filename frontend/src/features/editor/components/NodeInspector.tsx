// 선택된 노드 속성 패널 — role, tools, llm_profile override, system_prompt 편집.

import { Button } from '@/components/ui/button'
import { useEditorStore } from '@/features/editor/store'
import type { AgentNodeData } from '@/features/editor/types'

export function NodeInspector() {
  const { nodes, selectedNodeId, updateNodeData, setEntrypoint, removeNode } =
    useEditorStore()

  const selectedNode = nodes.find((n) => n.id === selectedNodeId)
  if (!selectedNode) {
    return (
      <div className="node-inspector node-inspector--empty">
        <p className="muted">Select a node to inspect</p>
      </div>
    )
  }

  const data = selectedNode.data

  const handleFieldChange = (field: keyof AgentNodeData, value: unknown) => {
    updateNodeData(selectedNode.id, { [field]: value } as Partial<AgentNodeData>)
  }

  const handleOverrideChange = (key: string, value: string) => {
    const overrides = { ...data.overrides, [key]: value }
    updateNodeData(selectedNode.id, { overrides })
  }

  const handleToolsChange = (value: string) => {
    const tools = value
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean)
    updateNodeData(selectedNode.id, { tools })
  }

  return (
    <div className="node-inspector">
      <h3 className="node-inspector__title">Node Properties</h3>

      <div className="node-inspector__field">
        <label>ID</label>
        <input value={selectedNode.id} disabled className="node-inspector__input" />
      </div>

      <div className="node-inspector__field">
        <label>Label</label>
        <input
          value={data.label}
          onChange={(e) => handleFieldChange('label', e.target.value)}
          className="node-inspector__input"
        />
      </div>

      <div className="node-inspector__field">
        <label>Role ID</label>
        <input
          value={data.roleId}
          onChange={(e) => handleFieldChange('roleId', e.target.value)}
          className="node-inspector__input"
        />
      </div>

      <div className="node-inspector__field">
        <label>Tools (comma-separated)</label>
        <input
          value={data.tools.join(', ')}
          onChange={(e) => handleToolsChange(e.target.value)}
          className="node-inspector__input"
          placeholder="fs.read_file, shell.exec"
        />
      </div>

      <div className="node-inspector__field">
        <label>LLM Profile Override</label>
        <input
          value={(data.overrides['llm_profile'] as string) ?? ''}
          onChange={(e) => handleOverrideChange('llm_profile', e.target.value)}
          className="node-inspector__input"
          placeholder="e.g. ollama-qwen2.5-7b"
        />
      </div>

      <div className="node-inspector__field">
        <label>System Prompt Override</label>
        <textarea
          value={(data.overrides['system_prompt'] as string) ?? ''}
          onChange={(e) => handleOverrideChange('system_prompt', e.target.value)}
          className="node-inspector__textarea"
          rows={4}
          placeholder="Custom system prompt..."
        />
      </div>

      <div className="node-inspector__actions">
        {!data.isEntrypoint && (
          <Button
            size="sm"
            variant="secondary"
            onClick={() => setEntrypoint(selectedNode.id)}
          >
            Set as Entrypoint
          </Button>
        )}
        <Button
          size="sm"
          variant="danger"
          onClick={() => removeNode(selectedNode.id)}
        >
          Delete Node
        </Button>
      </div>
    </div>
  )
}
