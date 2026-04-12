// BFS-based vertical layer layout for workflow graphs.
// dagre/elkjs 금지 — 자체 구현.

import type { AgentFlowEdge, AgentFlowNode } from '@/features/editor/types'

const NODE_WIDTH = 200
const NODE_HEIGHT = 80
const HORIZONTAL_GAP = 60
const VERTICAL_GAP = 100

/**
 * BFS 기반 수직 계층 레이아웃.
 * entrypoint 가 최상위(y=0), 하위 레벨로 노드 배치.
 */
export function applyBfsLayout(
  nodes: AgentFlowNode[],
  edges: AgentFlowEdge[],
): AgentFlowNode[] {
  if (nodes.length === 0) return []

  // Build adjacency list
  const adjacency = new Map<string, string[]>()
  for (const node of nodes) {
    adjacency.set(node.id, [])
  }
  for (const edge of edges) {
    const children = adjacency.get(edge.source)
    if (children) {
      children.push(edge.target)
    }
  }

  // Find entrypoint (isEntrypoint flag or first node)
  const entryNode = nodes.find((n) => n.data.isEntrypoint) ?? nodes[0]
  if (!entryNode) return nodes

  // BFS to assign levels
  const levels = new Map<string, number>()
  const queue: string[] = [entryNode.id]
  levels.set(entryNode.id, 0)

  while (queue.length > 0) {
    const current = queue.shift()!
    const currentLevel = levels.get(current) ?? 0
    const children = adjacency.get(current) ?? []
    for (const child of children) {
      if (!levels.has(child)) {
        levels.set(child, currentLevel + 1)
        queue.push(child)
      }
    }
  }

  // Assign level 0 to unvisited nodes (disconnected)
  for (const node of nodes) {
    if (!levels.has(node.id)) {
      levels.set(node.id, 0)
    }
  }

  // Group nodes by level
  const levelGroups = new Map<number, string[]>()
  for (const [nodeId, level] of levels) {
    const group = levelGroups.get(level)
    if (group) {
      group.push(nodeId)
    } else {
      levelGroups.set(level, [nodeId])
    }
  }

  // Compute positions
  const nodePositions = new Map<string, { x: number; y: number }>()
  for (const [level, nodeIds] of levelGroups) {
    const totalWidth =
      nodeIds.length * NODE_WIDTH + (nodeIds.length - 1) * HORIZONTAL_GAP
    const startX = -totalWidth / 2
    nodeIds.forEach((nodeId, index) => {
      nodePositions.set(nodeId, {
        x: startX + index * (NODE_WIDTH + HORIZONTAL_GAP),
        y: level * (NODE_HEIGHT + VERTICAL_GAP),
      })
    })
  }

  return nodes.map((node) => {
    const pos = nodePositions.get(node.id)
    return pos ? { ...node, position: pos } : node
  })
}
