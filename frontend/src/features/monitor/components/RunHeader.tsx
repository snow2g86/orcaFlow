import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { RunStatus, RunSummary } from '@/types/run.types'

type RunHeaderProps = {
  run: RunSummary
  onCancel: () => void
}

const STATUS_VARIANT: Record<RunStatus, 'default' | 'success' | 'warning' | 'error' | 'info'> = {
  pending: 'info',
  running: 'warning',
  awaiting_approval: 'warning',
  succeeded: 'success',
  failed: 'error',
  cancelled: 'default',
}

export function RunHeader({ run, onCancel }: RunHeaderProps) {
  const isRunning = run.status === 'running' || run.status === 'awaiting_approval'

  return (
    <div className="run-header">
      <div className="run-header__info">
        <span className="run-header__id">{run.runId.slice(0, 8)}...</span>
        <Badge variant={STATUS_VARIANT[run.status]}>{run.status}</Badge>
      </div>
      <div className="run-header__actions">
        {isRunning && (
          <Button variant="danger" size="sm" onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </div>
  )
}
