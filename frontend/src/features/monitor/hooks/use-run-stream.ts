import { useEffect } from 'react'

import { useRunStore } from '@/stores/run-store'

export function useRunStream(runId: string | null): void {
  const subscribe = useRunStore((s) => s.subscribe)
  const unsubscribe = useRunStore((s) => s.unsubscribe)

  useEffect(() => {
    if (!runId) return
    subscribe(runId)
    return () => {
      unsubscribe()
    }
  }, [runId, subscribe, unsubscribe])
}
