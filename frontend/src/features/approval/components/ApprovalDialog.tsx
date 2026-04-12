import { useCallback, useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { useApprovalStore } from '@/stores/approval-store'

import { DiffPreview } from './DiffPreview'

export function ApprovalDialog() {
  const { pending, decide } = useApprovalStore()
  const current = pending[0]

  const [remaining, setRemaining] = useState<number>(0)

  useEffect(() => {
    if (!current) return
    setRemaining(current.ttlSeconds)

    const interval = window.setInterval(() => {
      setRemaining((prev) => {
        if (prev <= 1) {
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => {
      window.clearInterval(interval)
    }
  }, [current])

  // Auto-dismiss when TTL expires
  useEffect(() => {
    if (current && remaining === 0) {
      useApprovalStore.getState().removePending(current.id)
    }
  }, [remaining, current])

  const handleApprove = useCallback(() => {
    if (!current) return
    void decide(current.id, 'approve')
  }, [current, decide])

  const handleReject = useCallback(() => {
    if (!current) return
    void decide(current.id, 'reject')
  }, [current, decide])

  if (!current) return null

  return (
    <Dialog open={true} onClose={handleReject}>
      <div className="approval-dialog">
        <h2>Approval Required</h2>

        <div className="approval-dialog__field">
          <label>Tool</label>
          <p>{current.toolCallId ?? 'N/A'}</p>
        </div>

        <div className="approval-dialog__field">
          <label>Reason</label>
          <p>{current.reason}</p>
        </div>

        {current.diffPreview && (
          <div className="approval-dialog__field">
            <label>Preview</label>
            <DiffPreview data={current.diffPreview} />
          </div>
        )}

        <div className="approval-dialog__ttl">
          Time remaining: {remaining.toString()}s
        </div>

        <div className="approval-dialog__actions">
          <Button variant="primary" onClick={handleApprove}>
            Approve
          </Button>
          <Button variant="danger" onClick={handleReject}>
            Reject
          </Button>
        </div>
      </div>
    </Dialog>
  )
}
