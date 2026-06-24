/** 渐变色数组 — 统一管理，避免 6 处重复 */
export const GRADIENTS = [
  'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
  'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
  'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
  'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
  'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
  'linear-gradient(135deg, #a18cd1 0%, #fbc2eb 100%)',
  'linear-gradient(135deg, #fccb90 0%, #d57eeb 100%)',
  'linear-gradient(135deg, #e0c3fc 0%, #8ec5fc 100%)',
]

/** 根据 ID/Code 确定性获取渐变色 */
export function agentGradient(id: number | string): string {
  const idx = typeof id === 'number' ? id : hashString(id)
  return GRADIENTS[Math.abs(idx) % GRADIENTS.length]
}

function hashString(s: string): number {
  let h = 0
  for (let i = 0; i < s.length; i++) {
    h = ((h << 5) - h + s.charCodeAt(i)) | 0
  }
  return h
}

/** 状态色映射 — 统一管理 */
export const STATUS_COLORS = {
  success: { bg: 'var(--m-success-soft, #dcfce7)', text: 'var(--m-success, #16a34a)' },
  warning: { bg: 'var(--m-warning-soft, #fef3c7)', text: 'var(--m-warning, #d97706)' },
  danger:  { bg: 'var(--m-danger-soft, #fee2e2)',  text: 'var(--m-danger, #dc2626)' },
  info:    { bg: 'var(--m-info-soft, #eff6ff)',    text: 'var(--m-info, #2563eb)' },
  default: { bg: 'var(--m-surface-variant, #f1f5f9)', text: 'var(--m-text-secondary, #64748b)' },
} as const

/** 可预览的文件扩展名 */
export const PREVIEWABLE = new Set([
  'html', 'htm', 'svg', 'md', 'txt', 'json', 'csv', 'xml', 'yaml', 'yml',
  'js', 'ts', 'py', 'java', 'go', 'rs', 'css', 'scss', 'sql', 'sh',
  'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf',
])

/** 从 Markdown 中提取纯文本（截断到指定长度） */
export function plainTextFromMarkdown(md: string, maxLen = 200): string {
  return md
    .replace(/```[\s\S]*?```/g, '[代码]')
    .replace(/`[^`]+`/g, '')
    .replace(/[#*_~\[\]()]/g, '')
    .replace(/\n+/g, ' ')
    .trim()
    .slice(0, maxLen)
}

/** 标准化单个工具调用 */
function _normalizeOne(tc: any) {
  return {
    name: tc.name || tc.tool_name || 'unknown',
    input: tc.input || tc.arguments || {},
    status: tc.status || (tc.error ? 'error' : 'success'),
    output: tc.output || tc.result || tc.error || undefined,
    duration_ms: tc.duration_ms,
    kind: tc.kind,
    label: tc.label,
    serverName: tc.serverName,
  }
}

/** 标准化工具调用 trace（统一桌面端/移动端/ChatTab） */
export function normalizeTrace(trace: any[] | undefined): any[] {
  if (!Array.isArray(trace) || !trace.length) return []
  return trace.map(_normalizeOne)
}
