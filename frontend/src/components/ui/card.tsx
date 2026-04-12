import { cn } from '@/lib/utils/cn'

import type { HTMLAttributes } from 'react'

type CardProps = HTMLAttributes<HTMLDivElement>

export function Card({ className, ...props }: CardProps) {
  return <div className={cn('orca-card', className)} {...props} />
}

export function CardHeader({ className, ...props }: CardProps) {
  return <div className={cn('orca-card__header', className)} {...props} />
}

export function CardContent({ className, ...props }: CardProps) {
  return <div className={cn('orca-card__content', className)} {...props} />
}
