// conventions.md §6.4 — Tauri IPC 는 오직 src/lib/api 안에서만 호출한다.
// 컴포넌트·스토어는 본 모듈이 export 하는 함수만 사용해야 한다.

import { invoke } from '@tauri-apps/api/core'

import type { AppConfig, AppStatus, SidecarEndpoint } from '@/types/app.types'

type RawAppStatus = {
  sidecar:
    | { state: 'starting' }
    | { state: 'ready'; port: number; version: string; token: string }
    | { state: 'failed'; reason: string }
  endpoint: { port: number; token: string; version: string } | null
  workspace: string
  version: string
}

type RawConfig = {
  app: { log_level: string; telemetry: boolean }
  sidecar: { host: string; port: number }
  db: { path: string }
  workspace: string
}

export async function fetchAppStatus(): Promise<AppStatus> {
  const raw = await invoke<RawAppStatus>('app_ready')
  const ep: SidecarEndpoint | null = raw.endpoint
    ? { port: raw.endpoint.port, token: raw.endpoint.token, version: raw.endpoint.version }
    : null
  return {
    sidecar: raw.sidecar,
    endpoint: ep,
    workspace: raw.workspace,
    version: raw.version,
  }
}

export async function fetchConfig(): Promise<AppConfig> {
  const raw = await invoke<RawConfig>('config_get')
  return {
    app: { logLevel: raw.app.log_level, telemetry: raw.app.telemetry },
    sidecar: raw.sidecar,
    db: raw.db,
    workspace: raw.workspace,
  }
}
