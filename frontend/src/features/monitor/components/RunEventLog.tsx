import { useMemo, useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import type { RunEvent } from '@/types/event.types'

type RunEventLogProps = {
  events: RunEvent[]
}

type EventFilter = 'all' | 'tool_call' | 'llm_call' | 'approval' | 'run_state'

const FILTERS: { value: EventFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'tool_call', label: 'Tool' },
  { value: 'llm_call', label: 'LLM' },
  { value: 'approval', label: 'Approval' },
  { value: 'run_state', label: 'Run' },
]

function matchesFilter(event: RunEvent, filter: EventFilter): boolean {
  if (filter === 'all') return true
  if (filter === 'tool_call') return event.event.startsWith('tool_call')
  if (filter === 'llm_call') return event.event.startsWith('llm_call')
  if (filter === 'approval') return event.event.startsWith('approval')
  if (filter === 'run_state') return event.event.startsWith('run.')
  return true
}

export function RunEventLog({ events }: RunEventLogProps) {
  const [filter, setFilter] = useState<EventFilter>('all')

  const filtered = useMemo(
    () => events.filter((e) => matchesFilter(e, filter)),
    [events, filter],
  )

  const hasGap = events.some((e) => e.event === 'run.gap')

  return (
    <div className="run-event-log">
      {hasGap && (
        <div className="run-event-log__gap-warning">
          Events may have been lost. Some events are missing from the stream.
        </div>
      )}
      <div className="run-event-log__filters">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            className={`run-event-log__filter ${filter === f.value ? 'run-event-log__filter--active' : ''}`}
            onClick={() => {
              setFilter(f.value)
            }}
          >
            {f.label}
          </button>
        ))}
      </div>
      <ScrollArea className="run-event-log__list">
        {filtered.map((event) => (
          <div key={event.id} className="run-event-log__item">
            <Badge variant="default">{event.event}</Badge>
            <span className="run-event-log__time">
              {new Date(event.at).toLocaleTimeString()}
            </span>
            <pre className="run-event-log__payload">
              {JSON.stringify(event.payload, null, 2)}
            </pre>
          </div>
        ))}
        {filtered.length === 0 && <p className="muted">No events</p>}
      </ScrollArea>
    </div>
  )
}
