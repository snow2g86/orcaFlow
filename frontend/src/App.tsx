import { useCallback, useEffect, useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ApprovalDialog, ApprovalList } from '@/features/approval'
import { ChatPanel } from '@/features/chat'
import { WorkflowEditor } from '@/features/editor'
import { RunMonitor } from '@/features/monitor'
import { PolicyManager } from '@/features/policy'
import { LLMProfileEditor, LLMProfileList, ProviderAddForm, ProviderList } from '@/features/settings'
import { useAppStore } from '@/stores/app-store'

type TabId = 'chat' | 'monitor' | 'editor' | 'policy' | 'settings'

export function App() {
  const { status, endpoint, loading, error, refresh } = useAppStore()
  const [activeTab, setActiveTab] = useState<TabId>('chat')

  useEffect(() => {
    void refresh()
    const id = window.setInterval(() => {
      void refresh()
    }, 5000)
    return () => window.clearInterval(id)
  }, [refresh])

  const navigateToMonitor = useCallback(() => {
    setActiveTab('monitor')
  }, [])

  const sidecarReady = status?.sidecar.state === 'ready' && endpoint !== null

  return (
    <main className="app-layout">
      <header className="top-bar">
        <h1 className="top-bar__title">OrcaFlow</h1>
        <div className="top-bar__status">
          {loading && !status && <Badge variant="info">Loading...</Badge>}
          {error && <Badge variant="error">Error</Badge>}
          {status?.sidecar.state === 'starting' && (
            <Badge variant="info">Starting...</Badge>
          )}
          {status?.sidecar.state === 'failed' && (
            <Badge variant="error">Failed</Badge>
          )}
          {sidecarReady && <Badge variant="success">Ready</Badge>}
          <ApprovalList />
        </div>
      </header>

      <nav className="tab-bar">
        {(['chat', 'monitor', 'editor', 'policy', 'settings'] as const).map(
          (tab) => (
            <Button
              key={tab}
              variant={activeTab === tab ? 'primary' : 'ghost'}
              size="sm"
              onClick={() => setActiveTab(tab)}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </Button>
          ),
        )}
      </nav>

      <section className="main-area">
        {activeTab === 'settings' ? (
          <div className="settings-panel">
            <ProviderList />
            <ProviderAddForm />
            <LLMProfileList />
            <LLMProfileEditor />
          </div>
        ) : !sidecarReady ? (
          <div className="main-area__loading">
            {status?.sidecar.state === 'failed' ? (
              <p className="error">
                Sidecar failed:{' '}
                {status.sidecar.state === 'failed' ? status.sidecar.reason : ''}
              </p>
            ) : (
              <p>Waiting for sidecar to be ready...</p>
            )}
          </div>
        ) : (
          <>
            {activeTab === 'chat' && (
              <ChatPanel onNavigateToMonitor={navigateToMonitor} />
            )}
            {activeTab === 'monitor' && <RunMonitor />}
            {activeTab === 'editor' && <WorkflowEditor />}
            {activeTab === 'policy' && <PolicyManager />}
          </>
        )}
      </section>

      <ApprovalDialog />
    </main>
  )
}
