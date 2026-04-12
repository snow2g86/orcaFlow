import { describe, it, expect } from 'vitest'

import { workflowToFlow, workflowToFlowEdges, workflowToFlowNodes } from '@/features/editor/lib/schema-to-rf'
import type { WorkflowDefinition } from '@/features/editor/types'

const SAMPLE_WORKFLOW: WorkflowDefinition = {
  name: 'Test Workflow',
  version: 1,
  entrypointNodeId: 'planner',
  nodes: [
    {
      id: 'planner',
      roleId: 'planner',
      label: 'Planner',
      position: { x: 0, y: 0 },
      overrides: { tools: ['fs.read_file'] },
    },
    {
      id: 'worker',
      roleId: 'file-organizer',
      position: { x: 200, y: 100 },
      overrides: { llm_profile: 'ollama-qwen2.5-7b' },
    },
  ],
  edges: [
    {
      fromNodeId: 'planner',
      toNodeId: 'worker',
      condition: 'state.plan != null',
    },
  ],
}

describe('schema-to-rf', () => {
  describe('workflowToFlowNodes', () => {
    it('converts workflow nodes to React Flow nodes', () => {
      const nodes = workflowToFlowNodes(SAMPLE_WORKFLOW)
      expect(nodes).toHaveLength(2)

      const planner = nodes.find((n) => n.id === 'planner')
      expect(planner).toBeDefined()
      expect(planner!.type).toBe('entrypoint')
      expect(planner!.data.roleId).toBe('planner')
      expect(planner!.data.label).toBe('Planner')
      expect(planner!.data.isEntrypoint).toBe(true)
      expect(planner!.data.tools).toEqual(['fs.read_file'])
      expect(planner!.position).toEqual({ x: 0, y: 0 })

      const worker = nodes.find((n) => n.id === 'worker')
      expect(worker).toBeDefined()
      expect(worker!.type).toBe('agent')
      expect(worker!.data.roleId).toBe('file-organizer')
      expect(worker!.data.isEntrypoint).toBe(false)
      expect(worker!.position).toEqual({ x: 200, y: 100 })
    })

    it('uses roleId as label when label is missing', () => {
      const nodes = workflowToFlowNodes(SAMPLE_WORKFLOW)
      const worker = nodes.find((n) => n.id === 'worker')
      expect(worker!.data.label).toBe('file-organizer')
    })

    it('sets hasError to false by default', () => {
      const nodes = workflowToFlowNodes(SAMPLE_WORKFLOW)
      for (const node of nodes) {
        expect(node.data.hasError).toBe(false)
      }
    })
  })

  describe('workflowToFlowEdges', () => {
    it('converts workflow edges to React Flow edges', () => {
      const edges = workflowToFlowEdges(SAMPLE_WORKFLOW)
      expect(edges).toHaveLength(1)
      expect(edges[0]!.source).toBe('planner')
      expect(edges[0]!.target).toBe('worker')
      expect(edges[0]!.data!.condition).toBe('state.plan != null')
    })

    it('handles edges without condition', () => {
      const wf: WorkflowDefinition = {
        ...SAMPLE_WORKFLOW,
        edges: [{ fromNodeId: 'planner', toNodeId: 'worker' }],
      }
      const edges = workflowToFlowEdges(wf)
      expect(edges[0]!.data!.condition).toBe('')
    })
  })

  describe('workflowToFlow', () => {
    it('returns both nodes and edges', () => {
      const { nodes, edges } = workflowToFlow(SAMPLE_WORKFLOW)
      expect(nodes).toHaveLength(2)
      expect(edges).toHaveLength(1)
    })

    it('preserves node positions', () => {
      const { nodes } = workflowToFlow(SAMPLE_WORKFLOW)
      const planner = nodes.find((n) => n.id === 'planner')
      expect(planner!.position).toEqual({ x: 0, y: 0 })
      const worker = nodes.find((n) => n.id === 'worker')
      expect(worker!.position).toEqual({ x: 200, y: 100 })
    })
  })
})
