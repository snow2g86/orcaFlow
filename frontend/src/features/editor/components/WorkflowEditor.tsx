// Main editor — React Flow canvas with context menu.

import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  ReactFlowProvider,
} from '@xyflow/react'
import { useCallback, useRef, useState } from 'react'

import '@xyflow/react/dist/style.css'

import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { EditorToolbar } from '@/features/editor/components/EditorToolbar'
import { NodeInspector } from '@/features/editor/components/NodeInspector'
import { YamlEditor } from '@/features/editor/components/YamlEditor'
import { useEditor } from '@/features/editor/hooks/use-editor'
import { nodeTypes } from '@/features/editor/nodes/registry'

type ContextMenu = {
  x: number
  y: number
  nodeId?: string
}

export function WorkflowEditor() {
  const {
    nodes,
    edges,
    mode,
    loading,
    onNodesChange,
    onEdgesChange,
    onConnect,
    addNode,
    removeNode,
    setEntrypoint,
    selectNode,
  } = useEditor()

  const reactFlowWrapper = useRef<HTMLDivElement>(null)
  const [contextMenu, setContextMenu] = useState<ContextMenu | null>(null)
  const [addNodeDialog, setAddNodeDialog] = useState(false)
  const [newNodeRole, setNewNodeRole] = useState('')
  const [newNodeLabel, setNewNodeLabel] = useState('')
  const [addNodePos, setAddNodePos] = useState({ x: 0, y: 0 })

  const handlePaneContextMenu = useCallback(
    (event: MouseEvent | React.MouseEvent) => {
      event.preventDefault()
      const bounds = reactFlowWrapper.current?.getBoundingClientRect()
      if (bounds) {
        setContextMenu({
          x: event.clientX - bounds.left,
          y: event.clientY - bounds.top,
        })
        setAddNodePos({
          x: event.clientX - bounds.left,
          y: event.clientY - bounds.top,
        })
      }
    },
    [],
  )

  const handleNodeContextMenu = useCallback(
    (event: MouseEvent | React.MouseEvent, nodeId: string) => {
      event.preventDefault()
      const bounds = reactFlowWrapper.current?.getBoundingClientRect()
      if (bounds) {
        setContextMenu({
          x: event.clientX - bounds.left,
          y: event.clientY - bounds.top,
          nodeId,
        })
      }
    },
    [],
  )

  const handleContextAction = useCallback(
    (action: string) => {
      if (action === 'add-node') {
        setAddNodeDialog(true)
      } else if (action === 'delete-node' && contextMenu?.nodeId) {
        removeNode(contextMenu.nodeId)
      } else if (action === 'set-entrypoint' && contextMenu?.nodeId) {
        setEntrypoint(contextMenu.nodeId)
      }
      setContextMenu(null)
    },
    [contextMenu, removeNode, setEntrypoint],
  )

  const handleAddNode = useCallback(() => {
    if (newNodeRole.trim()) {
      addNode(newNodeRole.trim(), newNodeLabel.trim() || newNodeRole.trim(), addNodePos)
      setNewNodeRole('')
      setNewNodeLabel('')
      setAddNodeDialog(false)
    }
  }, [newNodeRole, newNodeLabel, addNodePos, addNode])

  const handleNodeClick = useCallback(
    (_event: React.MouseEvent, node: { id: string }) => {
      selectNode(node.id)
    },
    [selectNode],
  )

  const handlePaneClick = useCallback(() => {
    setContextMenu(null)
    selectNode(null)
  }, [selectNode])

  if (loading) {
    return (
      <div className="workflow-editor">
        <EditorToolbar />
        <div className="workflow-editor__loading">Loading workflow...</div>
      </div>
    )
  }

  return (
    <div className="workflow-editor">
      <EditorToolbar />
      <div className="workflow-editor__body">
        {mode === 'yaml' ? (
          <YamlEditor />
        ) : (
          <div className="workflow-editor__canvas" ref={reactFlowWrapper}>
            <ReactFlowProvider>
              <ReactFlow
                nodes={nodes}
                edges={edges}
                nodeTypes={nodeTypes}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                onPaneContextMenu={handlePaneContextMenu}
                onNodeContextMenu={(event, node) =>
                  handleNodeContextMenu(event, node.id)
                }
                onNodeClick={handleNodeClick}
                onPaneClick={handlePaneClick}
                fitView
                deleteKeyCode="Delete"
              >
                <Background />
                <Controls />
                <MiniMap />
              </ReactFlow>
            </ReactFlowProvider>

            {/* Context menu */}
            {contextMenu && (
              <div
                className="editor-context-menu"
                style={{ left: contextMenu.x, top: contextMenu.y }}
              >
                {!contextMenu.nodeId && (
                  <button
                    className="editor-context-menu__item"
                    onClick={() => handleContextAction('add-node')}
                  >
                    Add Agent Node
                  </button>
                )}
                {contextMenu.nodeId && (
                  <>
                    <button
                      className="editor-context-menu__item"
                      onClick={() => handleContextAction('delete-node')}
                    >
                      Delete Node
                    </button>
                    <button
                      className="editor-context-menu__item"
                      onClick={() => handleContextAction('set-entrypoint')}
                    >
                      Set as Entrypoint
                    </button>
                  </>
                )}
              </div>
            )}
          </div>
        )}
        <NodeInspector />
      </div>

      {/* Add Node Dialog */}
      <Dialog
        open={addNodeDialog}
        onClose={() => setAddNodeDialog(false)}
        className="add-node-dialog"
      >
        <h3>Add Agent Node</h3>
        <div className="node-inspector__field">
          <label>Role ID</label>
          <input
            className="node-inspector__input"
            value={newNodeRole}
            onChange={(e) => setNewNodeRole(e.target.value)}
            placeholder="e.g. planner, file-organizer"
            autoFocus
          />
        </div>
        <div className="node-inspector__field">
          <label>Label</label>
          <input
            className="node-inspector__input"
            value={newNodeLabel}
            onChange={(e) => setNewNodeLabel(e.target.value)}
            placeholder="Display label (optional)"
          />
        </div>
        <div className="node-inspector__actions">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setAddNodeDialog(false)}
          >
            Cancel
          </Button>
          <Button size="sm" variant="primary" onClick={handleAddNode}>
            Add
          </Button>
        </div>
      </Dialog>
    </div>
  )
}
