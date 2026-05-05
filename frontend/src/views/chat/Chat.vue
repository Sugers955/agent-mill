<template>
  <div class="chat-wrap" :class="{ 'split-mode': previewFile }">
    <!-- Conversation -->
    <section class="conv">
      <div ref="scrollRef" class="messages">
        <div v-if="!chat.currentConvId" class="welcome">
          <div class="welcome-mark">
            <span class="dot dot-1" /><span class="dot dot-2" />
            <span class="dot dot-3" /><span class="dot dot-4" />
          </div>
          <h2 v-if="chat.currentAgent">你好,我是 {{ chat.currentAgent.name }}</h2>
          <h2 v-else>欢迎</h2>
          <p v-if="chat.currentAgent">{{ chat.currentAgent.description || '在下方输入开始对话' }}</p>
          <p v-else>暂无可用智能体,请联系管理员授权</p>
        </div>

        <template v-else>
          <div v-for="m in chat.messages" :key="m.id || m._tmp" :class="['msg', m.role]">
            <div v-if="m.role === 'assistant'" class="avatar bot">
              <span class="dot dot-1" /><span class="dot dot-2" />
              <span class="dot dot-3" /><span class="dot dot-4" />
            </div>
            <div class="bubble-stack">
              <!-- meta: 当前回答用的 agent / model -->
              <div v-if="m.role === 'assistant' && m._meta" class="msg-meta">
                <span>{{ m._meta.agent_name }}</span>
                <span class="dot-sep">·</span>
                <code>{{ m._meta.model_id }}</code>
                <span class="muted">({{ m._meta.provider }})</span>
              </div>

              <!-- thinking block -->
              <details v-if="m.content_json?.thinking || m._thinking" class="thinking-card" :open="m._thinkingOpen ?? !m.content_json?.text">
                <summary>
                  <el-icon><Cpu /></el-icon>
                  <span>思考过程</span>
                  <span class="muted" style="font-size:11px;margin-left:6px">{{ (m.content_json?.thinking || m._thinking || '').length }} 字</span>
                </summary>
                <div class="thinking-content">{{ m.content_json?.thinking || m._thinking }}</div>
              </details>

              <!-- tool / mcp / skill steps -->
              <div v-if="m._steps?.length || m.tool_calls_json?.trace?.length" class="step-list">
                <div v-for="(s, i) in (m._steps || normalizeTrace(m.tool_calls_json?.trace))" :key="i" :class="['step-card', s.status]">
                  <div class="step-head">
                    <el-icon v-if="s.status === 'running'" class="is-loading"><Loading /></el-icon>
                    <el-icon v-else-if="s.status === 'done'" style="color:var(--m-success)"><CircleCheckFilled /></el-icon>
                    <el-icon v-else><Tools /></el-icon>
                    <span class="step-kind">{{ s.kind }}</span>
                    <code class="step-name">{{ s.name }}</code>
                    <span v-if="s.duration_ms" class="muted" style="font-size:11px">{{ s.duration_ms }}ms</span>
                  </div>
                  <details v-if="s.input || s.output" class="step-detail">
                    <summary class="muted">查看 输入/输出</summary>
                    <div v-if="s.input" class="step-block"><div class="step-label">Input</div><pre>{{ formatStepData(s.input) }}</pre></div>
                    <div v-if="s.output" class="step-block"><div class="step-label">Output</div><pre>{{ formatStepData(s.output) }}</pre></div>
                  </details>
                </div>
              </div>

              <!-- file cards (saved outputs) -->
              <div v-if="(m.content_json?.files?.length) || m._files?.length" class="files-block">
                <FileCard
                  v-for="(f, fi) in (m._files?.length ? m._files : m.content_json.files)"
                  :key="fi + (f.name || '')"
                  :file="f"
                  @preview="openPreview"
                />
              </div>

              <!-- main answer -->
              <div v-if="m.content_json?.text || m.role === 'user'" class="bubble">
                <template v-if="m.role === 'user'">
                  <div v-if="m.content_json?.files?.length" class="msg-files">
                    <span
                      v-for="(f, fi) in m.content_json.files"
                      :key="fi"
                      :class="['msg-file-chip', { clickable: canPreview(f) }]"
                      @click="canPreview(f) && openPreview(f)"
                    >
                      <el-icon :size="12"><Paperclip /></el-icon>
                      {{ f.name }}<span v-if="f.parsed_chars" class="msg-file-meta"> · {{ f.parsed_chars }}字</span>
                    </span>
                  </div>
                  <div class="bubble-content" v-html="md.render(m.content_json?.text || '')"></div>
                </template>
                <template v-else>
                  <template v-for="(seg, si) in parseSegments(m)" :key="seg.type === 'widget' ? (seg.partialKey || seg.stableKey) : `t-${si}`">
                    <div v-if="seg.type === 'text'" class="bubble-content" v-html="md.render(seg.content)"></div>
                    <WidgetRenderer
                      v-else
                      :widget-code="seg.widgetCode"
                      :title="seg.title"
                      :is-streaming="seg.isStreaming"
                      @send-message="onWidgetSendMessage"
                    />
                  </template>
                </template>
              </div>
            </div>
          </div>
        </template>
      </div>

      <!-- Composer -->
      <div class="composer-wrap">
        <div v-if="chat.pendingFiles.length" class="files-row">
          <div
            v-for="f in chat.pendingFiles"
            :key="f.id"
            :class="['file-chip', f.parse_status]"
            :title="f.parse_error || f.name"
          >
            <el-icon class="chip-leading" v-if="f.parse_status === 'parsing'" :size="14"><Loading class="spin" /></el-icon>
            <el-icon class="chip-leading ok" v-else-if="f.parse_status === 'done'" :size="14"><CircleCheckFilled /></el-icon>
            <el-icon class="chip-leading err" v-else-if="f.parse_status === 'failed'" :size="14"><CircleCloseFilled /></el-icon>
            <el-icon class="chip-leading" v-else :size="14"><Paperclip /></el-icon>
            <span class="chip-name">{{ f.name }}</span>
            <span v-if="f.parse_status === 'done'" class="chip-meta">{{ f.parsed_chars }} 字</span>
            <span v-else-if="f.parse_status === 'parsing'" class="chip-meta">解析中</span>
            <button v-else-if="f.parse_status === 'failed'" class="chip-action" @click="retryFile(f)" title="重试">重试</button>
            <button v-if="canPreview(f)" class="chip-action" @click="openPreview(f)" title="预览">
              <el-icon :size="12"><View /></el-icon>
            </button>
            <button class="chip-close" @click="removeFile(f)" title="移除">
              <el-icon :size="12"><Close /></el-icon>
            </button>
          </div>
        </div>
        <div class="composer">
          <el-upload :show-file-list="false" :auto-upload="false" :on-change="onPick" multiple>
            <button class="icon-btn" :disabled="!chat.currentAgent" :title="'上传文件'"><el-icon :size="18"><Paperclip /></el-icon></button>
          </el-upload>
          <el-input
            v-model="input"
            type="textarea"
            :rows="1"
            autosize
            resize="none"
            :placeholder="chat.currentAgent ? '发送消息...' : '请联系管理员授权可用的智能体'"
            :disabled="sending || !chat.currentAgent"
            @keydown.enter.exact.prevent="send"
          />
          <button class="send-btn" :disabled="sending || !input.trim() || !chat.currentAgent" @click="send">
            <el-icon v-if="!sending" :size="18"><Promotion /></el-icon>
            <el-icon v-else class="is-loading" :size="18"><Loading /></el-icon>
          </button>
        </div>
      </div>
    </section>
    <PreviewPanel v-if="previewFile" :file="previewFile" @close="closePreview" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/api'
import { useChat } from '@/stores/chat'
import MarkdownIt from 'markdown-it'
import WidgetRenderer from '@/components/WidgetRenderer.vue'
import FileCard from '@/components/FileCard.vue'
import PreviewPanel from '@/components/PreviewPanel.vue'
import { parseMessageContent } from '@/lib/widget-parser'

const md = new MarkdownIt({ breaks: true, linkify: true })
const chat = useChat()

const input = ref('')
const sending = ref(false)
const scrollRef = ref<HTMLElement | null>(null)
const previewFile = ref<any | null>(null)

function closePreview() { previewFile.value = null }

onMounted(async () => {
  if (!chat.loaded) await chat.loadInit()
  await scrollBottom()
})

watch(() => chat.currentConvId, async () => {
  await scrollBottom()
})

async function onPick(uploadFile: any) {
  // el-upload `on-change` fires once per selected file. The actual File is on .raw
  const file: File | undefined = uploadFile?.raw
  if (!file) return
  if (!chat.currentAgent) {
    ElMessage.warning('请先选择智能体')
    return
  }
  if (!chat.currentConvId) {
    await chat.newConv()
  }
  try {
    const r = await api.uploadFile(file, chat.currentConvId!)
    chat.pendingFiles.push(r)
    pollFileStatus(r.id)
  } catch (e: any) {
    // axios interceptor already shows ElMessage; nothing else needed
  }
}

function pollFileStatus(fileId: number) {
  const tick = async () => {
    const idx = chat.pendingFiles.findIndex((x: any) => x.id === fileId)
    if (idx === -1) return  // user removed it
    try {
      const fresh = await api.getFile(fileId)
      // splice in place to keep reactivity
      chat.pendingFiles[idx] = { ...chat.pendingFiles[idx], ...fresh }
      if (fresh.parse_status === 'parsing') {
        setTimeout(tick, 1500)
      }
    } catch {
      // file gone or transient — stop polling
    }
  }
  setTimeout(tick, 800)
}

async function retryFile(f: any) {
  try {
    const fresh = await api.reparseFile(f.id)
    const idx = chat.pendingFiles.findIndex((x: any) => x.id === f.id)
    if (idx >= 0) chat.pendingFiles[idx] = { ...chat.pendingFiles[idx], ...fresh }
    pollFileStatus(f.id)
  } catch {}
}

async function removeFile(f: any) {
  chat.pendingFiles = chat.pendingFiles.filter((x: any) => x.id !== f.id)
  // best-effort cleanup on the server
  try { await api.deleteFile(f.id) } catch {}
}

const PREVIEWABLE_EXT = new Set([
  'html', 'htm', 'pdf',
  'md', 'markdown',
  'txt', 'log', 'json', 'csv', 'xml',
  'js', 'ts', 'css', 'py', 'sql', 'yml', 'yaml', 'sh',
  'svg',
  'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp',
])

function canPreview(f: any): boolean {
  if (!f) return false
  const e = (f.ext || (f.name || '').split('.').pop() || '').toLowerCase().replace(/^\./, '')
  return PREVIEWABLE_EXT.has(e)
}

function openPreview(f: any) {
  // Composer-uploaded files come from /api/files; their raw bytes live at /api/files/{id}/raw.
  // Skill-output files have download_url set already. Build the right URL on the fly.
  const url = f.download_url || (f.id ? `/api/files/${f.id}/raw` : '')
  previewFile.value = { ...f, download_url: url }
}

function renderContent(m: any) {
  const text = m.content_json?.text || ''
  return md.render(text)
}

function parseSegments(m: any) {
  const text = m.content_json?.text || ''
  return parseMessageContent(text, !!m._streaming)
}

function onWidgetSendMessage(text: string) {
  if (!text || sending.value) return
  input.value = text
  send()
}

function normalizeTrace(trace: any[] | undefined) {
  if (!trace) return []
  return trace.map((t) => ({
    kind: t.type === 'tool_use' ? 'tool' : 'tool_result',
    name: t.data?.name || '',
    input: t.data?.input,
    output: t.data?.content,
    status: 'done',
  }))
}

function formatStepData(v: any) {
  if (typeof v === 'string') {
    try { return JSON.stringify(JSON.parse(v), null, 2) } catch { return v }
  }
  return JSON.stringify(v, null, 2)
}

async function scrollBottom() {
  await nextTick()
  const el = scrollRef.value
  if (el) el.scrollTop = el.scrollHeight
}

async function send() {
  if (!chat.currentAgent || !input.value.trim()) return
  // Per-send file count cap (Agent policy)
  const policy = chat.currentAgent?.upload_policy_json || {}
  const maxPerSend = Number(policy.max_files_per_send || 0)
  if (maxPerSend > 0 && chat.pendingFiles.length > maxPerSend) {
    ElMessage.warning(`单次发送最多 ${maxPerSend} 个文件,请删减后再发送`)
    return
  }
  // Block send while files are still parsing
  const stillParsing = chat.pendingFiles.filter((f: any) => f.parse_status === 'parsing')
  if (stillParsing.length) {
    ElMessage.warning(`还有 ${stillParsing.length} 个文件解析中,请稍候`)
    return
  }
  const isFirstMessage = chat.messages.length === 0
  if (!chat.currentConvId) {
    await chat.newConv()
  }
  const text = input.value.trim()
  const fileIds = chat.pendingFiles.map((f) => f.id)
  // Snapshot file briefs onto the user message for history rendering
  const fileBriefs = chat.pendingFiles.map((f: any) => ({
    id: f.id, name: f.name, size: f.size, parse_status: f.parse_status, parsed_chars: f.parsed_chars,
  }))
  chat.messages.push({ _tmp: Date.now(), role: 'user', content_json: { text, files: fileBriefs } })
  chat.messages.push({
    _tmp: Date.now() + 1, role: 'assistant',
    content_json: { text: '' }, tool_calls_json: null,
    _meta: null, _thinking: '', _steps: [], _stepIndex: {} as Record<string, number>, _files: [],
    _streaming: true,
  })
  // IMPORTANT: keep a reference to the *reactive proxy* (last array element),
  // not the plain object literal above. Mutating the proxy is what notifies Vue.
  const placeholder: any = chat.messages[chat.messages.length - 1]
  input.value = ''
  chat.pendingFiles = []
  sending.value = true
  await scrollBottom()

  const token = localStorage.getItem('access_token')
  try {
    const resp = await fetch(`/api/conversations/${chat.currentConvId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ content: text, file_ids: fileIds }),
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
        let json: any
        try { json = JSON.parse(line.slice(5).trim()) } catch { continue }
        applyEvent(placeholder, json)
        await scrollBottom()
      }
    }
  } catch (e: any) {
    placeholder.content_json.text += `\n\n[网络错误] ${e.message}`
  } finally {
    placeholder._steps?.forEach((s: any) => { if (s.status === 'running') s.status = 'done' })
    placeholder._streaming = false
    sending.value = false
  }

  if (isFirstMessage && chat.currentConvId) {
    const conv = chat.convs.find((c) => c.id === chat.currentConvId)
    if (conv) {
      const title = text.replace(/\s+/g, ' ').trim().slice(0, 30)
      if (title && title !== conv.title) {
        chat.renameConv(conv, title).catch(() => {})
      }
    }
  }
}

function applyEvent(m: any, ev: { type: string; data: any }) {
  const { type, data } = ev
  if (type === 'meta') {
    m._meta = data
  } else if (type === 'text') {
    m.content_json.text += data.text || ''
  } else if (type === 'thinking') {
    m._thinking += data.text || ''
  } else if (type === 'tool_use') {
    const id = data.id || data.name
    const existingIdx = m._stepIndex[id]
    if (existingIdx != null) {
      // update existing step (e.g. final input arrives at content_block_stop)
      const s = m._steps[existingIdx]
      if (data.input && (typeof data.input !== 'object' || Object.keys(data.input).length)) {
        s.input = data.input
      }
      return
    }
    const idx = m._steps.length
    m._stepIndex[id] = idx
    m._steps.push({
      kind: data.name?.startsWith('mcp_') ? 'mcp' : 'tool',
      name: data.name || '(tool)',
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
    // Reassign array (not just push) so Vue reactivity reliably triggers,
    // even if the original placeholder was constructed with an inline literal.
    const next = Array.isArray(m._files) ? [...m._files, data] : [data]
    m._files = next
  } else if (type === 'error') {
    m.content_json.text += `\n\n[错误] ${data.message}`
  }
}
</script>

<style scoped>
.chat-wrap { display: flex; height: 100%; background: var(--m-bg); }
.chat-wrap.split-mode .conv { flex: 1 1 50%; max-width: 50%; }
.chat-wrap.split-mode :deep(.preview-panel) { flex: 1 1 50%; max-width: 50%; }

.files-block { display: flex; flex-direction: column; gap: 4px; }

/* Conv main */
.conv { flex: 1; display: flex; flex-direction: column; min-width: 0; background: var(--m-surface); }
.messages { flex: 1; overflow: auto; padding: 24px 0; }

.welcome {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  height: 100%; color: var(--m-text-secondary); text-align: center;
}
.welcome h2 { margin: 16px 0 6px; font-weight: 600; letter-spacing: -0.01em; color: var(--m-text); }
.welcome p { margin: 0; font-size: 14px; }
.welcome-mark { display:grid; grid-template-columns: 1fr 1fr; gap: 6px; width: 48px; height: 48px; }
.welcome-mark .dot { border-radius: 50%; width: 100%; height: 100%; }
.welcome-mark .dot-1 { background:#4285f4 } .welcome-mark .dot-2 { background:#ea4335 }
.welcome-mark .dot-3 { background:#fbbc04 } .welcome-mark .dot-4 { background:#34a853 }

.msg { display: flex; gap: 12px; max-width: 850px; margin: 0 auto 16px; padding: 0 24px; }
.msg.user { flex-direction: row-reverse; }
.avatar.bot {
  width: 32px; height: 32px; flex-shrink: 0;
  background: var(--m-surface); border: 1px solid var(--m-border);
  border-radius: 50%; padding: 6px;
  display:grid; grid-template-columns: 1fr 1fr; gap: 2px; box-sizing: border-box;
}
.avatar.bot .dot { border-radius: 50%; }
.avatar.bot .dot-1 { background:#4285f4 } .avatar.bot .dot-2 { background:#ea4335 }
.avatar.bot .dot-3 { background:#fbbc04 } .avatar.bot .dot-4 { background:#34a853 }

.bubble {
  max-width: 100%; padding: 12px 16px;
  background: var(--m-bg-soft); border: 1px solid transparent;
  border-radius: var(--m-radius-lg);
  font-size: 14.5px; line-height: 1.65; word-break: break-word;
}
.msg.user .bubble {
  background: var(--m-primary); color: #fff; border-color: transparent;
  border-radius: var(--m-radius-lg) var(--m-radius-sm) var(--m-radius-lg) var(--m-radius-lg);
}
.msg.assistant .bubble { border-radius: var(--m-radius-sm) var(--m-radius-lg) var(--m-radius-lg) var(--m-radius-lg); }
.bubble :deep(p) { margin: 4px 0; }
.bubble :deep(p:first-child) { margin-top: 0; }
.bubble :deep(p:last-child) { margin-bottom: 0; }
.bubble :deep(pre) { background: #202124; color: #e8eaed; padding: 14px; border-radius: var(--m-radius); overflow: auto; font-size: 13px; margin: 8px 0; }
.bubble :deep(code) { font-family: 'Roboto Mono', monospace; }
.bubble :deep(:not(pre) > code) { background: var(--m-surface-variant); padding: 1px 6px; border-radius: 4px; font-size: 13px; }
.msg.user .bubble :deep(:not(pre) > code) { background: rgba(255,255,255,.18); }

.tool-trace-list { margin-top: 8px; }

/* Bubble stack: meta + thinking + steps + bubble vertically.
   `flex: 1` makes the stack always claim the available row space (capped by
   max-width), so widgets and tool cards render at a consistent width
   regardless of which child rendered first. */
.bubble-stack { display: flex; flex-direction: column; gap: 8px; flex: 1 1 0; max-width: 80%; min-width: 0; }
.msg.user .bubble-stack { align-items: flex-end; }

.msg-meta {
  display: flex; align-items: center; gap: 6px;
  font-size: 11px; color: var(--m-text-secondary);
  padding: 0 4px;
}
.msg-meta code { background: var(--m-surface-variant); padding: 1px 6px; border-radius: 4px; font-family: 'Roboto Mono', monospace; }
.dot-sep { color: var(--m-text-tertiary); }

/* thinking card */
.thinking-card {
  border: 1px dashed var(--m-border-strong);
  border-radius: var(--m-radius);
  background: var(--m-bg-soft);
  font-size: 13px;
}
.thinking-card summary {
  list-style: none; cursor: pointer;
  display: flex; align-items: center; gap: 6px;
  padding: 8px 12px; color: var(--m-text-secondary); font-weight: 500;
}
.thinking-card summary::-webkit-details-marker { display: none; }
.thinking-card[open] summary { border-bottom: 1px dashed var(--m-border); }
.thinking-content {
  padding: 10px 14px; white-space: pre-wrap; word-break: break-word;
  color: var(--m-text-secondary); line-height: 1.65; font-size: 13px;
  font-family: 'Inter', sans-serif;
}

/* step cards (tool / mcp / skill calls) */
.step-list { display: flex; flex-direction: column; gap: 6px; }
.step-card {
  border: 1px solid var(--m-border);
  border-radius: var(--m-radius);
  background: var(--m-surface);
  padding: 10px 12px;
  font-size: 13px;
  transition: background .2s, border-color .2s;
}
.step-card.running {
  background: var(--m-primary-soft);
  border-color: var(--m-primary);
}
.step-card.done { border-color: var(--m-border); }
.step-head { display: flex; align-items: center; gap: 8px; }
.step-kind {
  text-transform: uppercase; font-size: 10px; font-weight: 700;
  letter-spacing: .06em; color: var(--m-text-secondary);
  background: var(--m-surface-variant); padding: 2px 8px; border-radius: 4px;
}
.step-card.running .step-kind { background: var(--m-primary); color: #fff; }
.step-name { font-family: 'Roboto Mono', monospace; font-size: 12px; color: var(--m-text); }

.step-detail { margin-top: 8px; }
.step-detail summary { cursor: pointer; font-size: 12px; padding: 2px 0; }
.step-block { margin-top: 6px; }
.step-label { font-size: 11px; font-weight: 600; color: var(--m-text-secondary); text-transform: uppercase; letter-spacing: .06em; margin-bottom: 4px; }
.step-block pre {
  background: #f8f9fa; padding: 8px 10px; border-radius: 6px;
  font-family: 'Roboto Mono', monospace; font-size: 11.5px;
  margin: 0; max-height: 200px; overflow: auto; white-space: pre-wrap; word-break: break-word;
}

/* Composer */
.composer-wrap { padding: 12px 24px 24px; max-width: 850px; width: 100%; margin: 0 auto; box-sizing: border-box; }

.files-row { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
.files-row .el-tag :deep(.el-icon) { margin-right: 4px; vertical-align: -2px; }

/* Composer file chips with parse status */
.file-chip {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 4px 6px 10px;
  background: var(--m-bg-soft);
  border: 1px solid var(--m-border);
  border-radius: var(--m-radius-pill);
  font-size: 12px;
  max-width: 280px;
  transition: border-color .2s, background .2s;
}
.file-chip.parsing { border-color: var(--m-primary); background: var(--m-primary-soft); }
.file-chip.done { border-color: transparent; background: var(--m-bg-soft); }
.file-chip.failed { border-color: var(--m-danger); background: #fce8e6; }

.file-chip .chip-leading { color: var(--m-text-secondary); flex-shrink: 0; }
.file-chip .chip-leading.ok { color: var(--m-success); }
.file-chip .chip-leading.err { color: var(--m-danger); }
.file-chip .spin { animation: spin 1s linear infinite; }

.file-chip .chip-name {
  font-weight: 500; color: var(--m-text);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  max-width: 160px;
}
.file-chip .chip-meta {
  font-size: 11px; color: var(--m-text-secondary);
  flex-shrink: 0;
}
.file-chip .chip-action {
  background: transparent; border: none; cursor: pointer;
  font-size: 11px; color: var(--m-danger); font-weight: 500;
  padding: 0 4px;
}
.file-chip .chip-close {
  width: 20px; height: 20px; border-radius: 50%;
  border: none; background: transparent; cursor: pointer;
  display: inline-flex; align-items: center; justify-content: center;
  color: var(--m-text-secondary);
  transition: background .15s, color .15s;
}
.file-chip .chip-close:hover { background: var(--m-surface-variant); color: var(--m-text); }

/* Inline file chips on user message bubbles */
.msg-files {
  display: flex; flex-wrap: wrap; gap: 4px;
  margin-bottom: 6px;
}
.msg-file-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px;
  background: rgba(255,255,255,.18);
  border-radius: var(--m-radius-pill);
  font-size: 11px;
}
.msg-file-chip.clickable { cursor: pointer; transition: background .15s; }
.msg-file-chip.clickable:hover { background: rgba(255,255,255,.32); }
.msg.assistant .msg-file-chip { background: var(--m-surface-variant); color: var(--m-text-secondary); }
.msg.assistant .msg-file-chip.clickable:hover { background: var(--m-primary-soft); color: var(--m-primary); }
.msg-file-meta { opacity: .7; }

.composer {
  display: flex; align-items: flex-end; gap: 8px;
  background: var(--m-bg-soft);
  border-radius: 28px;
  padding: 8px 8px 8px 12px;
  transition: box-shadow .15s ease;
}
.composer:focus-within { box-shadow: 0 0 0 2px var(--m-primary); }
.composer :deep(.el-textarea__inner) {
  border: none !important; background: transparent !important; box-shadow: none !important;
  padding: 8px 4px !important; min-height: 24px !important; resize: none; font-size: 14.5px;
}
.icon-btn, .send-btn {
  border: none; background: transparent; cursor: pointer;
  width: 40px; height: 40px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  color: var(--m-text-secondary); transition: background .15s ease;
}
.icon-btn:hover { background: var(--m-surface-variant); color: var(--m-text); }
.send-btn { background: var(--m-primary); color: #fff; }
.send-btn:hover:not(:disabled) { background: var(--m-primary-hover); }
.send-btn:disabled { background: var(--m-border-strong); cursor: not-allowed; }

.is-loading { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
