<template>
  <div class="mb-page chat-page">
    <header class="mb-header soft">
      <button class="mb-icon-btn" @click="drawerOpen = true" aria-label="菜单">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
      </button>
      <div class="mb-header-title" @click="agentSheetOpen = true">
        <span class="name">{{ chat.currentAgent?.name || '选择智能体' }}</span>
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
      </div>
      <button class="mb-icon-btn" @click="onNewConv" aria-label="新建对话">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12h14"/></svg>
      </button>
    </header>

    <div ref="scrollRef" class="messages">
      <div v-if="!chat.currentConvId || chat.messages.length === 0" class="welcome">
        <div class="welcome-mark">
          <span class="dot d1" /><span class="dot d2" /><span class="dot d3" /><span class="dot d4" />
        </div>
        <h2 v-if="chat.currentAgent">你好，我是 {{ chat.currentAgent.name }}</h2>
        <h2 v-else>暂无可用智能体</h2>
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
        <p v-else>请联系管理员授权</p>
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
              <span>{{ m._meta ? '正在思考' : '正在连接智能体' }}</span>
              <span class="thinking-dots"><span/><span/><span/></span>
            </div>

            <details v-if="m.content_json?.thinking || m._thinking" class="thinking-card">
              <summary>思考过程</summary>
              <div class="thinking-content">{{ m.content_json?.thinking || m._thinking }}</div>
            </details>

            <div v-if="m._steps?.length || m.tool_calls_json?.trace?.length" class="step-list">
              <div v-for="(s, i) in (m._steps || normalizeTrace(m.tool_calls_json?.trace))" :key="i" :class="['step-card', s.status]">
                <div class="step-head">
                  <span class="step-kind">{{ s.kind }}</span>
                  <span class="step-name">{{ s.name }}</span>
                  <span v-if="s.duration_ms" class="step-dur">{{ s.duration_ms }}ms</span>
                </div>
              </div>
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

            <div v-if="m.content_json?.text || m.role === 'user'" class="bubble">
              <div v-if="m.role === 'user' && m.content_json?.files?.length" class="msg-files">
                <span
                  v-for="(f, fi) in m.content_json.files"
                  :key="fi"
                  :class="['msg-file-chip', { clickable: canPreview(f) }]"
                  @click="canPreview(f) && openPreview(f)"
                >📎 {{ f.name }}</span>
              </div>
              <div class="bubble-content" v-html="md.render(m.content_json?.text || '')"></div>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- Composer -->
    <div class="composer-wrap">
      <div v-if="chat.pendingFiles.length" class="files-row">
        <div v-for="f in chat.pendingFiles" :key="f.id" :class="['file-chip', f.parse_status]">
          <span class="chip-name">{{ f.name }}</span>
          <span v-if="f.parse_status === 'parsing'" class="chip-meta">解析中…</span>
          <span v-else-if="f.parse_status === 'done'" class="chip-meta">{{ f.parsed_chars }} 字</span>
          <span v-else-if="f.parse_status === 'failed'" class="chip-meta err">解析失败</span>
          <button class="chip-close" @click="removeFile(f)" aria-label="移除">×</button>
        </div>
      </div>
      <div class="composer">
        <button class="icon-btn" :disabled="!chat.currentAgent" @click="triggerUpload" aria-label="上传文件">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>
        </button>
        <input ref="fileInput" type="file" multiple style="display:none" @change="onFilePick" />
        <textarea
          v-model="input"
          ref="textareaRef"
          rows="1"
          :placeholder="chat.currentAgent ? '发送消息…' : '请联系管理员授权智能体'"
          :disabled="sending || !chat.currentAgent"
          @input="autoResize"
          @keydown.enter.exact.prevent="send"
        />
        <button class="send-btn" :disabled="sending || !input.trim() || !chat.currentAgent" @click="send" aria-label="发送">
          <svg v-if="!sending" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
          <span v-else class="spinner" />
        </button>
      </div>
    </div>

    <!-- Sidebar drawer: brand top, new+history middle, user footer -->
    <div :class="['mb-drawer-mask', { open: drawerOpen }]" @click="drawerOpen = false" />
    <aside :class="['mb-drawer', { open: drawerOpen }]">
      <div class="drawer-brand">
        <div class="brand-mark">
          <span class="dot d1" /><span class="dot d2" />
          <span class="dot d3" /><span class="dot d4" />
        </div>
        <div class="brand-text">
          <div class="brand-name">Agent Forge</div>
          <div class="brand-sub">智能体助手</div>
        </div>
      </div>

      <button class="conv-new" @click="onNewConvFromDrawer">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12h14"/></svg>
        <span>新建对话</span>
      </button>

      <div class="drawer-nav">
        <button class="nav-item" @click="goRoute('/tasks')">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          <span>任务</span>
        </button>
        <button class="nav-item" @click="goRoute('/space')">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
          <span>空间</span>
        </button>
        <button class="nav-item" @click="goRoute('/notifications')">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
          <span>通知</span>
          <span v-if="unreadCount > 0" class="badge">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
        </button>
      </div>

      <div class="drawer-section-label">最近对话</div>
      <div class="drawer-list">
        <div v-if="!chat.convs.length" class="empty">暂无历史对话</div>
        <div
          v-for="c in chat.convs"
          :key="c.id"
          :class="['conv-item', { active: c.id === chat.currentConvId }]"
          @click="onSelectConv(c)"
        >
          <svg class="conv-icon" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
          <div class="conv-name">{{ c.title || '未命名' }}</div>
          <button class="conv-action" @click.stop="onConvActions(c)" aria-label="更多">⋯</button>
        </div>
      </div>

      <div class="drawer-footer" @click="userSheetOpen = true">
        <div class="user-avatar">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
        </div>
        <div class="user-info">
          <div class="user-name">{{ auth.user?.display_name || auth.user?.username || '-' }}</div>
          <div class="user-role">{{ auth.user?.role?.name || '' }}</div>
        </div>
        <button class="user-settings" aria-label="设置">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h0a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51h0a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v0a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
        </button>
      </div>
    </aside>

    <!-- Agent bottom sheet -->
    <div :class="['mb-drawer-mask', { open: agentSheetOpen }]" @click="agentSheetOpen = false" />
    <div :class="['mb-sheet', { open: agentSheetOpen }]">
      <div class="mb-sheet-handle" />
      <div class="mb-sheet-title">选择智能体</div>
      <div class="mb-sheet-body">
        <div v-if="!chat.agents.length" class="empty">暂无可用智能体</div>
        <div
          v-for="a in chat.agents" :key="a.id"
          :class="['agent-item', { active: a.id === chat.currentAgent?.id }]"
          @click="onPickAgent(a)"
        >
          <div class="agent-avatar">{{ (a.name || '?').slice(0, 1) }}</div>
          <div class="agent-text">
            <div class="agent-name">{{ a.name }}</div>
            <div v-if="a.description" class="agent-desc">{{ a.description }}</div>
          </div>
          <svg v-if="a.id === chat.currentAgent?.id" class="check" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
        </div>
      </div>
    </div>

    <!-- User settings sheet (from drawer footer) -->
    <div :class="['mb-drawer-mask', { open: userSheetOpen }]" @click="userSheetOpen = false" />
    <div :class="['mb-sheet', { open: userSheetOpen }]">
      <div class="mb-sheet-handle" />
      <div class="mb-sheet-title">{{ auth.user?.display_name || auth.user?.username || '我' }}</div>
      <div class="mb-sheet-body">
        <div class="action-item" @click="onChangePassword">修改密码</div>
        <div class="action-item danger" @click="onLogout">退出登录</div>
        <div class="action-item cancel" @click="userSheetOpen = false">取消</div>
      </div>
    </div>

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
import MessageDispatcher from '@/agent-ui/engine/MessageDispatcher.vue'

const md = new MarkdownIt({ breaks: true, linkify: true })
const chat = useMobileChat()
const auth = useMobileAuth()
const router = useRouter()
const route = useRoute()

const input = ref('')
const sending = ref(false)

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

function useStarter(q: string) {
  if (!q || sending.value || !chat.currentAgent) return
  input.value = q
  send()
}
const scrollRef = ref<HTMLElement | null>(null)
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)

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
  await scrollBottom()
  await refreshUnread()
  unreadTimer = setInterval(refreshUnread, 60_000)
})
onBeforeUnmount(() => {
  if (unreadTimer) clearInterval(unreadTimer)
})

watch(() => chat.currentConvId, async () => { await scrollBottom() })

function autoResize() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 140) + 'px'
}

function triggerUpload() {
  if (!chat.currentAgent) {
    showToast('请先选择智能体')
    return
  }
  fileInput.value?.click()
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

const PREVIEWABLE = new Set(['html','htm','pdf','md','markdown','txt','log','json','csv','xml','js','ts','css','py','sql','yml','yaml','sh','svg','png','jpg','jpeg','gif','webp','bmp'])
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
      steps.push({
        kind: data.name?.startsWith('mcp_') ? 'mcp' : 'tool',
        name: data.name || '(tool)',
        input: data.input,
        output: undefined,
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
  if (el) el.scrollTop = el.scrollHeight
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
  try {
    const resp = await fetch(`/api/conversations/${chat.currentConvId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ content: text, file_ids: [] }),
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
    placeholder.content_json.text += `\n\n[网络错误] ${e.message}`
  } finally {
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
  if (textareaRef.value) textareaRef.value.style.height = 'auto'
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

function applyEvent(m: any, ev: { type: string; data: any }) {
  const { type, data } = ev
  if (type === 'meta') m._meta = data
  else if (type === 'text') m.content_json.text += data.text || ''
  else if (type === 'thinking') m._thinking += data.text || ''
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

/* Soft header — no bottom border */
.mb-header.soft { background: var(--m-bg); border-bottom: none; }

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
.welcome-mark {
  display: grid; grid-template-columns: 1fr 1fr; gap: 6px;
  width: 44px; height: 44px; margin-bottom: 14px;
}
.welcome-mark .dot { border-radius: 50%; }
.d1 { background:#4285f4 } .d2 { background:#ea4335 }
.d3 { background:#fbbc04 } .d4 { background:#34a853 }
.welcome h2 { margin: 6px 0 4px; font-size: 18px; color: var(--m-text); font-weight: 600; }
.welcome p { margin: 0; font-size: 13px; }
.welcome-intro {
  margin: 0; padding: 0 16px;
  max-width: 100%;
  color: var(--m-text-secondary, #5f6368);
  line-height: 1.6;
  font-size: 13px;
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
  font-size: 13px; line-height: 1.5;
  padding: 10px 14px;
  border: 1px solid var(--m-border, #e8eaed);
  border-radius: 12px;
  background: #ffffff;
  color: var(--m-text, #202124);
  -webkit-tap-highlight-color: transparent;
  transition: background .15s, border-color .15s, transform .1s;
  box-shadow: 0 1px 2px rgba(60,64,67,.04);
}
.starter-chip:active:not(:disabled) {
  transform: scale(.99);
  background: #f8f9fa;
  border-color: #aecbfa;
}
.starter-chip:disabled { opacity: .55; }

.msg { display: flex; margin: 10px 0; }
.msg.user { justify-content: flex-end; }
.msg.assistant { justify-content: flex-start; }
.bubble-stack {
  display: flex; flex-direction: column; gap: 6px;
  max-width: 88%; min-width: 0;
}
.msg.user .bubble-stack { align-items: flex-end; }

.thinking-pill {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 7px 12px;
  background: var(--m-bg-soft);
  border-radius: var(--m-radius-pill);
  font-size: 13px;
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
  font-size: 12.5px;
}
.thinking-card summary {
  list-style: none; cursor: pointer;
  padding: 8px 12px;
  color: var(--m-text-secondary); font-weight: 500;
}
.thinking-card summary::-webkit-details-marker { display: none; }
.thinking-content {
  padding: 0 12px 10px; white-space: pre-wrap; word-break: break-word;
  color: var(--m-text-secondary); line-height: 1.6;
}

.step-list { display: flex; flex-direction: column; gap: 5px; }
.step-card {
  border: none;
  border-radius: var(--m-radius);
  background: var(--m-bg-soft);
  padding: 8px 10px;
  font-size: 12px;
}
.step-card.running { background: var(--m-primary-soft); }
.step-head { display: flex; align-items: center; gap: 6px; }
.step-kind {
  text-transform: uppercase; font-size: 10px; font-weight: 700;
  background: var(--m-surface); padding: 1px 6px; border-radius: 4px;
  color: var(--m-text-secondary);
}
.step-card.running .step-kind { background: var(--m-primary); color: #fff; }
.step-name {
  font-family: ui-monospace, Menlo, monospace; font-size: 11.5px; color: var(--m-text);
  flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.step-dur { font-size: 10.5px; color: var(--m-text-tertiary); }

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
  font-size: 13.5px; color: var(--m-text); font-weight: 500;
  max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.file-sub { font-size: 11.5px; color: var(--m-text-secondary); margin-top: 2px; }
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
  font-size: 14.5px;
  line-height: 1.6;
  word-break: break-word;
  box-shadow: var(--m-shadow-1);
}
.msg.user .bubble {
  background: var(--m-primary); color: #fff;
  border-radius: 16px 6px 16px 16px;
  box-shadow: 0 1px 2px rgba(66,133,244,.25);
}
.msg.assistant .bubble { border-radius: 6px 16px 16px 16px; }
.bubble :deep(p) { margin: 4px 0; }
.bubble :deep(p:first-child) { margin-top: 0; }
.bubble :deep(p:last-child) { margin-bottom: 0; }
.bubble :deep(pre) {
  background: #f1f3f4; color: #202124;
  padding: 10px 12px; border-radius: 8px;
  overflow: auto; max-height: 320px;
  font-size: 12px; line-height: 1.5;
  margin: 6px 0;
  font-family: ui-monospace, Menlo, monospace;
}
.bubble :deep(:not(pre) > code) {
  background: #f1f3f4; color: #c5221f;
  padding: 1px 5px; border-radius: 4px; font-size: 12px;
}
.msg.user .bubble :deep(:not(pre) > code) { background: rgba(255,255,255,.18); color: #fff; }

.msg-files { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px; }
.msg-file-chip {
  display: inline-flex; align-items: center;
  padding: 2px 8px;
  background: rgba(255,255,255,.18);
  border-radius: var(--m-radius-pill);
  font-size: 11px;
}
.msg-file-chip.clickable { cursor: pointer; }
.msg.assistant .msg-file-chip { background: var(--m-surface-variant); color: var(--m-text-secondary); }

/* Composer — no top border, just elevation */
.composer-wrap {
  flex-shrink: 0;
  padding: 8px 12px calc(10px + var(--safe-bottom));
  background: var(--m-bg);
}
.files-row { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
.file-chip {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 8px 5px 10px;
  background: var(--m-surface);
  border: none;
  border-radius: var(--m-radius-pill);
  font-size: 11.5px;
  max-width: 220px;
  box-shadow: var(--m-shadow-1);
}
.file-chip.parsing { background: var(--m-primary-soft); }
.file-chip.failed { background: #fce8e6; }
.chip-name {
  max-width: 110px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  font-weight: 500; color: var(--m-text);
}
.chip-meta { color: var(--m-text-secondary); font-size: 11px; }
.chip-meta.err { color: var(--m-danger); }
.chip-close {
  width: 18px; height: 18px; border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
  color: var(--m-text-secondary); font-size: 14px; line-height: 1;
}
.chip-close:active { background: var(--m-surface-variant); }

.composer {
  display: flex; align-items: flex-end; gap: 6px;
  background: var(--m-surface);
  border-radius: 24px;
  padding: 4px 4px 4px 6px;
  box-shadow: 0 1px 3px rgba(60,64,67,.1);
}
.icon-btn {
  width: 36px; height: 36px; border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
  color: var(--m-text-secondary); flex-shrink: 0;
}
.icon-btn:active { background: var(--m-surface-variant); color: var(--m-text); }
.icon-btn:disabled { color: var(--m-border-strong); }

textarea {
  flex: 1; min-width: 0;
  border: none; background: transparent;
  resize: none; outline: none;
  font-size: 15px; line-height: 1.4;
  padding: 9px 4px;
  max-height: 140px; min-height: 22px;
}
.send-btn {
  width: 36px; height: 36px; border-radius: 50%;
  background: var(--m-primary); color: #fff;
  display: inline-flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  transition: background .15s, transform .15s;
}
.send-btn:disabled { background: var(--m-border-strong); }
.send-btn:active:not(:disabled) { transform: scale(.94); }
.spinner {
  width: 14px; height: 14px; border-radius: 50%;
  border: 2px solid rgba(255,255,255,.4);
  border-top-color: #fff;
  animation: spin 1s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Drawer */
.mb-drawer {
  background: var(--m-bg);
  display: flex; flex-direction: column;
}
.drawer-brand {
  display: flex; align-items: center; gap: 10px;
  padding: env(safe-area-inset-top, 16px) 16px 12px;
  padding-top: calc(env(safe-area-inset-top, 0px) + 18px);
  flex-shrink: 0;
}
.brand-mark {
  width: 32px; height: 32px;
  display: grid; grid-template-columns: 1fr 1fr; gap: 4px;
  flex-shrink: 0;
}
.brand-mark .dot { border-radius: 50%; }
.brand-text { line-height: 1.2; }
.brand-name { font-size: 16px; font-weight: 600; color: var(--m-text); letter-spacing: -.01em; }
.brand-sub { font-size: 11.5px; color: var(--m-text-secondary); margin-top: 2px; }

.conv-new {
  margin: 4px 12px 14px;
  display: flex; align-items: center; gap: 8px; justify-content: center;
  height: 42px; border-radius: 12px;
  background: var(--m-primary-soft); color: var(--m-primary);
  font-weight: 500; font-size: 14px;
  flex-shrink: 0;
}
.conv-new:active { background: rgba(66,133,244,.15); }

.drawer-nav {
  display: flex; flex-direction: column;
  margin: 0 8px 8px;
  gap: 2px;
}
.nav-item {
  display: flex; align-items: center; gap: 10px;
  height: 38px; padding: 0 12px;
  border-radius: 10px;
  font-size: 13.5px; color: var(--m-text);
  background: transparent;
  position: relative;
}
.nav-item:active { background: var(--m-surface-variant); }
.nav-item .badge {
  position: absolute; right: 12px;
  min-width: 16px; height: 16px; padding: 0 5px;
  border-radius: 8px;
  background: var(--m-danger); color: #fff;
  font-size: 10px; font-weight: 600; line-height: 16px;
  text-align: center;
}

.drawer-section-label {
  padding: 4px 18px 6px;
  font-size: 11.5px; font-weight: 600;
  color: var(--m-text-tertiary); letter-spacing: .04em;
  text-transform: uppercase;
}
.drawer-list { flex: 1; overflow: auto; padding: 0 8px 12px; }
.empty {
  text-align: center; color: var(--m-text-tertiary);
  padding: 24px; font-size: 13px;
}
.conv-item {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 12px;
  margin: 2px 0;
  border-radius: 10px;
  font-size: 13.5px;
  color: var(--m-text);
}
.conv-item:active { background: var(--m-surface-variant); }
.conv-item.active { background: var(--m-primary-soft); color: var(--m-primary); }
.conv-icon { color: var(--m-text-tertiary); flex-shrink: 0; }
.conv-item.active .conv-icon { color: var(--m-primary); }
.conv-name {
  flex: 1; min-width: 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.conv-action {
  width: 26px; height: 26px; border-radius: 50%;
  color: var(--m-text-secondary); font-size: 16px; line-height: 1;
}
.conv-action:active { background: var(--m-surface-variant); }

.drawer-footer {
  flex-shrink: 0;
  display: flex; align-items: center; gap: 12px;
  padding: 12px 14px calc(12px + var(--safe-bottom));
  margin-top: 4px;
  background: var(--m-surface);
  border-top: 1px solid var(--m-border);
}
.drawer-footer:active { background: var(--m-surface-variant); }
.user-avatar {
  width: 38px; height: 38px; border-radius: 50%;
  background: var(--m-primary-soft); color: var(--m-primary);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.user-info { flex: 1; min-width: 0; }
.user-name {
  font-size: 14px; font-weight: 600; color: var(--m-text);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.user-role {
  font-size: 11.5px; color: var(--m-text-secondary); margin-top: 2px;
}
.user-settings {
  width: 36px; height: 36px; border-radius: 50%;
  color: var(--m-text-secondary);
  display: flex; align-items: center; justify-content: center;
}
.user-settings:active { background: var(--m-surface-variant); }

/* Agent sheet items */
.agent-item {
  display: flex; align-items: center; gap: 12px;
  padding: 14px 16px;
  border-bottom: none;
}
.agent-item:active { background: var(--m-surface-variant); }
.agent-item.active { background: var(--m-primary-soft); }
.agent-avatar {
  width: 36px; height: 36px; border-radius: 50%;
  background: var(--m-primary); color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-weight: 600; flex-shrink: 0;
}
.agent-text { flex: 1; min-width: 0; }
.agent-name { font-size: 15px; font-weight: 500; color: var(--m-text); }
.agent-desc {
  margin-top: 2px;
  font-size: 12.5px; color: var(--m-text-secondary); line-height: 1.5;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.agent-item.active .agent-name { color: var(--m-primary); }
.check { color: var(--m-primary); flex-shrink: 0; }

/* Action sheet items */
.action-item {
  padding: 14px 16px;
  text-align: center; font-size: 15px;
  border-bottom: none;
  position: relative;
}
.action-item + .action-item:not(.cancel)::before {
  content: '';
  position: absolute; left: 16px; right: 16px; top: 0;
  height: 1px; background: var(--m-border);
}
.action-item:active { background: var(--m-surface-variant); }
.action-item.danger { color: var(--m-danger); }
.action-item.cancel {
  margin-top: 8px;
  background: var(--m-bg-soft);
  font-weight: 600;
}

/* Change password fields */
.pwd-body { padding: 12px 16px 24px; display: flex; flex-direction: column; gap: 14px; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field span { font-size: 13px; color: var(--m-text-secondary); padding-left: 2px; }
.field input {
  height: 44px; padding: 0 14px;
  border: none;
  background: var(--m-bg-soft);
  border-radius: 12px;
  font-size: 15px; outline: none;
}
.field input:focus { background: var(--m-surface); box-shadow: 0 0 0 2px var(--m-primary); }

.primary-btn {
  height: 46px; margin-top: 6px;
  background: var(--m-primary); color: #fff;
  border-radius: 12px; font-size: 15px; font-weight: 500;
  display: flex; align-items: center; justify-content: center;
}
.primary-btn:active { background: var(--m-primary-hover); }
.primary-btn:disabled { background: var(--m-border-strong); }
</style>
