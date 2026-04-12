import { cn } from '@/lib/utils/cn'

import type { HTMLAttributes } from 'react'

type ScrollAreaProps = HTMLAttributes<HTMLDivElement>

export function ScrollArea({ className, ...props }: ScrollAreaProps) {
  return <div className={cn('orca-scroll-area', className)} {...props} />
}
