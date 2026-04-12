import { useCallback, useEffect, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Spinner } from '@/components/ui/spinner'
import { createWorkflow } from '@/lib/api/workflow'
import { useChatStore } from '@/stores/chat-store'
import { useRunStore } from '@/stores/run-store'

import { ChatInput } from './ChatInput'
import { ChatTurnMessage } from './ChatTurnMessage'
import { PlannerOutputCard } from './PlannerOutputCard'

type ChatPanelProps = {
  onNavigateToMonitor?: () => void
}

export function ChatPanel({ onNavigateToMonitor }: ChatPanelProps) {
  const { sessionId, turns, latestPlanner, pending, error, newSession, sendTurn } =
    useChatStore()
  const { startRun, subscribe } = useRunStore()
  const scrollRef = useRef<HTMLDivElement>(null)
  const [executing, setExecuting] = useState(false)

  useEffect(() => {
    if (!sessionId) {
      void newSession()
    }
  }, [sessionId, newSession])

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [turns])

  const handleSend = useCallback(
    (text: string) => {
      void sendTurn(text)
    },
    [sendTurn],
  )

  const handleExecute = useCallback(async () => {
    if (!latestPlanner) return
    setExecuting(true)
    try {
      const wf = await createWorkflow(latestPlanner.workflowYaml)
      const workflowId = typeof wf['id'] === 'string' ? wf['id'] : ''
      if (!workflowId) throw new Error('workflow creation returned no id')
      const runId = await startRun({ workflowId })
      subscribe(runId)
      onNavigateToMonitor?.()
    } catch {
      // Error handled by stores
    } finally {
      setExecuting(false)
    }
  }, [latestPlanner, startRun, subscribe, onNavigateToMonitor])

  return (
    <div className="chat-panel">
      <div className="chat-panel__header">
        <span className="chat-panel__session-id">
          {sessionId ? `Session: ${sessionId.slice(0, 8)}...` : 'No session'}
        </span>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            void newSession()
          }}
        >
          New Session
        </Button>
      </div>

      <ScrollArea className="chat-panel__messages">
        <div ref={scrollRef}>
          {turns.map((turn) => (
            <ChatTurnMessage key={turn.id} turn={turn} />
          ))}
          {latestPlanner && (
            <PlannerOutputCard
              output={latestPlanner}
              onExecute={() => {
                void handleExecute()
              }}
              executing={executing}
            />
          )}
          {pending && <Spinner size="sm" />}
          {error && <p className="error">{error}</p>}
        </div>
      </ScrollArea>

      <ChatInput onSend={handleSend} disabled={pending || !sessionId} />
    </div>
  )
}
