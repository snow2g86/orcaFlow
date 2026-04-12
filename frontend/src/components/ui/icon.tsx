// 간단한 SVG 아이콘 컴포넌트. M5 에서는 텍스트 기반 placeholder 로 시작.

import type { HTMLAttributes } from 'react'

type IconProps = HTMLAttributes<HTMLSpanElement> & {
  name: 'send' | 'cancel' | 'check' | 'x' | 'refresh' | 'chat' | 'monitor' | 'alert'
}

const ICONS: Record<IconProps['name'], string> = {
  send: '\u27A4',
  cancel: '\u2716',
  check: '\u2714',
  x: '\u2716',
  refresh: '\u21BB',
  chat: '\uD83D\uDCAC',
  monitor: '\uD83D\uDCCA',
  alert: '\u26A0',
}

export function Icon({ name, ...props }: IconProps) {
  return (
    <span role="img" aria-label={name} {...props}>
      {ICONS[name]}
    </span>
  )
}
