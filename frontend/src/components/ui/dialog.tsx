import { useEffect, useRef } from 'react'

import { cn } from '@/lib/utils/cn'

import type { HTMLAttributes, ReactNode } from 'react'

type DialogProps = HTMLAttributes<HTMLDivElement> & {
  open: boolean
  onClose: () => void
  children: ReactNode
}

export function Dialog({ open, onClose, className, children, ...props }: DialogProps) {
  const overlayRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    if (open) {
      document.addEventListener('keydown', handleKey)
    }
    return () => {
      document.removeEventListener('keydown', handleKey)
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      ref={overlayRef}
      className="orca-dialog-overlay"
      onClick={(e) => {
        if (e.target === overlayRef.current) onClose()
      }}
    >
      <div className={cn('orca-dialog', className)} {...props}>
        {children}
      </div>
    </div>
  )
}
