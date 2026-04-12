// schema.md §3.1 — Workflow 타입 (camelCase 내부 표현, 최소)

export type WorkflowSummary = {
  id: string
  name: string
  version: number
  entrypoint: string
}
