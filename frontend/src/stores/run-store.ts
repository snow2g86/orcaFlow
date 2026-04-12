import { create } from 'zustand'

import { cancelRun as apiCancelRun, getRun, startRun as apiStartRun } from '@/lib/api/run'
import { subscribeRunEvents } from '@/lib/ipc/run-stream'
import type { RunEvent } from '@/types/event.types'
import type { RunStartRequest, RunStatus, RunStepNode, RunSummary } from '@/types/run.types'

const MAX_EVENTS = 500

type LiveRunState = {
  runId: string
  events: RunEvent[]
  status: RunStatus
  stepTree: Record<string, RunStepNode>
  lastEventId: number | null
}

type RunStore = {
  runs: Record<string, RunSummary>
  liveRun: LiveRunState | null
  error: string | null
  startRun: (opts: RunStartRequest) => Promise<string>
  cancelRun: (runId: string) => Promise<void>
  subscribe: (runId: string) => void
  unsubscribe: () => void
  fetchRun: (runId: string) => Promise<void>
}

let unsubFn: (() => void) | null = null

export const useRunStore = create<RunStore>((set, get) => ({
  runs: {},
  liveRun: null,
  error: null,

  startRun: async (opts) => {
    try {
      const res = await apiStartRun(opts)
      const summary: RunSummary = {
        runId: res.runId,
        workflowId: opts.workflowId,
        status: 'pending',
        startedAt: res.startedAt,
      }
      set((s) => ({
        runs: { ...s.runs, [res.runId]: summary },
        error: null,
      }))
      return res.runId
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      set({ error: msg })
      throw e
    }
  },

  cancelRun: async (runId) => {
    try {
      await apiCancelRun(runId)
      set((s) => {
        const run = s.runs[runId]
        if (!run) return s
        return {
          runs: { ...s.runs, [runId]: { ...run, status: 'cancelled' as RunStatus } },
        }
      })
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      set({ error: msg })
    }
  },

  subscribe: (runId) => {
    // Unsubscribe from previous
    get().unsubscribe()

    const live: LiveRunState = {
      runId,
      events: [],
      status: 'running',
      stepTree: {},
      lastEventId: null,
    }
    set({ liveRun: live })

    unsubFn = subscribeRunEvents(runId, {
      onEvent: (event) => {
        set((s) => {
          if (!s.liveRun || s.liveRun.runId !== runId) return s
          const events =
            s.liveRun.events.length >= MAX_EVENTS
              ? [...s.liveRun.events.slice(1), event]
              : [...s.liveRun.events, event]

          let { status, stepTree } = s.liveRun

          // Update status from run events
          if (event.event === 'run.succeeded') status = 'succeeded'
          else if (event.event === 'run.failed') status = 'failed'
          else if (event.event === 'run.cancelled') status = 'cancelled'
          else if (event.event === 'run_step.started') {
            const p = event.payload
            const stepId = typeof p['stepId'] === 'string' ? p['stepId'] : ''
            if (stepId) {
              const newNode: RunStepNode = {
                id: stepId,
                runId,
                kind: (typeof p['kind'] === 'string' ? p['kind'] : 'tool_call') as RunStepNode['kind'],
                status: 'running',
                startedAt: typeof p['at'] === 'string' ? p['at'] : new Date().toISOString(),
                payload: {},
                children: [],
              }
              if (typeof p['parentStepId'] === 'string') newNode.parentStepId = p['parentStepId']
              if (typeof p['nodeId'] === 'string') newNode.nodeId = p['nodeId']
              stepTree = {
                ...stepTree,
                [stepId]: newNode,
              }
              // Add to parent's children
              const parentId =
                typeof p['parentStepId'] === 'string' ? p['parentStepId'] : undefined
              if (parentId && stepTree[parentId]) {
                stepTree = {
                  ...stepTree,
                  [parentId]: {
                    ...stepTree[parentId],
                    children: [...(stepTree[parentId]?.children ?? []), stepId],
                  },
                }
              }
            }
          } else if (
            event.event === 'run_step.succeeded' ||
            event.event === 'run_step.failed'
          ) {
            const p = event.payload
            const stepId = typeof p['stepId'] === 'string' ? p['stepId'] : ''
            const existing = stepTree[stepId]
            if (stepId && existing) {
              const updatedNode: RunStepNode = {
                ...existing,
                status: event.event === 'run_step.succeeded' ? 'succeeded' : 'failed',
                endedAt: typeof p['at'] === 'string' ? p['at'] : new Date().toISOString(),
              }
              if (typeof p['durationMs'] === 'number') updatedNode.durationMs = p['durationMs']
              stepTree = {
                ...stepTree,
                [stepId]: updatedNode,
              }
            }
          }

          // Update run summary
          const run = s.runs[runId]
          const updatedRuns = run
            ? { ...s.runs, [runId]: { ...run, status } }
            : s.runs

          return {
            liveRun: { ...s.liveRun, events, status, stepTree, lastEventId: event.id },
            runs: updatedRuns,
          }
        })
      },
      onError: (err) => {
        set({ error: err.message })
      },
      onClose: () => {
        // Stream closed normally
      },
    })
  },

  unsubscribe: () => {
    if (unsubFn) {
      unsubFn()
      unsubFn = null
    }
  },

  fetchRun: async (runId) => {
    try {
      const data = await getRun(runId)
      const summary: RunSummary = {
        runId: data.runId,
        workflowId: typeof data['workflowId'] === 'string' ? data['workflowId'] : '',
        status: data.status,
        startedAt: data.startedAt,
      }
      if (data.endedAt) summary.endedAt = data.endedAt
      if (data.error) summary.error = data.error
      set((s) => ({
        runs: { ...s.runs, [runId]: summary },
      }))
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      set({ error: msg })
    }
  },
}))
