import { cn } from '@/lib/utils/cn'

import type { HTMLAttributes } from 'react'

type SpinnerProps = HTMLAttributes<HTMLDivElement> & {
  size?: 'sm' | 'md' | 'lg'
}

export function Spinner({ size = 'md', className, ...props }: SpinnerProps) {
  return <div className={cn('orca-spinner', `orca-spinner--${size}`, className)} {...props} />
}
