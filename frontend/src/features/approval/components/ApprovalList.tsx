import { Badge } from '@/components/ui/badge'
import { useApprovalStore } from '@/stores/approval-store'

export function ApprovalList() {
  const count = useApprovalStore((s) => s.pending.length)

  if (count === 0) return null

  return (
    <Badge variant="warning" className="approval-badge">
      {count.toString()} pending
    </Badge>
  )
}
