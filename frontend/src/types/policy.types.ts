// schema.md §3.8 — Policy 타입 (최소, M5 에서는 ID 참조만)

export type PolicyMode = 'strict' | 'ask' | 'trusted'

export type PolicySummary = {
  id: string
  name: string
  mode: PolicyMode
}
