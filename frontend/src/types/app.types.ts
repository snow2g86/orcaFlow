// design.md §4.1 app_ready 커맨드 응답 타입
// 경계 케이싱 규칙 (conventions.md §1.3) 에 따라 frontend 내부는 camelCase 를 쓴다.
// Tauri 페이로드는 snake_case 이므로 lib/api 어댑터에서 1회 변환한다.

export type SidecarState = 'starting' | 'ready' | 'failed'

export type SidecarStatus =
  | { state: 'starting' }
  | { state: 'ready'; port: number; version: string; token: string }
  | { state: 'failed'; reason: string }

export type SidecarEndpoint = {
  port: number
  token: string
  version: string
}

export type AppStatus = {
  sidecar: SidecarStatus
  endpoint: SidecarEndpoint | null
  workspace: string
  version: string
}

export type AppConfig = {
  app: { logLevel: string; telemetry: boolean }
  sidecar: { host: string; port: number }
  db: { path: string }
  workspace: string
}
