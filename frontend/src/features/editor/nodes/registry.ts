// nodeTypes registry for React Flow.

import { AgentNodeView } from '@/features/editor/nodes/AgentNodeView'
import { EntrypointNodeView } from '@/features/editor/nodes/EntrypointNodeView'

import type { NodeTypes } from '@xyflow/react'

export const nodeTypes: NodeTypes = {
  agent: AgentNodeView,
  entrypoint: EntrypointNodeView,
}
