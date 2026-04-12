import { cn } from '@/lib/utils/cn'

import type { HTMLAttributes } from 'react'

type BadgeProps = HTMLAttributes<HTMLSpanElement> & {
  variant?: 'default' | 'success' | 'warning' | 'error' | 'info'
}

export function Badge({ variant = 'default', className, ...props }: BadgeProps) {
  return <span className={cn('orca-badge', `orca-badge--${variant}`, className)} {...props} />
}
