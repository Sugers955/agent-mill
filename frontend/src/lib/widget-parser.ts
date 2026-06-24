/**
 * widget-parser — extract show-widget code fences from streaming markdown.
 *
 * Adapted from agent-ide/src/utils/widget-parser.js (TypeScript port, trimmed).
 *
 * Two states:
 *   - fence still open (streaming): returns partial widget
 *   - fence closed (complete): returns parsed widgets + surrounding text
 */

const FENCE_OPEN = '```show-widget'
const FENCE_CLOSE = '```'

export interface WidgetData {
  title: string
  widget_code: string
}

export type WidgetSegment =
  | { type: 'text'; content: string }
  | { type: 'widget'; data: WidgetData }

export interface PartialWidgetResult {
  beforeText: string
  partialCode: string | null
  partialTitle: string | null
  hasCompletedFences: boolean
  completedSegments: WidgetSegment[]
  afterText?: string | null
  isRawVisualization?: boolean
  isComplete?: boolean
}

function unescapeJsonString(raw: string): string {
  if (!raw) return ''
  let value = raw
  if (value.endsWith('\\')) value = value.slice(0, -1)
  return value
    .replace(/\\\\/g, '\x00BS\x00')
    .replace(/\\n/g, '\n')
    .replace(/\\t/g, '\t')
    .replace(/\\r/g, '\r')
    .replace(/\\"/g, '"')
    .replace(/\\'/g, "'")
    .replace(/\\u([0-9a-fA-F]{4})/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)))
    .replace(/\x00BS\x00/g, '\\')
}

function findJsonStringEnd(source: string, valueStartIdx: number): number {
  let esc = false
  for (let i = valueStartIdx; i < source.length; i++) {
    const ch = source[i]
    if (esc) { esc = false; continue }
    if (ch === '\\') { esc = true; continue }
    if (ch === '"') return i
  }
  return -1
}

function extractJsonStringValue(source: string, key: string) {
  const keyIdx = source.indexOf(`"${key}"`)
  if (keyIdx === -1) return null
  const colonIdx = source.indexOf(':', keyIdx + key.length + 2)
  if (colonIdx === -1) return null
  const quoteIdx = source.indexOf('"', colonIdx + 1)
  if (quoteIdx === -1) return null
  const valueStart = quoteIdx + 1
  const valueEnd = findJsonStringEnd(source, valueStart)
  const raw = source.slice(valueStart, valueEnd === -1 ? source.length : valueEnd)
  return {
    value: unescapeJsonString(raw),
    isClosed: valueEnd !== -1,
    endIdx: valueEnd,
  }
}

function decodeWidgetCode(code: string): string {
  if (!code || !code.includes('\\')) return code
  return code
    .replace(/\\\\/g, '\x00BS\x00')
    .replace(/\\n/g, '\n')
    .replace(/\\t/g, '\t')
    .replace(/\\r/g, '\r')
    .replace(/\\"/g, '"')
    .replace(/\\'/g, "'")
    .replace(/\\u([0-9a-fA-F]{4})/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)))
    .replace(/\x00BS\x00/g, '\\')
}

function parseWidgetFenceBody(rawBody: string): WidgetData | null {
  const jsonStr = rawBody.trim().replace(/^```(?:json)?\s*/i, '').replace(/```$/i, '').trim()
  if (!jsonStr) return null
  try {
    const parsed = JSON.parse(jsonStr)
    if (parsed.title && parsed.widget_code) {
      return { title: parsed.title, widget_code: decodeWidgetCode(parsed.widget_code) }
    }
  } catch {
    // fall through
  }
  const widgetCode = extractJsonStringValue(jsonStr, 'widget_code')
  if (widgetCode?.value) {
    const title = extractJsonStringValue(jsonStr, 'title')?.value || 'Widget'
    return { title, widget_code: widgetCode.value }
  }
  return null
}

/** Parse a complete content string with closed fences. */
export function parseAllShowWidgets(content: string): WidgetSegment[] {
  const segments: WidgetSegment[] = []
  let remaining = content

  if (!content.includes(FENCE_OPEN)) {
    if (content.trim()) segments.push({ type: 'text', content })
    return segments
  }

  while (remaining.length > 0) {
    const fenceStart = remaining.indexOf(FENCE_OPEN)
    if (fenceStart === -1) {
      if (remaining.trim()) segments.push({ type: 'text', content: remaining })
      break
    }
    if (fenceStart > 0) {
      const before = remaining.slice(0, fenceStart)
      if (before.trim()) segments.push({ type: 'text', content: before })
    }
    const afterFence = remaining.slice(fenceStart + FENCE_OPEN.length)
    const contentStart = afterFence.startsWith('\n') ? 1 : 0
    const fenceBody = afterFence.slice(contentStart)
    const closeIdx = fenceBody.indexOf('\n' + FENCE_CLOSE)
    if (closeIdx === -1) {
      // fence not closed — bail; caller should use extractPartialWidget
      remaining = ''
      continue
    }
    const jsonStr = fenceBody.slice(0, closeIdx)
    const consumed = fenceStart + FENCE_OPEN.length + contentStart + closeIdx + 1 + FENCE_CLOSE.length
    const widget = parseWidgetFenceBody(jsonStr)
    if (widget?.widget_code) segments.push({ type: 'widget', data: widget })
    remaining = remaining.slice(consumed)
  }
  return segments
}

/**
 * Extract partial widget (mid-streaming) or completed segments.
 * Single function the renderer calls on every text update.
 */
/**
 * Defensive: detect raw <svg>…</svg> (or partial) anywhere in the content,
 * even outside a fence — so widgets render even if the model ignores the
 * `show-widget` instruction.
 */
function detectRawSvg(content: string): { before: string; svg: string; after: string; complete: boolean } | null {
  const trimmed = content
  // Strip a code-fence wrapper if the AI put SVG inside ``` … ```
  const fencedMatch = trimmed.match(/```(?:svg|html|xml)?\s*\n([\s\S]*?<svg[\s\S]*?<\/svg>[\s\S]*?)\n```/i)
  if (fencedMatch) {
    const fenceStart = trimmed.indexOf(fencedMatch[0])
    const before = trimmed.slice(0, fenceStart).trim()
    const after = trimmed.slice(fenceStart + fencedMatch[0].length).trim()
    const svgMatch = fencedMatch[1].match(/<svg[\s\S]*?<\/svg>/)
    if (svgMatch) return { before, svg: svgMatch[0], after, complete: true }
  }
  const svgIdx = trimmed.indexOf('<svg')
  if (svgIdx === -1) return null
  const closeIdx = trimmed.indexOf('</svg>', svgIdx)
  if (closeIdx === -1) {
    // Partial SVG, still streaming
    return {
      before: trimmed.slice(0, svgIdx).replace(/```(?:svg|html|xml)?\s*$/i, '').trim(),
      svg: trimmed.slice(svgIdx),
      after: '',
      complete: false,
    }
  }
  const svgEnd = closeIdx + '</svg>'.length
  return {
    before: trimmed.slice(0, svgIdx).replace(/```(?:svg|html|xml)?\s*$/i, '').trim(),
    svg: trimmed.slice(svgIdx, svgEnd),
    after: trimmed.slice(svgEnd).replace(/^\s*```/, '').trim(),
    complete: true,
  }
}

export function extractPartialWidget(content: string): PartialWidgetResult {
  const lastFenceMatch = [...content.matchAll(/```show-widget/g)].pop()

  if (!lastFenceMatch) {
    // No show-widget fence — try the raw-SVG fallback.
    const raw = detectRawSvg(content)
    if (raw) {
      return {
        beforeText: raw.before,
        partialCode: raw.svg,
        partialTitle: 'Visualization',
        hasCompletedFences: false,
        completedSegments: [],
        afterText: raw.after || null,
        isRawVisualization: true,
        isComplete: raw.complete,
      }
    }
    return { beforeText: '', partialCode: null, partialTitle: null, hasCompletedFences: false, completedSegments: [] }
  }

  const lastFenceStart = lastFenceMatch.index!
  const afterLastFence = content.slice(lastFenceStart)
  const lastFenceClosed = afterLastFence.indexOf('\n' + FENCE_CLOSE, FENCE_OPEN.length) !== -1

  if (lastFenceClosed) {
    const completedSegments = parseAllShowWidgets(content)
    let afterText: string | null = null
    if (completedSegments.length > 0) {
      const lastSeg = completedSegments[completedSegments.length - 1]
      if (lastSeg.type === 'widget') {
        const lastClose = content.lastIndexOf('```')
        if (lastClose !== -1 && lastClose < content.length - 3) {
          const trailing = content.slice(lastClose + 3).trim()
          if (trailing) afterText = trailing
        }
      }
    }
    return {
      beforeText: '',
      partialCode: null,
      partialTitle: null,
      hasCompletedFences: true,
      completedSegments,
      afterText,
      isComplete: true,
    }
  }

  // Partial: extract text before the open fence + the partial code
  const beforePart = content.slice(0, lastFenceStart)
  const hasCompletedFences = /```show-widget/.test(beforePart)
  const completedSegments = hasCompletedFences ? parseAllShowWidgets(beforePart) : []

  const markerEnd = afterLastFence.match(/^```\s*show-widget\s*\n?/)
  const fenceBodyRaw = markerEnd ? afterLastFence.slice(markerEnd[0].length) : afterLastFence

  let partialCode: string | null = null
  let jsonEndIdx = -1
  const widgetValue = extractJsonStringValue(fenceBodyRaw, 'widget_code')
  if (widgetValue?.value) {
    partialCode = widgetValue.value
    if (widgetValue.isClosed) jsonEndIdx = widgetValue.endIdx + 1
  }

  // truncate unclosed <script>
  if (partialCode) {
    const lastScript = partialCode.lastIndexOf('<script')
    if (lastScript !== -1) {
      const after = partialCode.slice(lastScript)
      if (!/<script[\s\S]*?<\/script>/i.test(after)) {
        partialCode = partialCode.slice(0, lastScript).trim() || null
      }
    }
  }

  let afterText: string | null = null
  if (jsonEndIdx !== -1 && jsonEndIdx < fenceBodyRaw.length) {
    const t = fenceBodyRaw.slice(jsonEndIdx).trim()
    if (t) afterText = t
  }

  const partialTitle = extractJsonStringValue(fenceBodyRaw, 'title')?.value || null

  return {
    beforeText: beforePart,
    partialCode,
    partialTitle,
    hasCompletedFences,
    completedSegments,
    afterText,
    isComplete: false,
  }
}

/** Stable key for a partial widget so Vue can reuse the iframe across deltas. */
export function computePartialWidgetKey(content: string): string {
  const matches = [...content.matchAll(/```show-widget/g)]
  return `partial-w-${matches.length - 1}`
}

export function createWidgetStableKey(code = '', title = 'widget'): string {
  let hash = 0
  const input = `${title}:${code}`
  for (let i = 0; i < input.length; i++) {
    hash = ((hash << 5) - hash + input.charCodeAt(i)) | 0
  }
  return `${title}-${Math.abs(hash)}`
}

// ── Rendered segments for the chat bubble ──────────────────────────────────

export interface RenderedTextSegment {
  type: 'text'
  content: string
}
export interface RenderedWidgetSegment {
  type: 'widget'
  widgetCode: string
  title: string
  isStreaming: boolean
  stableKey: string
  partialKey?: string
}
export type RenderedSegment = RenderedTextSegment | RenderedWidgetSegment

/** Convert raw streaming text into renderable segments for Chat.vue. */
export function parseMessageContent(content: string, isStreaming = false): RenderedSegment[] {
  if (!content) return []
  const result = extractPartialWidget(content)
  const segments: RenderedSegment[] = []
  const seen = new Set<string>()

  // Raw <svg> fallback path
  if (result.isRawVisualization && result.partialCode) {
    if (result.beforeText) {
      const t = result.beforeText.trim()
      if (t) segments.push({ type: 'text', content: result.beforeText })
    }
    segments.push({
      type: 'widget',
      widgetCode: result.partialCode,
      title: result.partialTitle || 'Visualization',
      isStreaming: isStreaming && !result.isComplete,
      stableKey: createWidgetStableKey(result.partialCode, result.partialTitle || 'Visualization'),
    })
    if (result.afterText) {
      const t = result.afterText.trim()
      if (t) segments.push({ type: 'text', content: result.afterText })
    }
    return segments
  }

  if (!result.hasCompletedFences && !result.partialCode) {
    return [{ type: 'text', content }]
  }

  for (const seg of result.completedSegments) {
    if (seg.type === 'text') {
      const t = seg.content.trim()
      if (t && !seen.has(t)) { segments.push({ type: 'text', content: seg.content }); seen.add(t) }
    } else {
      const isLast = seg === result.completedSegments[result.completedSegments.length - 1]
      segments.push({
        type: 'widget',
        widgetCode: seg.data.widget_code,
        title: seg.data.title || 'Widget',
        isStreaming: isStreaming && isLast && !result.partialCode,
        stableKey: createWidgetStableKey(seg.data.widget_code, seg.data.title),
      })
    }
  }

  if (result.partialCode && result.partialCode.length > 10) {
    segments.push({
      type: 'widget',
      widgetCode: result.partialCode,
      title: result.partialTitle || 'Widget',
      isStreaming: isStreaming && !result.isComplete,
      stableKey: createWidgetStableKey(result.partialCode, result.partialTitle || 'Widget'),
      partialKey: computePartialWidgetKey(content),
    })
  }

  if (result.afterText) {
    const t = result.afterText.trim()
    if (t && !seen.has(t)) segments.push({ type: 'text', content: result.afterText })
  }

  return segments
}
