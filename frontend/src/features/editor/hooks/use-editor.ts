// Editor hook — React Flow 이벤트 핸들러 연결.

import { useCallback } from 'react'

import { useEditorStore } from '@/features/editor/store'
import type { AgentFlowEdge, AgentFlowNode } from '@/features/editor/types'

import type { Connection, EdgeChange, NodeChange } from '@xyflow/react'

export function useEditor() {
  const store = useEditorStore()

  const onNodesChange = useCallback(
    (changes: NodeChange<AgentFlowNode>[]) => {
      const { nodes } = useEditorStore.getState()
      let updated = [...nodes]

      for (const change of changes) {
        if (change.type === 'position' && change.position) {
          updated = updated.map((n) =>
            n.id === change.id ? { ...n, position: change.position! } : n,
          )
        }
        if (change.type === 'remove') {
          updated = updated.filter((n) => n.id !== change.id)
        }
        if (change.type === 'select') {
          if (change.selected) {
            useEditorStore.getState().selectNode(change.id)
          }
        }
      }

      useEditorStore.getState().setNodes(updated)
    },
    [],
  )

  const onEdgesChange = useCallback(
    (changes: EdgeChange<AgentFlowEdge>[]) => {
      const { edges } = useEditorStore.getState()
      let updated = [...edges]

      for (const change of changes) {
        if (change.type === 'remove') {
          updated = updated.filter((e) => e.id !== change.id)
        }
      }

      useEditorStore.getState().setEdges(updated)
    },
    [],
  )

  const onConnect = useCallback((connection: Connection) => {
    if (connection.source && connection.target) {
      useEditorStore.getState().connectNodes(connection.source, connection.target)
    }
  }, [])

  return {
    ...store,
    onNodesChange,
    onEdgesChange,
    onConnect,
  }
}
