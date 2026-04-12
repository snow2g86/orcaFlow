// conventions.md §1.3 — snake_case <-> camelCase 변환 유틸.
// lib/api 에서만 사용. 컴포넌트/스토어는 camelCase 만 본다.

function snakeToCamel(s: string): string {
  return s.replace(/_([a-z0-9])/g, (_, c: string) => c.toUpperCase())
}

function camelToSnake(s: string): string {
  return s.replace(/[A-Z]/g, (c) => `_${c.toLowerCase()}`)
}

export function keysToCamel<T>(obj: unknown): T {
  if (Array.isArray(obj)) {
    return obj.map((v: unknown) => keysToCamel<unknown>(v)) as T
  }
  if (obj !== null && typeof obj === 'object') {
    const result: Record<string, unknown> = {}
    for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
      result[snakeToCamel(key)] = keysToCamel<unknown>(value)
    }
    return result as T
  }
  return obj as T
}

export function keysToSnake<T>(obj: unknown): T {
  if (Array.isArray(obj)) {
    return obj.map((v: unknown) => keysToSnake<unknown>(v)) as T
  }
  if (obj !== null && typeof obj === 'object') {
    const result: Record<string, unknown> = {}
    for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
      result[camelToSnake(key)] = keysToSnake<unknown>(value)
    }
    return result as T
  }
  return obj as T
}
