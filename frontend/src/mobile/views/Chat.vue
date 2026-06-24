<template>
  <div class="mb-page chat-page">
    <MobileChatHeader
      :agent="chat.currentAgent"
      @toggle-drawer="drawerOpen = true"
      @open-settings="agentSheetOpen = true"
      @new-conv="onNewConv"
    />

    <div ref="scrollRef" class="messages">
      <div v-if="!chat.currentConvId || chat.messages.length === 0" class="welcome">
        <div class="welcome-brand-row">
          <img class="welcome-logo" src="/logo-icon.png" alt="Agent Mill" />
          <div class="welcome-brand-text">
            <h2 class="welcome-brand">Agent Mill</h2>
            <p class="welcome-subtitle">你的数字员工工厂</p>
          </div>
        </div>
        
        <!-- 数字员工展示区 -->
        <div class="welcome-workers">
          <div 
            v-for="agent in chat.agents.slice(0, 4)" 
            :key="agent.id"
            class="worker-card"
            :class="{ active: chat.currentAgent?.id === agent.id }"
            @click="selectAgent(agent)"
          >
            <div class="worker-avatar" :style="{ background: agentGradient(agent?.id || 0) }">
              <img v-if="agent.icon_url" :src="agent.icon_url" />
              <span v-else>{{ agentInitial(agent) }}</span>
            </div>
            <div class="worker-name">{{ agent.name }}</div>
          </div>
        </div>
        
        <!-- 选中员工的介绍 -->
        <div v-if="chat.currentAgent" class="welcome-intro-section">
          <p class="welcome-intro">你好，我是{{ chat.currentAgent.name }}</p>
          <p class="welcome-desc">{{ chat.currentAgent.description }}</p>
        </div>
        
        <template v-else>
          <p class="welcome-intro">选择一位数字员工开始对话</p>
        </template>
        
        <!-- 快捷提问 -->
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
        
        <p v-if="!welcomeIntro && !welcomeStarters.length && chat.currentAgent" class="welcome-intro">在下方输入开始对话</p>
        <p v-else-if="!chat.agents.length" class="welcome-intro">暂无可用数字员工，请联系管理员授权</p>
      </div>

      <template v-else>
        <div
          v-for="m in chat.messages"
          v-show="!(m.role === 'user' && m.content_json?.hidden)"
          :key="m.id || m._tmp"
          :class="['msg', m.role]"
        >
          <div class="bubble-stack">
            <div v-if="isWaiting(m)" class="thinking-pill">
              <span>{{ m._meta ? '正在思考' : '正在连接数字员工' }}</span>
              <span class="thinking-dots"><span/><span/><span/></span>
            </div>

            <details v-if="m.content_json?.thinking || m._thinking" class="thinking-card">
              <summary>思考过程</summary>
              <div class="thinking-body">
                <div
                  :ref="(el) => setThinkingRef(el, m)"
                  class="thinking-content"
                >{{ m.content_json?.thinking || m._thinking }}</div>
              </div>
            </details>

            <div v-if="m._steps?.length || m.tool_calls_json?.trace?.length" class="step-list">
              <details
                v-for="(s, i) in (m._steps || normalizeTrace(m.tool_calls_json?.trace))"
                :key="i"
                :class="['step-card', s.status]"
              >
                <summary class="step-head">
                  <span class="step-kind">{{ s.kind }}</span>
                  <span class="step-name">{{ s.label || s.name }}</span>
                  <span v-if="s.serverName" class="step-server">{{ s.serverName }}</span>
                  <span v-if="s.duration_ms" class="step-dur">{{ s.duration_ms }}ms</span>
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
                  <div v-if="s.input" class="step-block">
                    <div class="step-label">Input</div>
                    <pre>{{ formatJson(s.input) }}</pre>
                  </div>
                  <div v-if="s.output" class="step-block">
                    <div class="step-label">Output</div>
                    <pre>{{ formatJson(s.output) }}</pre>
                  </div>
                </div>
              </details>
            </div>

            <!-- File cards (assistant-emitted files) -->
            <div v-if="(m.content_json?.files?.length) || m._files?.length" class="files-block">
              <div
                v-for="(f, fi) in (m._files?.length ? m._files : m.content_json.files)"
                :key="fi"
                :class="['file-card', { clickable: canPreview(f) }]"
                @click="canPreview(f) && openPreview(f)"
              >
                <div class="file-icon">
                  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                </div>
                <div class="file-meta">
                  <div class="file-name">{{ f.name }}</div>
                  <div class="file-sub">
                    <span v-if="f.parsed_chars">{{ f.parsed_chars }} 字</span>
                    <span v-else-if="f.size">{{ formatSize(f.size) }}</span>
                    <span v-if="canPreview(f)" class="file-preview-hint">· 点击预览</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- UI Schema interactive surfaces -->
            <div v-if="(m.content_json?.uis?.length) || m._uis?.length" class="ui-block">
              <MessageDispatcher
                v-for="(s, ui) in (m._uis?.length ? m._uis : m.content_json.uis)"
                :key="s.surface_id || ui"
                :schema="s"
                :on-agent-call="onAgentCall"
              />
            </div>

            <div v-if="m.content_json?.text || m.role === 'user'" :class="['bubble', { 'bubble--clamped': m.role === 'user' && isLongUserMsg(m) && !expandedMsgs[getMsgKey(m)] }]">
              <div v-if="m.role === 'user' && m.content_json?.files?.length" class="msg-files">
                <span
                  v-for="(f, fi) in m.content_json.files"
                  :key="fi"
                  :class="['msg-file-chip', { clickable: canPreview(f) }]"
                  @click="canPreview(f) && openPreview(f)"
                >📎 {{ f.name }}</span>
              </div>
              <div class="bubble-content" v-html="md.render(m.content_json?.text || '')"></div>
              <div v-if="m.role === 'user' && isLongUserMsg(m) && !expandedMsgs[getMsgKey(m)]" class="bubble-clamp-fade" />
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

            <!-- 助手回答操作栏：复制 + 收藏 -->
            <div
              v-if="m.role === 'assistant' && m.content_json?.text && !m._streaming"
              class="msg-actions"
            >
              <button class="msg-action" @click="copyAnswer(m)">
                <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                <span>复制</span>
              </button>
              <button
                class="msg-action"
                :class="{ active: isFavorited(m) }"
                @click="toggleFavorite(m)"
              >
                <svg v-if="isFavorited(m)" viewBox="0 0 24 24" width="15" height="15" fill="currentColor" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
                <svg v-else viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
                <span>{{ isFavorited(m) ? '已收藏' : '收藏' }}</span>
              </button>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- Composer -->
    <MobileComposer
      v-model="input"
      :disabled="sending"
      :sending="sending"
      :has-agent="!!chat.currentAgent"
      :pending-files="chat.pendingFiles"
      @send="send"
      @stop-stream="stopStream"
      @trigger-upload="triggerUpload"
      @file-pick="onFilePick"
      @remove-file="removeFile"
    />

    <!-- Sidebar drawer -->
    <MobileNavDrawer
      :visible="drawerOpen"
      :conversations="chat.convs"
      :current-conv-id="chat.currentConvId"
      :user="auth.user"
      :unread-count="unreadCount"
      @close="drawerOpen = false"
      @new-conv="onNewConvFromDrawer"
      @go-route="goRoute"
      @select-conv="onSelectConv"
      @conv-actions="onConvActions"
      @open-user-settings="userSheetOpen = true"
    />

    <!-- Agent bottom sheet -->
    <MobileAgentSheet
      :visible="agentSheetOpen"
      :agents="chat.agents"
      :current-agent-id="chat.currentAgent?.id"
      @close="agentSheetOpen = false"
      @select="onPickAgent"
    />

    <!-- User settings sheet -->
    <MobileUserSheet
      :visible="userSheetOpen"
      :user="auth.user"
      @close="userSheetOpen = false"
      @change-password="onChangePassword"
      @logout="onLogout"
    />

    <!-- Conv actions sheet -->
    <div :class="['mb-drawer-mask', { open: !!convActionTarget }]" @click="convActionTarget = null" />
    <div :class="['mb-sheet', { open: !!convActionTarget }]">
      <div class="mb-sheet-handle" />
      <div class="mb-sheet-title">{{ convActionTarget?.title || '对话' }}</div>
      <div class="mb-sheet-body">
        <div class="action-item" @click="onRenameConv">重命名</div>
        <div class="action-item danger" @click="onDeleteConv">删除对话</div>
        <div class="action-item cancel" @click="convActionTarget = null">取消</div>
      </div>
    </div>

    <!-- Change password sheet -->
    <div :class="['mb-drawer-mask', { open: changePasswordOpen }]" @click="changePasswordOpen = false" />
    <div :class="['mb-sheet', { open: changePasswordOpen }]">
      <div class="mb-sheet-handle" />
      <div class="mb-sheet-title">修改密码</div>
      <div class="mb-sheet-body pwd-body">
        <label class="field">
          <span>原密码</span>
          <input v-model="pwd.old" type="password" placeholder="请输入原密码" />
        </label>
        <label class="field">
          <span>新密码</span>
          <input v-model="pwd.next" type="password" placeholder="不少于 6 位" />
        </label>
        <label class="field">
          <span>确认新密码</span>
          <input v-model="pwd.confirm" type="password" placeholder="再次输入新密码" />
        </label>
        <button class="primary-btn" :disabled="pwdLoading" @click="onSubmitPwd">
          {{ pwdLoading ? '提交中…' : '提交' }}
        </button>
      </div>
    </div>

    <!-- Preview bottom sheet -->
    <PreviewSheet :file="previewFile" @close="closePreview" />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, nextTick, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import MarkdownIt from 'markdown-it'
import { useMobileChat } from '../stores/chat'
import { useMobileAuth } from '../stores/auth'
import { api } from '../api'
import { showToast } from '../toast'
import PreviewSheet from '../components/PreviewSheet.vue'
import MobileChatHeader from '../components/MobileChatHeader.vue'
import MobileNavDrawer from '../components/MobileNavDrawer.vue'
import MobileAgentSheet from '../components/MobileAgentSheet.vue'
import MobileUserSheet from '../components/MobileUserSheet.vue'
import MobileComposer from '../components/MobileComposer.vue'
import MessageDispatcher from '@/agent-ui/engine/MessageDispatcher.vue'
import { resolveToolMeta } from '@/lib/toolDisplay'

const md = new MarkdownIt({ breaks: true, linkify: true })
const chat = useMobileChat()
const auth = useMobileAuth()
const router = useRouter()
const route = useRoute()

const input = ref('')
const sending = ref(false)
const streamAbortController = ref<AbortController | null>(null)
function stopStream() { streamAbortController.value?.abort() }

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

/** Same parser as desktop Chat.vue: split agent description into intro lines
 *  and starter questions (lines starting with '- ', '• ', '* ' or '1.'). */
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

// 数字员工头像渐变
import { normalizeTrace, plainTextFromMarkdown, PREVIEWABLE, agentGradient } from '@/shared/constants'

// 数字员工首字母
function agentInitial(agent: any) {
  return (agent?.name || '').charAt(0)
}

// 选择数字员工
function selectAgent(agent: any) {
  chat.currentAgent = agent
  agentSheetOpen.value = false
}

function useStarter(q: string) {
  if (!q || sending.value || !chat.currentAgent) return
  input.value = q
  send()
}
const scrollRef = ref<HTMLElement | null>(null)

const drawerOpen = ref(false)
const agentSheetOpen = ref(false)
const userSheetOpen = ref(false)
const convActionTarget = ref<any | null>(null)
const changePasswordOpen = ref(false)
const pwdLoading = ref(false)
const pwd = reactive({ old: '', next: '', confirm: '' })

const previewFile = ref<any | null>(null)

const unreadCount = ref(0)
let unreadTimer: any = null

async function refreshUnread() {
  try {
    const r = await api.notifications({ unread: 1, limit: 1 })
    unreadCount.value = r.unread || 0
  } catch {}
}

function goRoute(p: string) {
  drawerOpen.value = false
  router.push(p)
}

onMounted(async () => {
  if (!chat.loaded) await chat.loadInit()
  // Deep-link: ?conv=N opens an existing conversation (e.g. from a task run)
  const convQ = route.query.conv
  const convId = Array.isArray(convQ) ? Number(convQ[0]) : Number(convQ)
  if (convId && !Number.isNaN(convId) && convId !== chat.currentConvId) {
    let conv: any = chat.convs.find((c: any) => c.id === convId)
    if (!conv) conv = { id: convId }
    try { await chat.selectConv(conv) } catch {}
  }
  if (chat.messages.length) loadFavoritesForMessages(chat.messages)
  await scrollBottom()
  await refreshUnread()
  unreadTimer = setInterval(refreshUnread, 60_000)
})
onBeforeUnmount(() => {
  if (unreadTimer) clearInterval(unreadTimer)
})

watch(() => chat.currentConvId, async () => { await scrollBottom() })

function triggerUpload() {
  if (!chat.currentAgent) {
    showToast('请先选择数字员工')
    return
  }
  // MobileComposer 组件会处理文件上传
}

async function onFilePick(e: Event) {
  const inputEl = e.target as HTMLInputElement
  const files = Array.from(inputEl.files || [])
  inputEl.value = ''
  if (!files.length) return
  if (!chat.currentConvId) await chat.ensureConv()
  for (const file of files) {
    try {
      const r = await api.uploadFile(file, chat.currentConvId!)
      chat.pendingFiles.push(r)
      pollFileStatus(r.id)
    } catch {}
  }
}

function pollFileStatus(fileId: number) {
  const tick = async () => {
    const idx = chat.pendingFiles.findIndex((x: any) => x.id === fileId)
    if (idx === -1) return
    try {
      const fresh = await api.getFile(fileId)
      chat.pendingFiles[idx] = { ...chat.pendingFiles[idx], ...fresh }
      if (fresh.parse_status === 'parsing') setTimeout(tick, 1500)
    } catch {}
  }
  setTimeout(tick, 800)
}

async function removeFile(f: any) {
  chat.pendingFiles = chat.pendingFiles.filter((x: any) => x.id !== f.id)
  try { await api.deleteFile(f.id) } catch {}
}


function canPreview(f: any) {
  if (!f) return false
  const e = (f.ext || (f.name || '').split('.').pop() || '').toLowerCase().replace(/^\./, '')
  return PREVIEWABLE.has(e)
}

function openPreview(f: any) {
  const url = f.download_url || (f.id ? `/api/files/${f.id}/raw` : '')
  if (!url) {
    showToast('无可预览资源')
    return
  }
  previewFile.value = { ...f, download_url: url }
}

function closePreview() { previewFile.value = null }

function formatSize(n: number) {
  if (!n) return ''
  if (n < 1024) return n + ' B'
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + ' KB'
  return (n / 1024 / 1024).toFixed(1) + ' MB'
}

function formatJson(v: any) {
  if (v == null) return ''
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

function isWaiting(m: any): boolean {
  if (m.role !== 'assistant' || !m._streaming) return false
  if (m.content_json?.text) return false
  if (m._thinking) return false
  if (m._steps?.length) return false
  if (m._files?.length) return false
  if (m._uis?.length) return false
  return true
}

async function scrollBottom() {
  await nextTick()
  const el = scrollRef.value
  if (!el) return
  const threshold = 120
  if (el.scrollHeight - el.scrollTop - el.clientHeight > threshold) return
  el.scrollTop = el.scrollHeight
}

function onNewConv() {
  chat.newConv()
}

function onNewConvFromDrawer() {
  chat.newConv()
  drawerOpen.value = false
}

async function onSelectConv(c: any) {
  try {
    await chat.selectConv(c)
    drawerOpen.value = false
    await scrollBottom()
    loadFavoritesForMessages(chat.messages)
  } catch {}
}

function onPickAgent(a: any) {
  chat.selectAgent(a)
  agentSheetOpen.value = false
}

function onConvActions(c: any) {
  convActionTarget.value = c
}

async function onRenameConv() {
  const c = convActionTarget.value
  if (!c) return
  const next = window.prompt('输入新标题', c.title || '')
  if (!next) { convActionTarget.value = null; return }
  try {
    await chat.renameConv(c, next.trim())
    showToast('已重命名', 'success')
  } catch {}
  convActionTarget.value = null
}

async function onDeleteConv() {
  const c = convActionTarget.value
  if (!c) return
  if (!window.confirm('确定删除该对话？')) { convActionTarget.value = null; return }
  try {
    await chat.deleteConv(c)
    showToast('已删除', 'success')
  } catch {}
  convActionTarget.value = null
}

function onChangePassword() {
  userSheetOpen.value = false
  pwd.old = ''; pwd.next = ''; pwd.confirm = ''
  changePasswordOpen.value = true
}

async function onSubmitPwd() {
  if (!pwd.old || !pwd.next || !pwd.confirm) {
    showToast('请填写完整')
    return
  }
  if (pwd.next.length < 6) {
    showToast('新密码至少 6 位')
    return
  }
  if (pwd.next !== pwd.confirm) {
    showToast('两次新密码不一致')
    return
  }
  pwdLoading.value = true
  try {
    await api.changePassword(pwd.old, pwd.next)
    showToast('密码已更新，请重新登录', 'success')
    changePasswordOpen.value = false
    auth.logout()
    chat.reset()
    setTimeout(() => router.replace('/login'), 600)
  } catch {} finally {
    pwdLoading.value = false
  }
}

function onLogout() {
  if (!window.confirm('确定退出登录？')) return
  auth.logout()
  chat.reset()
  router.replace('/login')
}

// UI Schema → Agent. Carries [UI_ACTION] (call tool, skip LLM) or [UI_MSG]
// (run LLM with synthetic user text, hidden from transcript). No local user bubble.
async function onAgentCall(text: string) {
  if (!chat.currentAgent || sending.value) return
  if (!chat.currentConvId) await chat.ensureConv()

  const placeholder: any = reactive({
    _tmp: Date.now(), role: 'assistant',
    content_json: { text: '' }, tool_calls_json: null,
    _meta: null, _thinking: '', _steps: [], _stepIndex: {} as Record<string, number>,
    _files: [], _uis: [], _streaming: true,
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
        try { applyEvent(placeholder, JSON.parse(line.slice(5).trim())) } catch {}
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

async function send() {
  if (!chat.currentAgent || !input.value.trim()) return
  const policy = chat.currentAgent?.upload_policy_json || {}
  const maxPerSend = Number(policy.max_files_per_send || 0)
  if (maxPerSend > 0 && chat.pendingFiles.length > maxPerSend) {
    showToast(`单次最多 ${maxPerSend} 个文件`)
    return
  }
  const stillParsing = chat.pendingFiles.filter((f: any) => f.parse_status === 'parsing')
  if (stillParsing.length) {
    showToast(`还有 ${stillParsing.length} 个文件解析中`)
    return
  }
  const isFirst = chat.messages.length === 0
  if (!chat.currentConvId) await chat.ensureConv()
  const text = input.value.trim()
  const fileIds = chat.pendingFiles.map((f) => f.id)
  const fileBriefs = chat.pendingFiles.map((f: any) => ({
    id: f.id, name: f.name, size: f.size, parse_status: f.parse_status, parsed_chars: f.parsed_chars,
  }))

  chat.messages.push({ _tmp: Date.now(), role: 'user', content_json: { text, files: fileBriefs } })
  chat.messages.push({
    _tmp: Date.now() + 1, role: 'assistant',
    content_json: { text: '' }, tool_calls_json: null,
    _meta: null, _thinking: '', _steps: [], _stepIndex: {} as Record<string, number>,
    _files: [], _uis: [], _streaming: true,
  })
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

  if (isFirst && chat.currentConvId) {
    const conv = chat.convs.find((c) => c.id === chat.currentConvId)
    if (conv) {
      const title = text.replace(/\s+/g, ' ').trim().slice(0, 30)
      if (title && title !== conv.title) {
        chat.renameConv(conv, title).catch(() => {})
      }
    }
  }
}

// -------- Copy + Favorite --------
const favByMessage = ref<Record<number, number>>({}) // message_id → favorite_id

async function loadFavoritesForMessages(messages: any[]) {
  const ids = messages.filter((m) => m.role === 'assistant' && m.id > 0).map((m) => m.id)
  if (!ids.length) return
  try {
    const map = await api.checkFavorites(ids)
    favByMessage.value = map || {}
  } catch {}
}

function isFavorited(m: any): boolean {
  if (!m?.id) return false
  return !!favByMessage.value[m.id]
}

async function copyAnswer(m: any) {
  const mid = m.id || m._tmp
  if (mid) {
    const el = document.querySelector(`.msg[data-mid="${mid}"] .bubble-stack`)
    if (el) {
      try {
        const plain = el.textContent || ''
        await navigator.clipboard.writeText(plain)
        showToast('已复制', 'success')
        return
      } catch {}
    }
  }
  const text = m.content_json?.text || ''
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    showToast('已复制', 'success')
  } catch {
    try {
      const ta = document.createElement('textarea')
      ta.value = text
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      ta.remove()
      showToast('已复制', 'success')
    } catch { showToast('复制失败', 'error') }
  }
}

async function toggleFavorite(m: any) {
  if (!m?.id) {
    showToast('消息还未保存，稍后再试')
    return
  }
  if (isFavorited(m)) {
    try {
      await api.deleteFavoriteByMessage(m.id)
      const next = { ...favByMessage.value }
      delete next[m.id]
      favByMessage.value = next
      showToast('已取消收藏', 'success')
    } catch (e: any) {
      showToast('操作失败')
    }
  } else {
    try {
      const fav = await api.createFavorite(m.id)
      favByMessage.value = { ...favByMessage.value, [m.id]: fav.id }
      showToast('已加入空间', 'success')
    } catch (e: any) {
      showToast('操作失败')
    }
  }
}

function applyEvent(m: any, ev: { type: string; data: any }) {
  const { type, data } = ev
  if (type === 'meta') m._meta = data
  else if (type === 'text') m.content_json.text += data.text || ''
  else if (type === 'thinking') { m._thinking += data.text || ''; scrollThinkingToBottom(m) }
  else if (type === 'tool_use') {
    const id = data.id || data.name
    const existingIdx = m._stepIndex[id]
    if (existingIdx != null) {
      const s = m._steps[existingIdx]
      if (data.input && (typeof data.input !== 'object' || Object.keys(data.input).length)) s.input = data.input
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
    m._files = Array.isArray(m._files) ? [...m._files, data] : [data]
  } else if (type === 'ui') {
    m._uis = Array.isArray(m._uis) ? [...m._uis, data] : [data]
  } else if (type === 'error') {
    m.content_json.text += `\n\n[错误] ${data.message}`
  }
}
</script>

<style scoped>
.chat-page { background: var(--m-bg); }

.messages {
  flex: 1; overflow: auto;
  padding: 8px 14px 8px;
  -webkit-overflow-scrolling: touch;
}

.welcome {
  height: 100%;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  text-align: center; color: var(--m-text-secondary);
  padding: 40px 24px;
}
.welcome-brand-row {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 20px;
}
.welcome-logo {
  width: 64px; height: 64px;
  border-radius: 14px;
  object-fit: cover; object-position: center 35%;
  box-shadow: 0 4px 16px rgba(0,0,0,.08);
  background: var(--m-surface);
  flex-shrink: 0;
}
.welcome-brand-text { display: flex; flex-direction: column; gap: 2px; text-align: left; }

/* 欢迎页 — 数字员工品牌 */
.welcome-brand {
  font-size: 20px !important;
  font-weight: 700 !important;
  color: var(--m-text) !important;
  margin: 0 !important;
}
.welcome-subtitle {
  font-size: 12px;
  color: var(--m-text-tertiary);
  margin: 0;
}

/* 数字员工展示区 */
.welcome-workers {
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
  margin: 0 0 20px 0;
  padding: 0 8px;
}
.worker-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px;
  border-radius: 12px;
  border: 1px solid var(--m-border);
  background: var(--m-surface);
  cursor: pointer;
  transition: all 0.2s;
  min-width: 80px;
}
.worker-card:hover, .worker-card.active {
  border-color: var(--m-primary);
  background: var(--m-primary-soft);
}
.worker-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 6px;
}
.worker-avatar img {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  object-fit: cover;
}
.worker-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--m-text);
}
.welcome-intro-section {
  text-align: center;
  margin-bottom: 12px;
}
.welcome-desc {
  font-size: 13px;
  color: var(--m-text-secondary);
  margin-top: 4px;
  padding: 0 16px;
}

/* 呼吸灯动画 */
@keyframes worker-breathe {
  0%, 100% { box-shadow: 0 0 0 0 rgba(30, 142, 62, 0.4); }
  50% { box-shadow: 0 0 0 4px rgba(30, 142, 62, 0); }
}
.worker-card.active .worker-avatar {
  animation: worker-breathe 2s ease-in-out infinite;
}

.welcome h2 { margin: 6px 0 4px; font-size: 20px; color: var(--m-text); font-weight: 600; }
.welcome p { margin: 0; font-size: 16px; }
.welcome-intro {
  margin: 0; padding: 0 16px;
  max-width: 100%;
  color: var(--m-text-secondary, #5f6368);
  line-height: 1.6;
  font-size: 16px;
}
.welcome-starters {
  margin-top: 14px;
  padding: 0 16px;
  display: flex; flex-direction: column; gap: 8px;
  align-items: stretch;
  width: 100%; max-width: 480px;
}
.starter-chip {
  appearance: none;
  width: 100%;
  text-align: left;
  font-size: 16px; line-height: 1.5;
  padding: 10px 14px;
  border: 1px solid var(--m-border, #e8eaed);
  border-radius: 12px;
  background: var(--m-surface);
  color: var(--m-text);
  -webkit-tap-highlight-color: transparent;
  transition: background .15s, border-color .15s, transform .1s;
  box-shadow: 0 1px 2px rgba(60,64,67,.04);
}
.starter-chip:active:not(:disabled) {
  transform: scale(.99);
  background: var(--m-bg-soft);
  border-color: var(--m-primary-hover);
}
.starter-chip:disabled { opacity: .55; }

.msg { display: flex; margin: 10px 0; }
.msg.user { justify-content: flex-end; }
.msg.assistant { justify-content: flex-start; }
.bubble-stack {
  display: flex; flex-direction: column; gap: 6px;
  max-width: 100%; min-width: 0;
}
.msg.user .bubble-stack { align-items: flex-end; }

.thinking-pill {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 7px 12px;
  background: var(--m-bg-soft);
  border-radius: var(--m-radius-pill);
  font-size: 16px;
  color: var(--m-text-secondary);
  align-self: flex-start;
}
.thinking-dots { display: inline-flex; gap: 3px; }
.thinking-dots span {
  width: 4px; height: 4px; border-radius: 50%; background: currentColor;
  animation: dot-bounce 1.2s ease-in-out infinite;
}
.thinking-dots span:nth-child(2) { animation-delay: .15s; }
.thinking-dots span:nth-child(3) { animation-delay: .3s; }
@keyframes dot-bounce {
  0%, 80%, 100% { opacity: .3; transform: translateY(0); }
  40% { opacity: 1; transform: translateY(-3px); }
}

.thinking-card {
  border: none;
  border-radius: var(--m-radius);
  background: var(--m-bg-soft);
  font-size: 14px;
}
.thinking-card summary {
  list-style: none; cursor: pointer;
  padding: 8px 12px;
  color: var(--m-text-secondary); font-weight: 500;
}
.thinking-card summary::-webkit-details-marker { display: none; }
.thinking-body {
  position: relative;
}
.thinking-body::before,
.thinking-body::after {
  content: '';
  position: absolute;
  left: 0; right: 0;
  height: 24px;
  pointer-events: none;
  z-index: 1;
}
.thinking-body::before {
  top: 0;
  background: linear-gradient(to bottom, var(--m-bg-soft) 0%, transparent 100%);
}
.thinking-body::after {
  bottom: 0;
  background: linear-gradient(to top, var(--m-bg-soft) 0%, transparent 100%);
}
.thinking-content {
  max-height: 180px;
  overflow-y: auto;
  padding: 8px 12px; white-space: pre-wrap; word-break: break-word;
  color: var(--m-text-secondary); line-height: 1.6;
  scrollbar-width: thin;
  scrollbar-color: var(--m-border-strong) transparent;
}
.thinking-content::-webkit-scrollbar { width: 3px; }
.thinking-content::-webkit-scrollbar-track { background: transparent; }
.thinking-content::-webkit-scrollbar-thumb {
  background: var(--m-border-strong);
  border-radius: 2px;
}

.step-list { display: flex; flex-direction: column; gap: 5px; }
.step-card {
  border: none;
  border-radius: var(--m-radius);
  background: var(--m-bg-soft);
  padding: 0;
  font-size: 14px;
}
.step-card.running { background: var(--m-primary-soft); }
.step-head {
  display: flex; align-items: center; gap: 6px; justify-content: space-between;
  padding: 8px 10px;
  cursor: pointer;
  list-style: none;
  user-select: none;
}
.step-head::-webkit-details-marker { display: none; }
.step-kind {
  text-transform: uppercase; font-size: 14px; font-weight: 700;
  background: var(--m-surface); padding: 1px 6px; border-radius: 4px;
  color: var(--m-text-secondary);
  flex-shrink: 0;
}
.step-card.running .step-kind { background: var(--m-primary); color: #fff; }
.step-name {
  font-size: 14px; color: var(--m-text);
  flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.step-server {
  font-size: 11px; color: var(--m-text-secondary);
  background: var(--m-surface); padding: 1px 5px; border-radius: 3px;
  flex-shrink: 0; font-style: italic;
}
.step-raw-name { font-family: ui-monospace, Menlo, monospace; font-size: 11px; color: var(--m-text-secondary); word-break: break-all; }
.step-id-row { display: flex; align-items: center; gap: 6px; padding: 6px 0 2px; }
.step-dur { font-size: 14px; color: var(--m-text-tertiary); flex-shrink: 0; }

.step-io-toggle {
  display: inline-flex; align-items: center; gap: 3px;
  color: var(--m-primary); font-size: 14px; font-weight: 500;
  flex-shrink: 0; white-space: nowrap;
}
.step-chevron {
  color: var(--m-text-secondary);
  transition: transform .2s ease;
}
.step-card[open] .step-chevron { transform: rotate(180deg); color: var(--m-primary); }

.step-body {
  padding: 0 10px 8px 10px;
  border-top: 1px solid color-mix(in srgb, var(--m-border) 50%, transparent);
  background: color-mix(in srgb, var(--m-bg-soft) 70%, var(--m-surface));
}
.step-block { margin-top: 6px; }
.step-block:first-child { margin-top: 0; }
.step-label { font-size: 14px; font-weight: 600; color: var(--m-text-secondary); text-transform: uppercase; letter-spacing: .06em; margin-bottom: 3px; }
.step-block pre {
  margin: 0; padding: 6px 8px; background: var(--m-bg-soft);
  border-radius: 4px; font-size: 14px; font-family: ui-monospace, Menlo, monospace;
  overflow: auto; max-height: 160px; white-space: pre-wrap; word-break: break-word;
}

.files-block { display: flex; flex-direction: column; gap: 6px; }
.file-card {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 14px;
  background: var(--m-surface);
  border: none;
  border-radius: 14px;
  box-shadow: var(--m-shadow-1);
}
.file-card.clickable:active { transform: scale(.99); background: var(--m-bg-soft); }
.file-icon {
  width: 36px; height: 36px; border-radius: 10px;
  background: var(--m-primary-soft); color: var(--m-primary);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.file-meta { flex: 1; min-width: 0; }
.file-name {
  font-size: 16px; color: var(--m-text); font-weight: 500;
  max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.file-sub { font-size: 14px; color: var(--m-text-secondary); margin-top: 2px; }
.file-preview-hint { color: var(--m-primary); margin-left: 4px; }

.ui-block { display: flex; flex-direction: column; gap: 8px; }
.ui-block :deep(.ui-surface) {
  background: var(--m-surface);
  border: none;
  border-radius: 14px;
  padding: 14px;
  box-shadow: var(--m-shadow-1);
}

.bubble {
  padding: 10px 14px;
  background: var(--m-surface);
  border-radius: 16px;
  font-size: 16px;
  line-height: 1.6;
  word-break: break-word;
  box-shadow: var(--m-shadow-1);
}
.msg.user .bubble {
  background: var(--m-primary); color: #fff;
  border-radius: 16px 6px 16px 16px;
  box-shadow: 0 1px 2px rgba(66,133,244,.25);
}
.bubble--clamped { max-height: 200px; overflow: hidden; position: relative; }
.bubble-clamp-fade {
  position: absolute; bottom: 0; left: 0; right: 0; height: 56px;
  background: linear-gradient(to bottom, transparent, var(--m-primary));
  pointer-events: none;
  border-radius: 0 0 16px 6px;
}
.bubble-expand-btn {
  display: inline-flex; align-items: center; gap: 3px;
  align-self: flex-end;
  padding: 2px 8px; margin-top: 2px;
  font-size: 13px; color: var(--m-primary);
  background: transparent; border: none;
  cursor: pointer; opacity: .75;
  transition: opacity .15s;
}
.bubble-expand-btn:hover { opacity: 1; }
.bubble-expand-chevron { transition: transform .2s ease; }
.bubble-expand-chevron.rotated { transform: rotate(180deg); }
.msg.assistant .bubble { border-radius: 6px 16px 16px 16px; }
.bubble :deep(p) { margin: 4px 0; }
.bubble :deep(p:first-child) { margin-top: 0; }
.bubble :deep(p:last-child) { margin-bottom: 0; }
.bubble :deep(pre) {
  background: var(--m-bg-soft); color: var(--m-text);
  padding: 10px 12px; border-radius: 8px;
  overflow: auto; max-height: 320px;
  font-size: 14px; line-height: 1.5;
  margin: 6px 0;
  font-family: ui-monospace, Menlo, monospace;
}
.bubble :deep(:not(pre) > code) {
  background: var(--m-bg-soft); color: var(--m-danger);
  padding: 1px 5px; border-radius: 4px; font-size: 14px;
}
.msg.user .bubble :deep(:not(pre) > code) { background: rgba(255,255,255,.18); color: #fff; }

.msg-files { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px; }
.msg-file-chip {
  display: inline-flex; align-items: center;
  padding: 2px 8px;
  background: rgba(255,255,255,.18);
  border-radius: var(--m-radius-pill);
  font-size: 14px;
}
.msg-file-chip.clickable { cursor: pointer; }
.msg.assistant .msg-file-chip { background: var(--m-surface-variant); color: var(--m-text-secondary); }

/* Change password fields */
.pwd-body { padding: 12px 16px 24px; display: flex; flex-direction: column; gap: 14px; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field span { font-size: 16px; color: var(--m-text-secondary); padding-left: 2px; }
.field input {
  height: 44px; padding: 0 14px;
  border: none;
  background: var(--m-bg-soft);
  border-radius: 12px;
  font-size: 16px; outline: none;
}
.field input:focus { background: var(--m-surface); box-shadow: 0 0 0 2px var(--m-primary); }

.primary-btn {
  height: 46px; margin-top: 6px;
  background: var(--m-primary); color: #fff;
  border-radius: 12px; font-size: 16px; font-weight: 500;
  display: flex; align-items: center; justify-content: center;
}
.primary-btn:active { background: var(--m-primary-hover); }
.primary-btn:disabled { background: var(--m-border-strong); }

/* Message action bar: copy + favorite */
.msg-actions {
  display: flex;
  gap: 6px;
  padding: 2px 0;
  align-self: flex-start;
}
.msg-action {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  border-radius: 20px;
  font-size: 14px;
  color: var(--m-text-secondary);
  background: var(--m-bg-soft);
  border: 1px solid var(--m-border);
  -webkit-tap-highlight-color: transparent;
  transition: background .15s, color .15s;
}
.msg-action:active { background: var(--m-surface-variant); }
.msg-action.active { color: var(--m-primary); border-color: var(--m-primary); }
</style>
