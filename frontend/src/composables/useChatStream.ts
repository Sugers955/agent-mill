/**
 * Shared chat streaming logic — eliminates duplication between Chat.vue and ChatTab.vue.
 *
 * Usage:
 *   const { send, applyEvent, isWaiting, sending, streamAbortController } = useChatStream({
 *     chatStore,
 *     scrollBottom,
 *     input,
 *     onMeta,          // optional: called when meta event arrives
 *     onThinkingScroll, // optional: called to scroll thinking block
 *   })
 */
import { ref, type Ref } from 'vue'
import { useChat } from '@/stores/chat'
import { resolveToolMeta } from '@/lib/toolDisplay'

export interface UseChatStreamOptions {
  chatStore: ReturnType<typeof useChat>
  scrollBottom: () => Promise<void>
  input: Ref<string>
  /** Called when meta event arrives (Chat.vue uses this, ChatTab doesn't) */
  onMeta?: (data: any) => void
  /** Called to scroll thinking block (Chat.vue uses this, ChatTab doesn't) */
  onThinkingScroll?: (m: any) => void
  /** Called after send completes to auto-rename conversation (ChatTab uses this) */
  onAfterSend?: (text: string) => void
}

export function useChatStream(options: UseChatStreamOptions) {
  const { chatStore, scrollBottom, input, onMeta, onThinkingScroll, onAfterSend } = options
  const sending = ref(false)
  const streamAbortController: Ref<AbortController | null> = ref(null)

  function applyEvent(m: any, ev: { type: string; data: any }) {
    const { type, data } = ev
    if (type === 'meta') {
      m._meta = data
      onMeta?.(data)
    } else if (type === 'text') {
      m.content_json.text += data.text || ''
    } else if (type === 'thinking') {
      m._thinking += data.text || ''
      onThinkingScroll?.(m)
    } else if (type === 'tool_use') {
      const id = data.id || data.name
      const existingIdx = m._stepIndex[id]
      if (existingIdx != null) {
        const s = m._steps[existingIdx]
        if (data.input && (typeof data.input !== 'object' || Object.keys(data.input).length)) {
          s.input = data.input
        }
        return
      }
      const idx = m._steps.length
      m._stepIndex[id] = idx
      const meta = resolveToolMeta(data.name || '')
      m._steps.push({
        kind: meta.kind,
        name: data.name || '(tool)',
        label: meta.label,
        serverName: meta.serverName,
        input: data.input,
        status: 'running',
        _start: performance.now(),
      })
    } else if (type === 'tool_result') {
      const id = data.tool_use_id
      let idx = id != null ? m._stepIndex[id] : undefined
      if (idx == null) idx = m._steps.length - 1
      const s = m._steps[idx]
      if (s) {
        s.output = data.content
        s.status = 'done'
        if (s._start) s.duration_ms = Math.round(performance.now() - s._start)
      }
    } else if (type === 'file') {
      const next = Array.isArray(m._files) ? [...m._files, data] : [data]
      m._files = next
    } else if (type === 'ui') {
      const next = Array.isArray(m._uis) ? [...m._uis, data] : [data]
      m._uis = next
    } else if (type === 'error') {
      m.content_json.text += `\n\n[错误] ${data.message}`
    }
  }

  function isWaiting(m: any): boolean {
    if (m.role !== 'assistant' || !m._streaming) return false
    if (m.content_json?.text) return false
    if (m._thinking) return false
    if (m._steps?.length) return false
    if (m._files?.length) return false
    if (m._uis?.length) return false
    return true
  }

  function createPlaceholder(): any {
    return {
      _tmp: Date.now(),
      role: 'assistant',
      content_json: { text: '' },
      tool_calls_json: null,
      _meta: null,
      _thinking: '',
      _steps: [],
      _stepIndex: {} as Record<string, number>,
      _files: [],
      _uis: [],
      _streaming: true,
    }
  }

  /** Core SSE streaming logic — called by send() or directly for custom flows */
  async function streamMessage(opts: {
    convId: number
    text: string
    fileIds?: number[]
    placeholder: any
  }) {
    const { convId, text, fileIds = [], placeholder } = opts
    const token = localStorage.getItem('access_token')
    const controller = new AbortController()
    streamAbortController.value = controller
    try {
      const resp = await fetch(`/api/conversations/${convId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ content: text, file_ids: fileIds }),
        signal: controller.signal,
      })
      if (!resp.ok || !resp.body) throw new Error(`HTTP ${resp.status}`)
      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n\n')
        buf = lines.pop() || ''
        for (const line of lines) {
          if (!line.startsWith('data:')) continue
          try {
            const json = JSON.parse(line.slice(5).trim())
            applyEvent(placeholder, json)
          } catch {}
          await scrollBottom()
        }
      }
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        if (e?.response?.status === 429) {
          placeholder.content_json.text += '\n\n⚠️ 本月额度已用完，请联系管理员提升额度。'
        } else {
          placeholder.content_json.text += `\n\n[网络错误] ${e.message}`
        }
      }
    } finally {
      streamAbortController.value = null
      placeholder._steps?.forEach((s: any) => {
        if (s.status === 'running') s.status = 'done'
      })
      placeholder._streaming = false
      sending.value = false
    }
  }

  async function send(textOverride?: string) {
    const chat = chatStore
    const text = textOverride ?? input.value.trim()
    if (!chat.currentAgent || !text) return
    if (!chat.currentConvId) await chat.ensureConv()

    // Push user message
    chat.messages.push({ _tmp: Date.now(), role: 'user', content_json: { text } })

    // Push assistant placeholder
    const placeholder = createPlaceholder()
    chat.messages.push(placeholder)
    if (!textOverride) input.value = ''

    sending.value = true
    await scrollBottom()

    if (!chat.currentConvId) return
    await streamMessage({ convId: chat.currentConvId, text, fileIds: [], placeholder })

    // Auto-rename conversation on first exchange
    if (chat.messages.length <= 2 && chat.currentConvId) {
      onAfterSend?.(text)
    }
  }

  return {
    sending,
    streamAbortController,
    send,
    streamMessage,
    applyEvent,
    isWaiting,
    createPlaceholder,
  }
}
