<template>
  <div class="chat-wrap" :class="{ 'split-mode': previewFile }">
    <!-- Conversation -->
    <section class="conv">
      <div ref="scrollRef" class="messages">
        <div v-if="!chat.currentConvId || chat.messages.length === 0" class="welcome">
          <div class="welcome-mark">
            <img class="welcome-logo" src="/logo.png" alt="Agent Mill" />
          </div>
          <h2 v-if="chat.currentAgent">
            你好,我是 {{ chat.currentAgent.name }}
            <button class="cap-info-btn" :title="'查看智能体能力'" @click="openCapabilities(chat.currentAgent.id)">
              <el-icon :size="16"><InfoFilled /></el-icon>
            </button>
          </h2>
          <h2 v-else>欢迎</h2>
          <template v-if="chat.currentAgent">
            <p v-if="welcomeIntro" class="welcome-intro">{{ welcomeIntro }}</p>
            <div v-if="welcomeStarters.length" class="welcome-starters">
              <button
                v-for="(q, qi) in welcomeStarters"
                :key="qi"
                class="starter-chip"
                :disabled="sending || !chat.currentAgent"
                @click="useStarter(q)"
              >
                {{ q }}
              </button>
            </div>
            <p v-if="!welcomeIntro && !welcomeStarters.length" class="welcome-intro">在下方输入开始对话</p>
          </template>
          <p v-else>暂无可用智能体,请联系管理员授权</p>
        </div>

        <template v-else>
          <div
            v-for="m in chat.messages"
            v-show="!(m.role === 'user' && m.content_json?.hidden)"
            :key="m.id || m._tmp"
            :class="['msg', m.role, { 'is-highlighted': highlightedMessageId === m.id }]"
            :data-mid="m.id"
          >
            <div v-if="m.role === 'assistant'" :class="['avatar', 'bot', { 'is-thinking': isWaiting(m) }]">
              <span class="dot dot-1" /><span class="dot dot-2" />
              <span class="dot dot-3" /><span class="dot dot-4" />
            </div>
            <div class="bubble-stack">
              <!-- waiting indicator: shown only until first content arrives -->
              <div v-if="isWaiting(m)" class="thinking-pill">
                <span class="thinking-text">{{ thinkingLabel(m) }}</span>
                <span class="thinking-dots"><span /><span /><span /></span>
              </div>

              <!-- meta: 当前回答用的 agent / model. Only after the first token has arrived. -->
              <div v-if="m.role === 'assistant' && m._meta && m.content_json?.text" class="msg-meta">
                <span>{{ m._meta.agent_name }}</span>
                <span class="dot-sep">·</span>
                <code>{{ m._meta.model_id }}</code>
                <button
                  v-if="chat.currentAgent"
                  class="cap-info-btn cap-info-btn-sm"
                  :title="'查看智能体能力'"
                  @click="openCapabilities(chat.currentAgent.id)"
                >
                  <el-icon :size="13"><InfoFilled /></el-icon>
                </button>
              </div>

              <!-- thinking block -->
              <details v-if="m.content_json?.thinking || m._thinking" class="thinking-card" :open="m._thinkingOpen ?? !m.content_json?.text">
                <summary>
                  <el-icon><Cpu /></el-icon>
                  <span>思考过程</span>
                  <span class="muted" style="font-size:11px;margin-left:6px">{{ (m.content_json?.thinking || m._thinking || '').length }} 字</span>
                </summary>
                <div class="thinking-body">
                  <div
                    :ref="(el) => setThinkingRef(el, m)"
                    class="thinking-content"
                  >{{ m.content_json?.thinking || m._thinking }}</div>
                </div>
              </details>

              <!-- tool / mcp / skill steps -->
              <div v-if="m._steps?.length || m.tool_calls_json?.trace?.length" class="step-list">
                <template v-for="(s, i) in (m._steps || normalizeTrace(m.tool_calls_json?.trace))" :key="i">
                  <PackProgressCard
                    v-if="s.name?.startsWith('run_pack__')"
                    :pack-code="s.name.replace('run_pack__', '')"
                    :input="s.input"
                    :output="s.output"
                  />
                  <details v-else :class="['step-card', s.status]" :open="false">
                    <summary class="step-head">
                      <el-icon v-if="s.status === 'running'" class="is-loading"><Loading /></el-icon>
                      <el-icon v-else-if="s.status === 'done'" style="color:var(--m-success)"><CircleCheckFilled /></el-icon>
                      <el-icon v-else><Tools /></el-icon>
                      <span class="step-kind">{{ s.kind }}</span>
                      <span class="step-name">{{ s.label || s.name }}</span>
                      <span v-if="s.serverName" class="step-server">{{ s.serverName }}</span>
                      <span v-if="s.duration_ms" class="muted step-dur">{{ s.duration_ms }}ms</span>
                      <span v-if="s.input || s.output || s.name" class="step-io-toggle">
                        <span class="step-io-label">详情</span>
                        <svg class="step-chevron" viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 6 8 10 12 6"/></svg>
                      </span>
                    </summary>
                    <div class="step-body">
                      <div class="step-block step-id-row">
                        <span class="step-label">工具 ID</span>
                        <code class="step-raw-name">{{ s.name }}</code>
                      </div>
                      <div v-if="s.input" class="step-block"><div class="step-label">Input</div><pre>{{ formatStepData(s.input) }}</pre></div>
                      <div v-if="s.output" class="step-block"><div class="step-label">Output</div><pre>{{ formatStepData(s.output) }}</pre></div>
                    </div>
                  </details>
                </template>
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

              <!-- UI Schema surfaces (interactive components) -->
              <div v-if="(m.content_json?.uis?.length) || m._uis?.length" class="ui-block">
                <MessageDispatcher
                  v-for="(s, ui) in (m._uis?.length ? m._uis : m.content_json.uis)"
                  :key="s.surface_id || ui"
                  :schema="s"
                  :on-agent-call="onAgentCall"
                />
              </div>

              <!-- main answer -->
              <div v-if="m.content_json?.text || m.role === 'user'" :class="['bubble', { 'bubble--clamped': m.role === 'user' && isLongUserMsg(m) && !expandedMsgs[getMsgKey(m)] }]">
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
                  <div v-if="isLongUserMsg(m) && !expandedMsgs[getMsgKey(m)]" class="bubble-clamp-fade" />
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

              <!-- expand/collapse for long user messages -->
              <button
                v-if="m.role === 'user' && isLongUserMsg(m)"
                class="bubble-expand-btn"
                @click="toggleExpandMsg(m)"
              >
                {{ expandedMsgs[getMsgKey(m)] ? '收起' : '展开' }}
                <svg :class="['bubble-expand-chevron', { rotated: expandedMsgs[getMsgKey(m)] }]" viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 6 8 10 12 6"/></svg>
              </button>

              <!-- assistant message action bar (copy + favorite) -->
              <div
                v-if="m.role === 'assistant' && m.content_json?.text && !m._streaming"
                class="msg-actions"
              >
                <button class="msg-action" @click="copyAnswer(m)" title="复制回答">
                  <el-icon :size="14"><DocumentCopy /></el-icon>
                  <span>复制</span>
                </button>
                <button
                  class="msg-action"
                  :class="{ active: isFavorited(m) }"
                  @click="toggleFavorite(m)"
                  :title="isFavorited(m) ? '取消收藏' : '收藏到空间'"
                >
                  <el-icon :size="14">
                    <StarFilled v-if="isFavorited(m)" />
                    <Star v-else />
                  </el-icon>
                  <span>{{ isFavorited(m) ? '已收藏' : '收藏' }}</span>
                </button>
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
            <span v-else-if="f.parse_status === 'skipped'" class="chip-meta">原始文件</span>
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
          <button v-if="sending" class="stop-btn" title="停止生成" @click="stopStream">
            <el-icon class="stop-spin" :size="22"><Loading /></el-icon>
          </button>
          <button v-else class="send-btn" :disabled="!input.trim() || !chat.currentAgent" @click="send">
            <el-icon :size="18"><Promotion /></el-icon>
          </button>
        </div>
      </div>
    </section>
    <PreviewPanel v-if="previewFile" :file="previewFile" @close="closePreview" />
    <AgentCapabilityDrawer
      v-model="capDrawerVisible"
      :agent-id="capDrawerAgentId"
      :agent-name="chat.currentAgent?.name"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'
import { useChat } from '@/stores/chat'
import { useSpace } from '@/stores/space'
import MarkdownIt from 'markdown-it'
import WidgetRenderer from '@/components/WidgetRenderer.vue'
import FileCard from '@/components/FileCard.vue'
import PackProgressCard from '@/components/PackProgressCard.vue'
import PreviewPanel from '@/components/PreviewPanel.vue'
import AgentCapabilityDrawer from '@/components/AgentCapabilityDrawer.vue'
import MessageDispatcher from '@/agent-ui/engine/MessageDispatcher.vue'
import { InfoFilled, Loading } from '@element-plus/icons-vue'
import { parseMessageContent } from '@/lib/widget-parser'
import { resolveToolMeta } from '@/lib/toolDisplay'

const md = new MarkdownIt({ breaks: true, linkify: true })
const chat = useChat()
const space = useSpace()
const route = useRoute()

const input = ref('')
const sending = ref(false)
const streamAbortController = ref<AbortController | null>(null)

function stopStream() {
  streamAbortController.value?.abort()
}

const expandedMsgs = ref<Record<string, boolean>>({})
function getMsgKey(m: any) { return String(m.id ?? m._tmp ?? '') }
function toggleExpandMsg(m: any) {
  const key = getMsgKey(m)
  expandedMsgs.value[key] = !expandedMsgs.value[key]
}
function isLongUserMsg(m: any) {
  const text = m.content_json?.text || ''
  return text.length > 400 || text.split('\n').length > 8
}

const scrollRef = ref<HTMLElement | null>(null)
const previewFile = ref<any | null>(null)
const capDrawerVisible = ref(false)
const capDrawerAgentId = ref<number | null>(null)
function openCapabilities(agentId: number) {
  capDrawerAgentId.value = agentId
  capDrawerVisible.value = true
}

/** Split the current agent's description into a plain intro paragraph and a
 *  list of starter questions. Lines starting with '- ', '• ', '* ' or a
 *  numbered prefix like '1.' are treated as starter questions; everything
 *  else joins the intro. */
const parsedWelcome = computed<{ intro: string; starters: string[] }>(() => {
  const desc = chat.currentAgent?.description || ''
  if (!desc) return { intro: '', starters: [] }
  const starterRe = /^\s*(?:[-•*]|\d+[.、])\s+(.+)$/
  const introLines: string[] = []
  const starters: string[] = []
  for (const raw of desc.split(/\r?\n/)) {
    const m = raw.match(starterRe)
    if (m && m[1].trim()) {
      starters.push(m[1].trim())
    } else if (raw.trim()) {
      introLines.push(raw.trim())
    }
  }
  return { intro: introLines.join(' '), starters: starters.slice(0, 4) }
})
const welcomeIntro = computed(() => parsedWelcome.value.intro)
const welcomeStarters = computed(() => parsedWelcome.value.starters)

function useStarter(q: string) {
  if (!q || sending.value || !chat.currentAgent) return
  input.value = q
  send()
}

function closePreview() { previewFile.value = null }

// "Jump back to original conversation" support — Space.vue routes to
// /chat?msg=<id> after selectConv-ing the right conversation. We then scroll
// that message into view and flash a highlight ring on it for ~1.6s.
const highlightedMessageId = ref<number | null>(null)
let highlightTimer: any = null
async function scrollToMessage(messageId: number) {
  if (!messageId) return
  for (let i = 0; i < 12; i++) {
    await nextTick()
    const el = document.querySelector(`.msg[data-mid="${messageId}"]`) as HTMLElement | null
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      highlightedMessageId.value = messageId
      if (highlightTimer) clearTimeout(highlightTimer)
      highlightTimer = setTimeout(() => { highlightedMessageId.value = null }, 1600)
      return
    }
    await new Promise((r) => setTimeout(r, 80))  // wait for messages to render
  }
}

onMounted(async () => {
  if (!chat.loaded) await chat.loadInit()
  // Deep-link: /chat?conv=N opens an existing conversation (e.g. from a task run).
  const convQuery = route.query.conv
  const convId = Array.isArray(convQuery) ? Number(convQuery[0]) : Number(convQuery)
  if (convId && !Number.isNaN(convId) && convId !== chat.currentConvId) {
    let conv = chat.convs.find((c: any) => c.id === convId)
    if (!conv) conv = { id: convId }
    try { await chat.selectConv(conv) } catch {}
  }
  await scrollBottom()
  // Deep-link: /chat?msg=N highlights & scrolls to that message.
  const msgQuery = route.query.msg
  const msgId = Array.isArray(msgQuery) ? Number(msgQuery[0]) : Number(msgQuery)
  if (msgId && !Number.isNaN(msgId)) await scrollToMessage(msgId)
})

watch(() => chat.currentConvId, async () => {
  await scrollBottom()
})

// Re-trigger scroll when ?msg= changes while already on /chat
watch(() => route.query.msg, async (val) => {
  const id = Array.isArray(val) ? Number(val[0]) : Number(val)
  if (id && !Number.isNaN(id)) await scrollToMessage(id)
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
    await chat.ensureConv()
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

// Bridge for UI Schema → Agent. The text carries one of two prefixes:
//   [UI_ACTION] tool=...  → backend bypasses LLM and calls the tool directly
//   [UI_MSG] <text>       → backend strips the prefix and runs the LLM normally,
//                            but the user-message it persists is marked hidden
//                            so the synthetic bubble doesn't show up in the transcript.
// Either way, we don't push a user bubble locally.
async function onAgentCall(text: string) {
  if (!chat.currentAgent || sending.value) return
  if (!chat.currentConvId) await chat.ensureConv()

  const placeholder: any = reactive({
    _tmp: Date.now(), role: 'assistant',
    content_json: { text: '' }, tool_calls_json: null,
    _meta: null, _thinking: '', _steps: [], _stepIndex: {}, _files: [], _uis: [],
    _streaming: true,
  })
  chat.messages.push(placeholder)
  sending.value = true
  await scrollBottom()

  const token = localStorage.getItem('access_token')
  const controller = new AbortController()
  streamAbortController.value = controller
  try {
    const resp = await fetch(`/api/conversations/${chat.currentConvId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ content: text, file_ids: [] }),
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
      placeholder.content_json.text += `\n\n[网络错误] ${e.message}`
    }
  } finally {
    streamAbortController.value = null
    placeholder._streaming = false
    sending.value = false
  }
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
  if (!Array.isArray(trace) || !trace.length) return []
  const steps: any[] = []
  const stepIndex: Record<string, number> = {}

  for (const t of trace) {
    const data = t?.data || {}
    if (t?.type === 'tool_use') {
      const id = String(data.id || data.name || `tool-${steps.length}`)
      const existingIdx = stepIndex[id]
      if (existingIdx != null) {
        const s = steps[existingIdx]
        if (data.input && (typeof data.input !== 'object' || Object.keys(data.input).length)) {
          s.input = data.input
        }
        continue
      }
      stepIndex[id] = steps.length
      const meta = resolveToolMeta(data.name || '')
      steps.push({
        kind: meta.kind,
        name: data.name || '(tool)',
        label: meta.label,
        serverName: meta.serverName,
        input: data.input,
        status: 'done',
      })
      continue
    }
    if (t?.type === 'tool_result') {
      const id = data.tool_use_id != null ? String(data.tool_use_id) : ''
      let idx = id ? stepIndex[id] : undefined
      if (idx == null) idx = steps.length - 1
      const s = steps[idx]
      if (s) {
        s.output = data.content
      }
    }
  }

  return steps
}

function formatStepData(v: any) {
  if (typeof v === 'string') {
    try { return JSON.stringify(JSON.parse(v), null, 2) } catch { return v }
  }
  return JSON.stringify(v, null, 2)
}

// -------- Thinking block: per-message scroll refs --------
const thinkingRefs = new WeakMap<object, HTMLElement>()

function setThinkingRef(el: unknown, m: object) {
  if (el instanceof HTMLElement) thinkingRefs.set(m, el)
}

function scrollThinkingToBottom(m: object) {
  nextTick(() => {
    const el = thinkingRefs.get(m)
    if (el) el.scrollTop = el.scrollHeight
  })
}

// True while we've sent the question but no visible content has come back yet.
// Hides as soon as text / thinking / tool steps / files / UIs appear.
function isWaiting(m: any): boolean {
  if (m.role !== 'assistant' || !m._streaming) return false
  if (m.content_json?.text) return false
  if (m._thinking) return false
  if (m._steps?.length) return false
  if (m._files?.length) return false
  if (m._uis?.length) return false
  return true
}

// Show a slightly more informative label once the model has acknowledged
// (we got `meta`) but before any visible token.
function thinkingLabel(m: any): string {
  return m._meta ? '正在思考' : '正在连接智能体'
}

// -------- Copy / Favorite (message action bar) --------

function plainTextFromMarkdown(md_src: string): string {
  // Strip common markdown markers for the plaintext clipboard slot. Keeps
  // line breaks, list bullets become "- ", removes inline emphasis.
  let s = md_src
  s = s.replace(/```([\s\S]*?)```/g, (_m, code) => code)         // code fences → bare code
  s = s.replace(/`([^`]+)`/g, '$1')                              // inline code
  s = s.replace(/\*\*([^*]+)\*\*/g, '$1').replace(/\*([^*]+)\*/g, '$1')
  s = s.replace(/__([^_]+)__/g, '$1').replace(/_([^_]+)_/g, '$1')
  s = s.replace(/^#{1,6}\s+/gm, '')                              // headings
  s = s.replace(/^\s*[-*+]\s+/gm, '• ')                          // bullets
  s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '$1 ($2)')           // links
  return s
}

async function copyAnswer(m: any) {
  const text = m.content_json?.text || ''
  if (!text) return
  const html = md.render(text)
  const plain = plainTextFromMarkdown(text)
  try {
    if (typeof (window as any).ClipboardItem === 'function' && navigator.clipboard?.write) {
      const item = new ClipboardItem({
        'text/html': new Blob([html], { type: 'text/html' }),
        'text/plain': new Blob([plain], { type: 'text/plain' }),
      })
      await navigator.clipboard.write([item])
    } else {
      await navigator.clipboard.writeText(plain)
    }
    ElMessage.success('已复制')
  } catch {
    // last-resort fallback for older browsers / non-HTTPS dev hosts
    try {
      const ta = document.createElement('textarea')
      ta.value = plain
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      ta.remove()
      ElMessage.success('已复制')
    } catch {
      ElMessage.error('复制失败')
    }
  }
}

function isFavorited(m: any): boolean {
  return space.isFavorited(m?.id)
}

async function toggleFavorite(m: any) {
  if (!m?.id) {
    ElMessage.warning('该消息还未保存,稍后再试')
    return
  }
  if (isFavorited(m)) {
    try {
      await ElMessageBox.confirm('确定取消收藏吗?', '确认', { type: 'warning' })
    } catch { return }
    try {
      await space.unfavorite(m.id)
      ElMessage.success('已取消收藏')
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail || '操作失败')
    }
  } else {
    try {
      await space.favorite(m.id)
      ElMessage.success('已加入空间')
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail || '操作失败')
    }
  }
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
    await chat.ensureConv()
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
    _meta: null, _thinking: '', _steps: [], _stepIndex: {} as Record<string, number>, _files: [], _uis: [],
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
  const controller = new AbortController()
  streamAbortController.value = controller
  try {
    const resp = await fetch(`/api/conversations/${chat.currentConvId}/messages`, {
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
        let json: any
        try { json = JSON.parse(line.slice(5).trim()) } catch { continue }
        applyEvent(placeholder, json)
        await scrollBottom()
      }
    }
  } catch (e: any) {
    if (e.name !== 'AbortError') {
      placeholder.content_json.text += `\n\n[网络错误] ${e.message}`
    }
  } finally {
    streamAbortController.value = null
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
    scrollThinkingToBottom(m)
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
.welcome-intro { max-width: 640px; color: var(--m-text-secondary); line-height: 1.6; }
.welcome-starters {
  margin-top: 18px;
  display: flex; flex-direction: column; gap: 8px;
  align-items: center;
  width: 100%; max-width: 560px;
}
.starter-chip {
  appearance: none;
  width: 100%;
  text-align: left;
  font-size: 13px; line-height: 1.5;
  padding: 10px 14px;
  border: 1px solid var(--m-border, #e8eaed);
  border-radius: 12px;
  background: #ffffff;
  color: var(--m-text, #202124);
  cursor: pointer;
  transition: background .15s, border-color .15s, box-shadow .15s, transform .1s;
  box-shadow: 0 1px 2px rgba(60,64,67,.04);
}
.starter-chip:hover:not(:disabled) {
  background: #f8f9fa;
  border-color: #aecbfa;
  box-shadow: 0 1px 3px rgba(26,115,232,.12);
}
.starter-chip:active:not(:disabled) { transform: scale(.99); }
.starter-chip:disabled { opacity: .55; cursor: not-allowed; }
.welcome-mark { width: 64px; height: 64px; }
.welcome-logo { width: 100%; height: 100%; border-radius: 12px; object-fit: contain; }

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

/* Waiting state: avatar pulses, dots cycle */
.avatar.bot.is-thinking {
  border-color: var(--m-primary);
  box-shadow: 0 0 0 0 var(--m-primary-soft);
  animation: avatar-glow 1.6s ease-in-out infinite;
}
.avatar.bot.is-thinking .dot { animation: dot-pulse 1.2s ease-in-out infinite; }
.avatar.bot.is-thinking .dot-1 { animation-delay: 0s; }
.avatar.bot.is-thinking .dot-2 { animation-delay: .15s; }
.avatar.bot.is-thinking .dot-3 { animation-delay: .45s; }
.avatar.bot.is-thinking .dot-4 { animation-delay: .3s; }
@keyframes dot-pulse {
  0%, 100% { transform: scale(0.85); opacity: .55; }
  50%      { transform: scale(1.15); opacity: 1; }
}
@keyframes avatar-glow {
  0%, 100% { box-shadow: 0 0 0 0 rgba(66,133,244,.18); }
  50%      { box-shadow: 0 0 0 4px rgba(66,133,244,.06); }
}

/* Thinking pill — shown next to avatar until first content arrives */
.thinking-pill {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 8px 14px;
  background: var(--m-bg-soft);
  border-radius: var(--m-radius-pill);
  font-size: 13px; color: var(--m-text-secondary);
  align-self: flex-start;
  width: fit-content;
}
.thinking-text { font-weight: 500; }
.thinking-dots { display: inline-flex; gap: 3px; }
.thinking-dots span {
  width: 5px; height: 5px; border-radius: 50%;
  background: currentColor;
  animation: dot-bounce 1.2s ease-in-out infinite;
}
.thinking-dots span:nth-child(2) { animation-delay: .15s; }
.thinking-dots span:nth-child(3) { animation-delay: .3s; }
@keyframes dot-bounce {
  0%, 80%, 100% { opacity: .3; transform: translateY(0); }
  40%           { opacity: 1; transform: translateY(-3px); }
}

.bubble {
  max-width: 100%; padding: 12px 16px;
  background: var(--m-bg-soft); border: 1px solid transparent;
  border-radius: var(--m-radius-lg);
  font-size: 14.5px; line-height: 1.65; word-break: break-word;
}

/* "Jump back" highlight from /chat?msg=<id> */
.msg.is-highlighted .bubble {
  animation: msg-flash 1.6s ease-out;
}
@keyframes msg-flash {
  0%   { box-shadow: 0 0 0 0 var(--m-primary-soft); background: var(--m-primary-soft); }
  60%  { box-shadow: 0 0 0 6px transparent; background: var(--m-primary-soft); }
  100% { box-shadow: 0 0 0 0 transparent; background: var(--m-bg-soft); }
}

/* assistant message action bar — sits beneath the bubble */
.msg-actions {
  display: flex; align-items: center; gap: 4px;
  margin-top: 4px;
  padding: 0 4px;
  opacity: .5;
  transition: opacity .15s ease;
}
.msg:hover .msg-actions { opacity: 1; }
.msg-action {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 4px 8px;
  font-size: 12px;
  color: var(--m-text-secondary);
  background: transparent;
  border: none;
  border-radius: var(--m-radius);
  cursor: pointer;
  transition: background .15s, color .15s;
}
.msg-action:hover { background: var(--m-surface-variant); color: var(--m-text); }
.msg-action.active { color: var(--m-primary); }
.msg-action.active:hover { background: var(--m-primary-soft); color: var(--m-primary-hover); }
.msg.user .bubble {
  background: var(--m-primary); color: #fff; border-color: transparent;
  border-radius: var(--m-radius-lg) var(--m-radius-sm) var(--m-radius-lg) var(--m-radius-lg);
}
.bubble--clamped { max-height: 200px; overflow: hidden; position: relative; }
.bubble-clamp-fade {
  position: absolute; bottom: 0; left: 0; right: 0; height: 56px;
  background: linear-gradient(to bottom, transparent, var(--m-primary));
  pointer-events: none;
  border-radius: 0 0 var(--m-radius-lg) var(--m-radius-sm);
}
.bubble-expand-btn {
  display: inline-flex; align-items: center; gap: 3px;
  align-self: flex-end;
  padding: 2px 8px; margin-top: 2px;
  font-size: 12px; color: var(--m-primary);
  background: transparent; border: none;
  cursor: pointer; opacity: .75;
  transition: opacity .15s;
}
.bubble-expand-btn:hover { opacity: 1; }
.bubble-expand-chevron { transition: transform .2s ease; }
.bubble-expand-chevron.rotated { transform: rotate(180deg); }
.msg.assistant .bubble { border-radius: var(--m-radius-sm) var(--m-radius-lg) var(--m-radius-lg) var(--m-radius-lg); }
.bubble :deep(p) { margin: 4px 0; }
.bubble :deep(p:first-child) { margin-top: 0; }
.bubble :deep(p:last-child) { margin-bottom: 0; }
.bubble :deep(pre) {
  background: #f8f9fa;
  color: #202124;
  padding: 14px 16px;
  border-radius: var(--m-radius);
  border: 1px solid #e8eaed;
  overflow: auto;
  max-height: 420px;
  font-size: 13px;
  line-height: 1.55;
  margin: 8px 0;
  font-family: 'Roboto Mono', ui-monospace, 'SFMono-Regular', Menlo, Consolas, monospace;
  scrollbar-width: thin;
  scrollbar-color: #c4c7c5 transparent;
}
.bubble :deep(pre)::-webkit-scrollbar { width: 8px; height: 8px; }
.bubble :deep(pre)::-webkit-scrollbar-track { background: transparent; }
.bubble :deep(pre)::-webkit-scrollbar-thumb { background: #dadce0; border-radius: 4px; }
.bubble :deep(pre)::-webkit-scrollbar-thumb:hover { background: #bdc1c6; }
.bubble :deep(pre code) { background: transparent; color: inherit; padding: 0; font-size: inherit; }
.bubble :deep(code) { font-family: 'Roboto Mono', ui-monospace, 'SFMono-Regular', Menlo, Consolas, monospace; }
.bubble :deep(:not(pre) > code) {
  background: #f1f3f4;
  color: #c5221f;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 13px;
  border: 1px solid #e8eaed;
}
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

.cap-info-btn {
  display: inline-flex; align-items: center; justify-content: center;
  border: none; background: transparent; cursor: pointer;
  margin-left: 8px; padding: 2px 4px; border-radius: 4px;
  color: var(--m-text-secondary); transition: background .15s, color .15s;
}
.cap-info-btn:hover { background: var(--m-surface-variant); color: var(--m-primary); }
.cap-info-btn-sm { margin-left: 4px; padding: 1px 3px; }

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
/* Wrapper: positions gradient overlay pseudo-elements */
.thinking-body {
  position: relative;
}
.thinking-body::before,
.thinking-body::after {
  content: '';
  position: absolute;
  left: 0; right: 0;
  height: 28px;
  pointer-events: none;
  z-index: 1;
}
.thinking-body::before {
  top: 0;
  background: linear-gradient(to bottom, #fafbfc 0%, transparent 100%);
}
.thinking-body::after {
  bottom: 0;
  background: linear-gradient(to top, #fafbfc 0%, transparent 100%);
}
.thinking-content {
  max-height: 200px;
  overflow-y: auto;
  padding: 10px 14px; white-space: pre-wrap; word-break: break-word;
  color: var(--m-text-secondary); line-height: 1.65; font-size: 13px;
  font-family: 'Inter', sans-serif;
  scrollbar-width: thin;
  scrollbar-color: var(--m-border-strong) transparent;
}
.thinking-content::-webkit-scrollbar { width: 4px; }
.thinking-content::-webkit-scrollbar-track { background: transparent; }
.thinking-content::-webkit-scrollbar-thumb {
  background: var(--m-border-strong);
  border-radius: 2px;
}

/* step cards (tool / mcp / skill calls) */
.step-list { display: flex; flex-direction: column; gap: 6px; }
.step-card {
  border: 1px solid var(--m-border);
  border-radius: var(--m-radius);
  background: var(--m-surface);
  padding: 0;
  font-size: 13px;
  transition: background .2s, border-color .2s;
}
.step-card.running {
  background: var(--m-primary-soft);
  border-color: var(--m-primary);
}
.step-card.done { border-color: var(--m-border); }
.step-head {
  display: flex; align-items: center; gap: 8px; justify-content: space-between;
  padding: 10px 12px;
  cursor: pointer;
  list-style: none;
  user-select: none;
}
.step-head::-webkit-details-marker { display: none; }
.step-head:hover { background: color-mix(in srgb, var(--m-primary) 6%, transparent); }
.step-kind {
  text-transform: uppercase; font-size: 10px; font-weight: 700;
  letter-spacing: .06em; color: var(--m-text-secondary);
  background: var(--m-surface-variant); padding: 2px 8px; border-radius: 4px;
  flex-shrink: 0;
}
.step-card.running .step-kind { background: var(--m-primary); color: #fff; }
.step-name { font-size: 13px; color: var(--m-text); flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.step-server {
  font-size: 11px; color: var(--m-text-secondary);
  background: var(--m-surface-variant); padding: 1px 6px; border-radius: 3px;
  flex-shrink: 0; font-style: italic;
}
.step-dur { font-size: 11px; flex-shrink: 0; }

.step-io-toggle {
  display: inline-flex; align-items: center; gap: 4px;
  color: var(--m-primary); font-size: 11px; font-weight: 500;
  flex-shrink: 0; white-space: nowrap;
}
.step-io-label { cursor: pointer; }
.step-chevron {
  color: var(--m-text-secondary);
  transition: transform .2s ease;
}
.step-card[open] .step-chevron { transform: rotate(180deg); color: var(--m-primary); }

.step-body {
  padding: 0 12px 10px 12px;
  border-top: 1px solid var(--m-border);
  background: color-mix(in srgb, var(--m-bg-soft) 50%, var(--m-surface));
}
.step-id-row { display: flex; align-items: center; gap: 8px; padding: 8px 0 4px; }
.step-raw-name { font-family: 'Roboto Mono', monospace; font-size: 11px; color: var(--m-text-secondary); word-break: break-all; }
.step-block { margin-top: 8px; }
.step-block:first-child { margin-top: 0; }
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
.stop-btn {
  border: none; cursor: pointer;
  width: 40px; height: 40px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  background: transparent; color: var(--m-text-secondary, #80868b);
  transition: background .15s ease, color .15s ease;
  flex-shrink: 0;
}
.stop-btn:hover { background: var(--m-surface-variant, #e8eaed); color: var(--m-text, #3c4043); }
.stop-btn:active { transform: scale(.93); }
.stop-spin { animation: spin 1s linear infinite; }

.is-loading { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
