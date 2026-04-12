import { Badge } from '@/components/ui/badge'
import type { RunStepNode, RunStepStatus } from '@/types/run.types'

type RunStepTreeProps = {
  stepTree: Record<string, RunStepNode>
}

const STEP_STATUS_VARIANT: Record<RunStepStatus, 'default' | 'success' | 'warning' | 'error' | 'info'> = {
  queued: 'default',
  running: 'warning',
  succeeded: 'success',
  failed: 'error',
  blocked: 'info',
}

function StepNode({ node, stepTree, depth }: { node: RunStepNode; stepTree: Record<string, RunStepNode>; depth: number }) {
  return (
    <div className="run-step-node" style={{ paddingLeft: `${(depth * 16).toString()}px` }}>
      <div className="run-step-node__row">
        <Badge variant={STEP_STATUS_VARIANT[node.status]}>{node.kind}</Badge>
        <span className="run-step-node__status">{node.status}</span>
        {node.durationMs !== undefined && (
          <span className="run-step-node__duration">{node.durationMs.toString()}ms</span>
        )}
      </div>
      {node.children.map((childId) => {
        const child = stepTree[childId]
        if (!child) return null
        return <StepNode key={childId} node={child} stepTree={stepTree} depth={depth + 1} />
      })}
    </div>
  )
}

export function RunStepTree({ stepTree }: RunStepTreeProps) {
  // Find root steps (no parentStepId)
  const roots = Object.values(stepTree).filter((s) => !s.parentStepId)

  if (roots.length === 0) {
    return <p className="muted">No steps yet</p>
  }

  return (
    <div className="run-step-tree">
      {roots.map((root) => (
        <StepNode key={root.id} node={root} stepTree={stepTree} depth={0} />
      ))}
    </div>
  )
}
