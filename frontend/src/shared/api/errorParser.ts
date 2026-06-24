/**
 * API 错误消息解析 — 桌面端和移动端共享
 */
export function parseApiError(data: any, fallback: string): string {
  if (typeof data?.detail === 'string') return data.detail
  if (Array.isArray(data?.detail)) {
    return data.detail
      .map((d: any) => `${(d.loc || []).slice(-1)[0] || ''}: ${d.msg}`)
      .filter(Boolean)
      .join('; ') || fallback
  }
  if (data?.message) return data.message
  return fallback
}
