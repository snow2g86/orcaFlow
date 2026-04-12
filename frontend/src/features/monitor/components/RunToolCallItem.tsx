import { Badge } from '@/components/ui/badge'
import type { RunEvent } from '@/types/event.types'

type RunToolCallItemProps = {
  event: RunEvent
}

export function RunToolCallItem({ event }: RunToolCallItemProps) {
  const toolId =
    typeof event.payload['toolId'] === 'string' ? event.payload['toolId'] : 'unknown'
  const status = event.event.includes('succeeded')
    ? 'success' as const
    : event.event.includes('failed')
      ? 'error' as const
      : 'warning' as const

  return (
    <div className="run-tool-call-item">
      <Badge variant={status}>{toolId}</Badge>
      <pre>{JSON.stringify(event.payload, null, 2)}</pre>
    </div>
  )
}
