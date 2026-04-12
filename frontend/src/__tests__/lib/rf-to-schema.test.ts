import { describe, it, expect } from 'vitest'

import { flowToWorkflow, workflowToYaml, yamlToWorkflow } from '@/features/editor/lib/rf-to-schema'
import { workflowToFlow } from '@/features/editor/lib/schema-to-rf'
import type { AgentFlowEdge, AgentFlowNode, WorkflowDefinition } from '@/features/editor/types'

const SAMPLE_NODES: AgentFlowNode[] = [
  {
    id: 'planner',
    type: 'entrypoint',
    position: { x: 0, y: 0 },
    data: {
      roleId: 'planner',
      label: 'Planner',
      overrides: {},
      isEntrypoint: true,
      tools: [],
      hasError: false,
    },
  },
  {
    id: 'worker',
    type: 'agent',
    position: { x: 200, y: 100 },
    data: {
      roleId: 'file-organizer',
      label: 'Worker',
      overrides: { llm_profile: 'ollama-qwen2.5-7b' },
      isEntrypoint: false,
      tools: ['fs.write_file'],
      hasError: false,
    },
  },
]

const SAMPLE_EDGES: AgentFlowEdge[] = [
  {
    id: 'e-planner-worker-0',
    source: 'planner',
    target: 'worker',
    data: {
      condition: 'state.plan != null',
      label: 'state.plan != null',
      hasError: false,
    },
  },
]

describe('rf-to-schema', () => {
  describe('flowToWorkflow', () => {
    it('converts RF nodes/edges to WorkflowDefinition', () => {
      const wf = flowToWorkflow(SAMPLE_NODES, SAMPLE_EDGES, {
        name: 'Test',
      })
      expect(wf.name).toBe('Test')
      expect(wf.entrypointNodeId).toBe('planner')
      expect(wf.nodes).toHaveLength(2)
      expect(wf.edges).toHaveLength(1)

      const planner = wf.nodes.find((n) => n.id === 'planner')
      expect(planner!.roleId).toBe('planner')
      expect(planner!.position).toEqual({ x: 0, y: 0 })

      const worker = wf.nodes.find((n) => n.id === 'worker')
      expect(worker!.roleId).toBe('file-organizer')
      expect(worker!.overrides).toEqual({ llm_profile: 'ollama-qwen2.5-7b' })

      expect(wf.edges[0]!.fromNodeId).toBe('planner')
      expect(wf.edges[0]!.toNodeId).toBe('worker')
      expect(wf.edges[0]!.condition).toBe('state.plan != null')
    })

    it('preserves label when different from roleId', () => {
      const wf = flowToWorkflow(SAMPLE_NODES, SAMPLE_EDGES, { name: 'Test' })
      const planner = wf.nodes.find((n) => n.id === 'planner')
      expect(planner!.label).toBe('Planner')
    })
  })

  describe('workflowToYaml', () => {
    it('serializes to YAML with snake_case keys', () => {
      const wf = flowToWorkflow(SAMPLE_NODES, SAMPLE_EDGES, {
        name: 'Test WF',
        version: 1,
      })
      const yamlStr = workflowToYaml(wf)
      expect(yamlStr).toContain('name: Test WF')
      expect(yamlStr).toContain('entrypoint: planner')
      expect(yamlStr).toContain('role: planner')
      expect(yamlStr).toContain("condition: state.plan != null")
    })
  })

  describe('yamlToWorkflow', () => {
    it('parses YAML back to WorkflowDefinition', () => {
      const yamlStr = `
version: 1
name: Test WF
entrypoint: planner
nodes:
  - id: planner
    role: planner
    position: {x: 0, y: 0}
  - id: worker
    role: file-organizer
    position: {x: 200, y: 100}
    overrides:
      llm_profile: ollama-qwen2.5-7b
edges:
  - from: planner
    to: worker
    condition: "state.plan != null"
`
      const wf = yamlToWorkflow(yamlStr)
      expect(wf.name).toBe('Test WF')
      expect(wf.entrypointNodeId).toBe('planner')
      expect(wf.nodes).toHaveLength(2)
      expect(wf.nodes[0]!.roleId).toBe('planner')
      expect(wf.nodes[1]!.roleId).toBe('file-organizer')
      expect(wf.edges[0]!.condition).toBe('state.plan != null')
    })
  })

  describe('roundtrip RF -> YAML -> RF', () => {
    it('preserves data through RF -> YAML -> WorkflowDef -> RF roundtrip', () => {
      // RF -> WorkflowDefinition
      const wf1 = flowToWorkflow(SAMPLE_NODES, SAMPLE_EDGES, {
        name: 'Roundtrip Test',
        version: 1,
      })

      // WorkflowDefinition -> YAML
      const yamlStr = workflowToYaml(wf1)

      // YAML -> WorkflowDefinition
      const wf2 = yamlToWorkflow(yamlStr)

      // WorkflowDefinition -> RF
      const { nodes, edges } = workflowToFlow(wf2)

      // Verify nodes
      expect(nodes).toHaveLength(2)
      const planner = nodes.find((n) => n.id === 'planner')
      expect(planner).toBeDefined()
      expect(planner!.data.roleId).toBe('planner')
      expect(planner!.data.isEntrypoint).toBe(true)
      expect(planner!.position).toEqual({ x: 0, y: 0 })

      const worker = nodes.find((n) => n.id === 'worker')
      expect(worker).toBeDefined()
      expect(worker!.data.roleId).toBe('file-organizer')

      // Verify edges
      expect(edges).toHaveLength(1)
      expect(edges[0]!.source).toBe('planner')
      expect(edges[0]!.target).toBe('worker')
      expect(edges[0]!.data!.condition).toBe('state.plan != null')
    })
  })

  describe('roundtrip WorkflowDef -> RF -> WorkflowDef', () => {
    it('preserves data through WorkflowDef -> RF -> WorkflowDef', () => {
      const original: WorkflowDefinition = {
        name: 'Original',
        version: 1,
        entrypointNodeId: 'n1',
        nodes: [
          { id: 'n1', roleId: 'planner', position: { x: 10, y: 20 } },
          { id: 'n2', roleId: 'worker', position: { x: 300, y: 200 } },
        ],
        edges: [
          { fromNodeId: 'n1', toNodeId: 'n2', condition: 'x > 0' },
        ],
      }

      const { nodes, edges } = workflowToFlow(original)
      const recovered = flowToWorkflow(nodes, edges, {
        name: original.name,
        version: original.version,
      })

      expect(recovered.name).toBe('Original')
      expect(recovered.entrypointNodeId).toBe('n1')
      expect(recovered.nodes).toHaveLength(2)
      expect(recovered.nodes[0]!.roleId).toBe('planner')
      expect(recovered.nodes[0]!.position).toEqual({ x: 10, y: 20 })
      expect(recovered.edges[0]!.fromNodeId).toBe('n1')
      expect(recovered.edges[0]!.toNodeId).toBe('n2')
      expect(recovered.edges[0]!.condition).toBe('x > 0')
    })
  })
})
