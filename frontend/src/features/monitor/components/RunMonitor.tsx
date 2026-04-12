import { useCallback, useMemo, useState } from 'react'

import { Button } from '@/components/ui/button'
import { useRunStore } from '@/stores/run-store'

import { useRunStream } from '../hooks/use-run-stream'

import { RunEventLog } from './RunEventLog'
import { RunHeader } from './RunHeader'
import { RunStepTree } from './RunStepTree'

export function RunMonitor() {
  const { runs, liveRun, error, cancelRun } = useRunStore()
  const runList = useMemo(
    () =>
      Object.values(runs)
        .sort((a, b) => b.startedAt.localeCompare(a.startedAt))
        .slice(0, 20),
    [runs],
  )

  const [selectedRunId, setSelectedRunId] = useState<string | null>(
    liveRun?.runId ?? null,
  )

  // Keep selectedRunId in sync with liveRun
  const activeRunId = selectedRunId ?? liveRun?.runId ?? null
  useRunStream(activeRunId)

  const selectedRun = activeRunId ? runs[activeRunId] : undefined

  const handleCancel = useCallback(() => {
    if (activeRunId) {
      void cancelRun(activeRunId)
    }
  }, [activeRunId, cancelRun])

  return (
    <div className="run-monitor">
      <div className="run-monitor__sidebar">
        <h3>Runs</h3>
        {runList.length === 0 && <p className="muted">No runs yet</p>}
        {runList.map((run) => (
          <Button
            key={run.runId}
            variant={run.runId === activeRunId ? 'primary' : 'ghost'}
            size="sm"
            className="run-monitor__run-item"
            onClick={() => {
              setSelectedRunId(run.runId)
            }}
          >
            {run.runId.slice(0, 8)}... ({run.status})
          </Button>
        ))}
      </div>

      <div className="run-monitor__main">
        {selectedRun && (
          <>
            <RunHeader run={selectedRun} onCancel={handleCancel} />
            {liveRun && liveRun.runId === activeRunId && (
              <>
                <div className="run-monitor__section">
                  <h3>Step Tree</h3>
                  <RunStepTree stepTree={liveRun.stepTree} />
                </div>
                <div className="run-monitor__section">
                  <h3>Event Log</h3>
                  <RunEventLog events={liveRun.events} />
                </div>
              </>
            )}
          </>
        )}
        {!selectedRun && <p className="muted">Select a run to monitor</p>}
        {error && <p className="error">{error}</p>}
      </div>
    </div>
  )
}
