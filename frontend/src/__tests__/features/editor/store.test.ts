import { describe, it, expect, beforeEach } from 'vitest'

import { useEditorStore } from '@/features/editor/store'

describe('features/editor/store', () => {
  beforeEach(() => {
    useEditorStore.setState({
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
    })
  })

  it('starts with empty state', () => {
    const state = useEditorStore.getState()
    expect(state.nodes).toHaveLength(0)
    expect(state.edges).toHaveLength(0)
    expect(state.dirty).toBe(false)
  })

  it('addNode adds a node and sets dirty', () => {
    useEditorStore.getState().addNode('planner', 'Planner', { x: 0, y: 0 })
    const state = useEditorStore.getState()
    expect(state.nodes).toHaveLength(1)
    expect(state.nodes[0]!.data.roleId).toBe('planner')
    expect(state.nodes[0]!.data.label).toBe('Planner')
    expect(state.dirty).toBe(true)
  })

  it('first node is automatically entrypoint', () => {
    useEditorStore.getState().addNode('planner', 'P', { x: 0, y: 0 })
    expect(useEditorStore.getState().nodes[0]!.data.isEntrypoint).toBe(true)
    expect(useEditorStore.getState().nodes[0]!.type).toBe('entrypoint')
  })

  it('second node is not entrypoint', () => {
    useEditorStore.getState().addNode('planner', 'P', { x: 0, y: 0 })
    useEditorStore.getState().addNode('worker', 'W', { x: 100, y: 100 })
    expect(useEditorStore.getState().nodes[1]!.data.isEntrypoint).toBe(false)
    expect(useEditorStore.getState().nodes[1]!.type).toBe('agent')
  })

  it('removeNode removes a node and its edges', () => {
    useEditorStore.getState().addNode('planner', 'P', { x: 0, y: 0 })
    useEditorStore.getState().addNode('worker', 'W', { x: 100, y: 100 })
    const nodes = useEditorStore.getState().nodes
    const sourceId = nodes[0]!.id
    const targetId = nodes[1]!.id
    useEditorStore.getState().connectNodes(sourceId, targetId, 'always')
    expect(useEditorStore.getState().edges).toHaveLength(1)

    useEditorStore.getState().removeNode(targetId)
    expect(useEditorStore.getState().nodes).toHaveLength(1)
    expect(useEditorStore.getState().edges).toHaveLength(0)
  })

  it('connectNodes creates an edge', () => {
    useEditorStore.getState().addNode('a', 'A', { x: 0, y: 0 })
    useEditorStore.getState().addNode('b', 'B', { x: 100, y: 100 })
    const nodes = useEditorStore.getState().nodes
    useEditorStore.getState().connectNodes(nodes[0]!.id, nodes[1]!.id, 'x > 0')
    const edges = useEditorStore.getState().edges
    expect(edges).toHaveLength(1)
    expect(edges[0]!.source).toBe(nodes[0]!.id)
    expect(edges[0]!.target).toBe(nodes[1]!.id)
    expect(edges[0]!.data!.condition).toBe('x > 0')
  })

  it('removeEdge removes an edge', () => {
    useEditorStore.getState().addNode('a', 'A', { x: 0, y: 0 })
    useEditorStore.getState().addNode('b', 'B', { x: 100, y: 100 })
    const nodes = useEditorStore.getState().nodes
    useEditorStore.getState().connectNodes(nodes[0]!.id, nodes[1]!.id)
    const edgeId = useEditorStore.getState().edges[0]!.id
    useEditorStore.getState().removeEdge(edgeId)
    expect(useEditorStore.getState().edges).toHaveLength(0)
  })

  it('setEntrypoint changes entrypoint', () => {
    useEditorStore.getState().addNode('a', 'A', { x: 0, y: 0 })
    useEditorStore.getState().addNode('b', 'B', { x: 100, y: 100 })
    const nodes = useEditorStore.getState().nodes
    const bId = nodes[1]!.id

    useEditorStore.getState().setEntrypoint(bId)
    const updated = useEditorStore.getState().nodes
    expect(updated.find((n) => n.id === bId)!.data.isEntrypoint).toBe(true)
    expect(updated.find((n) => n.id === nodes[0]!.id)!.data.isEntrypoint).toBe(false)
  })

  it('updateNodeData updates node data', () => {
    useEditorStore.getState().addNode('a', 'A', { x: 0, y: 0 })
    const nodeId = useEditorStore.getState().nodes[0]!.id
    useEditorStore.getState().updateNodeData(nodeId, {
      label: 'Updated',
      tools: ['fs.write_file'],
    })
    const node = useEditorStore.getState().nodes[0]!
    expect(node.data.label).toBe('Updated')
    expect(node.data.tools).toEqual(['fs.write_file'])
  })

  it('updateEdgeCondition updates edge condition', () => {
    useEditorStore.getState().addNode('a', 'A', { x: 0, y: 0 })
    useEditorStore.getState().addNode('b', 'B', { x: 100, y: 100 })
    const nodes = useEditorStore.getState().nodes
    useEditorStore.getState().connectNodes(nodes[0]!.id, nodes[1]!.id)
    const edgeId = useEditorStore.getState().edges[0]!.id

    useEditorStore.getState().updateEdgeCondition(edgeId, 'state.done')
    expect(useEditorStore.getState().edges[0]!.data!.condition).toBe('state.done')
  })

  it('selectNode sets selectedNodeId', () => {
    useEditorStore.getState().addNode('a', 'A', { x: 0, y: 0 })
    const nodeId = useEditorStore.getState().nodes[0]!.id
    useEditorStore.getState().selectNode(nodeId)
    expect(useEditorStore.getState().selectedNodeId).toBe(nodeId)
  })

  it('removeNode clears selectedNodeId if selected', () => {
    useEditorStore.getState().addNode('a', 'A', { x: 0, y: 0 })
    const nodeId = useEditorStore.getState().nodes[0]!.id
    useEditorStore.getState().selectNode(nodeId)
    useEditorStore.getState().removeNode(nodeId)
    expect(useEditorStore.getState().selectedNodeId).toBeNull()
  })

  it('newWorkflow resets state', () => {
    useEditorStore.getState().addNode('a', 'A', { x: 0, y: 0 })
    useEditorStore.getState().newWorkflow()
    const state = useEditorStore.getState()
    expect(state.nodes).toHaveLength(0)
    expect(state.edges).toHaveLength(0)
    expect(state.dirty).toBe(false)
    expect(state.workflowId).toBeNull()
    expect(state.workflowName).toBe('New Workflow')
  })

  it('syncYamlFromFlow generates yaml', () => {
    useEditorStore.getState().addNode('planner', 'Planner', { x: 0, y: 0 })
    useEditorStore.getState().syncYamlFromFlow()
    const yaml = useEditorStore.getState().yamlText
    expect(yaml).toContain('name: New Workflow')
    expect(yaml).toContain('role: planner')
  })

  it('syncFlowFromYaml parses yaml into nodes', () => {
    const yaml = `
version: 1
name: From YAML
entrypoint: n1
nodes:
  - id: n1
    role: planner
    position: {x: 0, y: 0}
edges: []
`
    useEditorStore.getState().syncFlowFromYaml(yaml)
    const state = useEditorStore.getState()
    expect(state.workflowName).toBe('From YAML')
    expect(state.nodes).toHaveLength(1)
    expect(state.nodes[0]!.data.roleId).toBe('planner')
  })

  it('syncFlowFromYaml sets error on invalid yaml', () => {
    useEditorStore.getState().syncFlowFromYaml('{{invalid yaml::')
    expect(useEditorStore.getState().error).toBeTruthy()
  })
})
