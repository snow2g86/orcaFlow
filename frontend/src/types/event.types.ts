// SSE RunEvent 타입 (camelCase 내부 표현)

export type RunEvent = {
  id: number
  event: string
  payload: Record<string, unknown>
  at: string
}
