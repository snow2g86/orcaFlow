// Editor Zustand store — 에디터 상태 관리.

import { create } from 'zustand'

import { applyBfsLayout } from '@/features/editor/lib/layout'
import { flowToWorkflow, workflowToYaml, yamlToWorkflow } from '@/features/editor/lib/rf-to-schema'
import { workflowToFlow } from '@/features/editor/lib/schema-to-rf'
import type {
  AgentFlowEdge,
  AgentFlowNode,
  AgentNodeData,
  EditorMode,
  FlowEdgeData,
  ValidationError,
  WorkflowDefinition,
} from '@/features/editor/types'
import * as workflowApi from '@/lib/api/workflow'
import type { WorkflowSummary } from '@/types/workflow.types'

type EditorState = {
  // Workflow metadata
  workflowId: string | null
  workflowName: string
  workflowMeta: {
    description?: string | undefined
    version: number
    author?: string | undefined
    policyId?: string | undefined
    defaultLlmProfileId?: string | undefined
  }

  // React Flow state
  nodes: AgentFlowNode[]
  edges: AgentFlowEdge[]

  // Editor state
  mode: EditorMode
  yamlText: string
  dirty: boolean
  selectedNodeId: string | null
  validationErrors: ValidationError[]
  saving: boolean
  loading: boolean
  error: string | null

  // Workflow list
  workflows: WorkflowSummary[]

  // Actions
  setNodes: (nodes: AgentFlowNode[]) => void
  setEdges: (edges: AgentFlowEdge[]) => void
  addNode: (roleId: string, label: string, position: { x: number; y: number }) => void
  removeNode: (nodeId: string) => void
  connectNodes: (sourceId: string, targetId: string, condition?: string) => void
  removeEdge: (edgeId: string) => void
  selectNode: (nodeId: string | null) => void
  updateNodeData: (nodeId: string, data: Partial<AgentNodeData>) => void
  setEntrypoint: (nodeId: string) => void
  updateEdgeCondition: (edgeId: string, condition: string) => void
  setMode: (mode: EditorMode) => void
  syncYamlFromFlow: () => void
  syncFlowFromYaml: (yamlStr: string) => void
  setWorkflowName: (name: string) => void
  autoLayout: () => void
  loadWorkflowList: () => Promise<void>
  loadWorkflow: (id: string) => Promise<void>
  saveWorkflow: () => Promise<void>
  validateWorkflow: () => Promise<void>
  newWorkflow: () => void
}

let nodeCounter = 0

export const useEditorStore = create<EditorState>((set, get) => ({
  workflowId: null,
  workflowName: 'New Workflow',
  workflowMeta: { version: 1 },
  nodes: [],
  edges: [],
  mode: 'visual',
  yamlText: '',
  dirty: false,
  selectedNodeId: null,
  validationErrors: [],
  saving: false,
  loading: false,
  error: null,
  workflows: [],

  setNodes: (nodes) => set({ nodes, dirty: true }),

  setEdges: (edges) => set({ edges, dirty: true }),

  addNode: (roleId, label, position) => {
    nodeCounter += 1
    const id = `node-${nodeCounter.toString()}`
    const { nodes } = get()
    const isFirst = nodes.length === 0
    const newNode: AgentFlowNode = {
      id,
      type: isFirst ? 'entrypoint' : 'agent',
      position,
      data: {
        roleId,
        label,
        overrides: {},
        isEntrypoint: isFirst,
        tools: [],
        hasError: false,
      },
    }
    set({ nodes: [...nodes, newNode], dirty: true })
  },

  removeNode: (nodeId) => {
    const { nodes, edges, selectedNodeId } = get()
    const filtered = nodes.filter((n) => n.id !== nodeId)
    const filteredEdges = edges.filter(
      (e) => e.source !== nodeId && e.target !== nodeId,
    )
    set({
      nodes: filtered,
      edges: filteredEdges,
      dirty: true,
      selectedNodeId: selectedNodeId === nodeId ? null : selectedNodeId,
    })
  },

  connectNodes: (sourceId, targetId, condition) => {
    const { edges } = get()
    const edgeId = `e-${sourceId}-${targetId}-${edges.length.toString()}`
    const edgeData: FlowEdgeData = {
      condition: condition ?? '',
      label: condition ?? '',
      hasError: false,
    }
    const newEdge: AgentFlowEdge = {
      id: edgeId,
      source: sourceId,
      target: targetId,
      label: condition ?? undefined,
      data: edgeData,
    }
    set({ edges: [...edges, newEdge], dirty: true })
  },

  removeEdge: (edgeId) => {
    const { edges } = get()
    set({ edges: edges.filter((e) => e.id !== edgeId), dirty: true })
  },

  selectNode: (nodeId) => set({ selectedNodeId: nodeId }),

  updateNodeData: (nodeId, data) => {
    const { nodes } = get()
    set({
      nodes: nodes.map((n) => {
        if (n.id !== nodeId) return n
        return {
          ...n,
          data: { ...n.data, ...data },
        }
      }),
      dirty: true,
    })
  },

  setEntrypoint: (nodeId) => {
    const { nodes } = get()
    set({
      nodes: nodes.map((n) => ({
        ...n,
        type: n.id === nodeId ? 'entrypoint' : 'agent',
        data: {
          ...n.data,
          isEntrypoint: n.id === nodeId,
        },
      })),
      dirty: true,
    })
  },

  updateEdgeCondition: (edgeId, condition) => {
    const { edges } = get()
    set({
      edges: edges.map((e) => {
        if (e.id !== edgeId) return e
        return {
          ...e,
          label: condition || undefined,
          data: {
            condition,
            label: condition,
            hasError: e.data?.hasError ?? false,
          },
        }
      }),
      dirty: true,
    })
  },

  setMode: (mode) => {
    if (mode === 'yaml') {
      get().syncYamlFromFlow()
    }
    set({ mode })
  },

  syncYamlFromFlow: () => {
    const { nodes, edges, workflowName, workflowMeta, workflowId } = get()
    const wf = flowToWorkflow(nodes, edges, {
      id: workflowId ?? undefined,
      name: workflowName,
      ...workflowMeta,
    })
    const yamlText = workflowToYaml(wf)
    set({ yamlText })
  },

  syncFlowFromYaml: (yamlStr) => {
    try {
      const wf = yamlToWorkflow(yamlStr)
      const { nodes, edges } = workflowToFlow(wf)
      set({
        nodes,
        edges,
        workflowName: wf.name,
        workflowMeta: {
          description: wf.description,
          version: wf.version,
          author: wf.author,
          policyId: wf.policyId,
          defaultLlmProfileId: wf.defaultLlmProfileId,
        },
        yamlText: yamlStr,
        dirty: true,
        error: null,
      })
    } catch (e) {
      set({ error: e instanceof Error ? e.message : 'YAML parse error' })
    }
  },

  setWorkflowName: (name) => set({ workflowName: name, dirty: true }),

  autoLayout: () => {
    const { nodes, edges } = get()
    const layouted = applyBfsLayout(nodes, edges)
    set({ nodes: layouted, dirty: true })
  },

  loadWorkflowList: async () => {
    try {
      const workflows = await workflowApi.listWorkflows()
      set({ workflows })
    } catch (e) {
      set({ error: e instanceof Error ? e.message : 'Failed to load workflows' })
    }
  },

  loadWorkflow: async (id) => {
    set({ loading: true, error: null })
    try {
      const raw = await workflowApi.getWorkflow(id)
      const wf: WorkflowDefinition = {
        id: raw.id,
        name: raw.name,
        description: raw.description,
        version: raw.version,
        author: raw.author,
        nodes: raw.nodes.map((n) => ({
          id: n.id,
          roleId: n.roleId,
          label: n.label,
          position: n.position,
          overrides: n.overrides,
        })),
        edges: raw.edges.map((e) => ({
          fromNodeId: e.fromNodeId,
          toNodeId: e.toNodeId,
          condition: e.condition,
          label: e.label,
        })),
        entrypointNodeId: raw.entrypointNodeId,
        policyId: raw.policyId,
        defaultLlmProfileId: raw.defaultLlmProfileId,
      }
      const { nodes, edges } = workflowToFlow(wf)
      set({
        workflowId: raw.id,
        workflowName: raw.name,
        workflowMeta: {
          description: raw.description,
          version: raw.version,
          author: raw.author,
          policyId: raw.policyId,
          defaultLlmProfileId: raw.defaultLlmProfileId,
        },
        nodes,
        edges,
        dirty: false,
        loading: false,
        validationErrors: [],
      })
    } catch (e) {
      set({
        error: e instanceof Error ? e.message : 'Failed to load workflow',
        loading: false,
      })
    }
  },

  saveWorkflow: async () => {
    const { nodes, edges, workflowName, workflowMeta, workflowId } = get()
    set({ saving: true, error: null })
    try {
      const wf = flowToWorkflow(nodes, edges, {
        id: workflowId ?? undefined,
        name: workflowName,
        ...workflowMeta,
      })
      const yamlStr = workflowToYaml(wf)
      const result = await workflowApi.createWorkflow(yamlStr)
      set({
        workflowId: result.id,
        saving: false,
        dirty: false,
      })
    } catch (e) {
      set({
        error: e instanceof Error ? e.message : 'Failed to save',
        saving: false,
      })
    }
  },

  validateWorkflow: async () => {
    const { nodes, edges, workflowName, workflowMeta, workflowId } = get()
    set({ error: null })
    try {
      const wf = flowToWorkflow(nodes, edges, {
        id: workflowId ?? undefined,
        name: workflowName,
        ...workflowMeta,
      })
      const yamlStr = workflowToYaml(wf)
      const result = await workflowApi.validateWorkflow(yamlStr)
      if (result.ok) {
        // Clear all error highlights
        set({
          validationErrors: [],
          nodes: nodes.map((n) => ({ ...n, data: { ...n.data, hasError: false } })),
          edges: edges.map((e) => ({
            ...e,
            data: { ...e.data, hasError: false } as FlowEdgeData,
          })),
        })
      } else {
        const errors = result.errors ?? []
        // Highlight errored nodes/edges
        const errorNodeIds = new Set(errors.filter((e) => e.nodeId).map((e) => e.nodeId!))
        const errorEdgeIndices = new Set(
          errors.filter((e) => e.edgeIndex !== undefined).map((e) => e.edgeIndex!),
        )
        set({
          validationErrors: errors,
          nodes: nodes.map((n) => ({
            ...n,
            data: { ...n.data, hasError: errorNodeIds.has(n.id) },
          })),
          edges: edges.map((e, i) => ({
            ...e,
            data: {
              condition: e.data?.condition ?? '',
              label: e.data?.label ?? '',
              hasError: errorEdgeIndices.has(i),
            },
          })),
        })
      }
    } catch (e) {
      set({ error: e instanceof Error ? e.message : 'Validation failed' })
    }
  },

  newWorkflow: () => {
    nodeCounter = 0
    set({
      workflowId: null,
      workflowName: 'New Workflow',
      workflowMeta: { version: 1 },
      nodes: [],
      edges: [],
      yamlText: '',
      dirty: false,
      selectedNodeId: null,
      validationErrors: [],
      error: null,
    })
  },
}))
