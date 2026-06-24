<template>
  <div class="chat-wrap" :class="{ 'split-mode': previewFile }">
    <section class="conv">
      <div ref="scrollRef" class="messages">
        <!-- 欢迎页 -->
        <WelcomePanel
          v-if="!chat.currentConvId || chat.messages.length === 0"
          :agents="welcomeAgents"
          :starters="activeStarters"
          @pick-agent="selectAgent"
          @pick-starter="useStarter"
        />

        <template v-else>
          <div
            v-for="m in chat.messages"
            v-show="!(m.role === 'user' && m.content_json?.hidden)"
            :key="m.id || m._tmp"
            :class="['msg', m.role, { 'is-highlighted': highlightedMessageId === m.id }]"
            :data-mid="m.id"
          >
            <div v-if="m.role === 'assistant'" :class="['avatar', 'bot', { 'is-thinking': isWaiting(m) }]" :style="{ background: agentGradient(chat.currentAgent?.id || 0) }">
              <img v-if="chat.currentAgent?.icon_url" :src="chat.currentAgent.icon_url" />
              <span v-else>{{ agentInitial(chat.currentAgent) }}</span>
            </div>
            <div class="bubble-stack">
              <div v-if="isWaiting(m)" class="thinking-pill">
                <span class="thinking-text">{{ thinkingLabel(m) }}</span>
                <span class="thinking-dots"><span /><span /><span /></span>
              </div>

              <div v-if="m.role === 'assistant' && m._meta && m.content_json?.text" class="msg-meta">
                <span>{{ m._meta.agent_name }}</span>
                <span class="dot-sep">·</span>
                <code>{{ m._meta.model_id }}</code>
              </div>

              <details v-if="m.content_json?.thinking || m._thinking" class="thinking-card" :open="m._thinkingOpen ?? !m.content_json?.text">
                <summary>
                  <el-icon><Cpu /></el-icon>
                  <span>思考过程</span>
                  <span class="muted" style="font-size:11px;margin-left:6px">{{ (m.content_json?.thinking || m._thinking || '').length }} 字</span>
                </summary>
                <div class="thinking-body">
                  <div :ref="(el) => setThinkingRef(el, m)" class="thinking-content">{{ m.content_json?.thinking || m._thinking }}</div>
                </div>
              </details>

              <div v-if="m._steps?.length" class="step-summary">
                <svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"><polyline points="2 8 6 12 14 4"/></svg>
                执行 {{ m._steps.length }} 个步骤
              </div>

              <div v-if="(m.content_json?.files?.length) || m._files?.length" class="files-block">
                <FileCard
                  v-for="(f, fi) in (m._files?.length ? m._files : m.content_json.files)"
                  :key="fi + (f.name || '')"
                  :file="f"
                  @preview="openPreview"
                />
              </div>

              <div v-if="(m.content_json?.uis?.length) || m._uis?.length" class="ui-block">
                <MessageDispatcher
                  v-for="(s, ui) in (m._uis?.length ? m._uis : m.content_json.uis)"
                  :key="s.surface_id || ui"
                  :schema="s"
                  :on-agent-call="onAgentCall"
                />
              </div>

              <div v-if="(m.content_json?.text || m.role === 'user') && !(m.role === 'user' && editingMsg === m)" :class="['bubble', { 'bubble--clamped': m.role === 'user' && isLongUserMsg(m) && !expandedMsgs[getMsgKey(m)] }]">
                <template v-if="m.role === 'user'">
                  <div v-if="m.content_json?.files?.length" class="msg-files">
                    <span v-for="(f, fi) in m.content_json.files" :key="fi" :class="['msg-file-chip', { clickable: canPreview(f) }]" @click="canPreview(f) && openPreview(f)">
                      <el-icon :size="12"><Paperclip /></el-icon>
                      {{ f.name }}<span v-if="f.parsed_chars" class="msg-file-meta"> · {{ f.parsed_chars }}字</span>
                    </span>
                  </div>
                  <div class="bubble-content" v-html="safeRender(m.content_json?.text || '')"></div>
                  <div v-if="isLongUserMsg(m) && !expandedMsgs[getMsgKey(m)]" class="bubble-clamp-fade" />
                </template>
                <template v-else>
                  <div :class="{ 'msg-body-fold': isFolded(m) }">
                    <template v-for="(seg, si) in parseSegments(m)" :key="seg.type === 'widget' ? ('w-' + (seg as any).stableKey || si) : 't-' + si">
                      <div v-if="seg.type === 'text'" class="bubble-content" v-html="renderText(seg.content)"></div>
                      <WidgetRenderer v-else-if="seg.type === 'widget'" :widget-code="(seg as any).widgetCode" :title="(seg as any).title" :is-streaming="(seg as any).isStreaming" @send-message="onWidgetSendMessage" />
                    </template>
                    <MermaidRenderer :text="m.content_json?.text || ''" />
                  </div>
                  <button v-if="isLongAssistantMsg(m)" class="msg-fold-btn" @click="toggleFold(m)">
                    {{ isFolded(m) ? '展开全部 ↓' : '收起 ↑' }}
                  </button>
                </template>
              </div>

              <button v-if="m.role === 'user' && isLongUserMsg(m)" class="bubble-expand-btn" @click="toggleExpandMsg(m)">
                {{ expandedMsgs[getMsgKey(m)] ? '收起' : '展开' }}
                <svg :class="['bubble-expand-chevron', { rotated: expandedMsgs[getMsgKey(m)] }]" viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 6 8 10 12 6"/></svg>
              </button>

              <div v-if="m.role === 'assistant' && m.content_json?.text && !m._streaming" class="msg-actions">
                <button class="msg-action" @click="copyAnswer(m)" title="复制回答">
                  <el-icon :size="14"><DocumentCopy /></el-icon><span>复制</span>
                </button>
                <button class="msg-action" :class="{ active: isFavorited(m) }" @click="toggleFavorite(m)" :title="isFavorited(m) ? '取消收藏' : '收藏到空间'">
                  <el-icon :size="14"><StarFilled v-if="isFavorited(m)" /><Star v-else /></el-icon>
                  <span>{{ isFavorited(m) ? '已收藏' : '收藏' }}</span>
                </button>
                <button class="msg-action feedback-like" :class="{ active: getFeedback(m) === 'like' }" @click="toggleFeedback(m, 'like')" title="有帮助"><el-icon :size="14"><SuccessFilled /></el-icon></button>
                <button class="msg-action feedback-dislike" :class="{ active: getFeedback(m) === 'dislike' }" @click="toggleFeedback(m, 'dislike')" title="没帮助"><el-icon :size="14"><CircleCloseFilled /></el-icon></button>
              </div>

              <!-- 用户消息编辑 -->
              <div v-if="m.role === 'user' && editingMsg !== m" class="msg-actions">
                <button class="msg-action" @click="onEdit(m)" title="编辑" aria-label="编辑消息">
                  <el-icon :size="14"><Edit /></el-icon><span>编辑</span>
                </button>
              </div>
              <div v-if="m.role === 'user' && editingMsg === m" class="edit-mode">
                <el-input type="textarea" v-model="editText" :rows="3" resize="vertical" />
                <div class="edit-actions">
                  <el-button size="small" @click="onCancelEdit">取消</el-button>
                  <el-button size="small" type="primary" @click="onConfirmEdit">确认</el-button>
                </div>
              </div>

              <!-- 分支按钮 -->
              <div v-if="m.role === 'assistant' && m.id && !m._streaming" class="msg-actions">
                <button class="msg-action" @click="onBranch(m)" title="从此处继续对话" aria-label="从此处继续对话">
                  <el-icon :size="14"><Share /></el-icon><span>分支</span>
                </button>
              </div>
            </div>
          </div>
        </template>
      </div>

      <ComposerInput
        :files="pendingFilesCompatible"
        :sending="sending"
        :suggestions="slashSuggestions"
        @send="onSend"
        @stop="stopStream"
        @add-file="onPick"
        @remove-file="removeFile"
      />
    </section>
    <PreviewPanel v-if="previewFile" :file="previewFile" @close="closePreview" />
    <AgentCapabilityDrawer v-model="capDrawerVisible" :agent-id="capDrawerAgentId" :agent-name="chat.currentAgent?.name" />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'
import { useChat } from '@/stores/chat'
import { useSpace } from '@/stores/space'
import MarkdownIt from 'markdown-it'
import WidgetRenderer from '@/components/WidgetRenderer.vue'
import PreviewPanel from '@/components/PreviewPanel.vue'
import AgentCapabilityDrawer from '@/components/AgentCapabilityDrawer.vue'
import MessageDispatcher from '@/agent-ui/engine/MessageDispatcher.vue'
import WelcomePanel from '@/components/chat/WelcomePanel.vue'
import ComposerInput from '@/components/chat/ComposerInput.vue'
import MermaidRenderer from '@/components/chat/MermaidRenderer.vue'
import { InfoFilled, Loading } from '@element-plus/icons-vue'
import { parseMessageContent } from '@/lib/widget-parser'
import { useChatStream } from '@/composables/useChatStream'
import { PREVIEWABLE, agentGradient } from '@/shared/constants'
import type { AgentInfo, StarterItem, UploadFile } from '@/shared/types/chat'

const md = new MarkdownIt({ breaks: true, linkify: true })
const chat = useChat()
const space = useSpace()
const route = useRoute()
const router = useRouter()

const editingMsg = ref<any>(null)
const editText = ref('')

const { sending, streamAbortController, streamMessage, isWaiting } = useChatStream({
  chatStore: chat,
  scrollBottom: async () => {
    await nextTick()
    const el = scrollRef.value
    if (!el) return
    const threshold = 120
    if (el.scrollHeight - el.scrollTop - el.clientHeight > threshold) return
    el.scrollTop = el.scrollHeight
  },
  input: ref(''),
})

function stopStream() { streamAbortController.value?.abort() }

const expandedMsgs = ref<Record<string, boolean>>({})
const foldedLongMsgs = ref<Record<string, boolean>>({})
function getMsgKey(m: any) { return String(m.id ?? m._tmp ?? '') }
function toggleExpandMsg(m: any) { const k = getMsgKey(m); expandedMsgs.value[k] = !expandedMsgs.value[k] }
function isLongUserMsg(m: any) { const t = m.content_json?.text || ''; return t.length > 400 || t.split('\n').length > 8 }
function isLongAssistantMsg(m: any) { const t = m.content_json?.text || ''; return t.length > 600 || t.split('\n').length > 20 }
function toggleFold(m: any) { const k = getMsgKey(m); foldedLongMsgs.value[k] = !foldedLongMsgs.value[k] }
function isFolded(m: any) { return foldedLongMsgs.value[getMsgKey(m)] ?? (isLongAssistantMsg(m) ? true : false) }

const scrollRef = ref<HTMLElement | null>(null)
const previewFile = ref<any | null>(null)
const capDrawerVisible = ref(false)
const capDrawerAgentId = ref<number | null>(null)

function agentInitial(agent: any) { return (agent?.name || '').charAt(0) }

function selectAgent(agentId: number) {
  const found = chat.agents.find((a: any) => a.id === agentId)
  if (found) chat.selectAgent(found)
}

const activeStarters = computed<StarterItem[]>(() => {
  const desc = chat.currentAgent?.description || ''
  if (!desc) return []
  const starterRe = /^\s*(?:[-•*]|\d+[.、])\s+(.+)$/
  const items: StarterItem[] = []
  for (const raw of desc.split(/\r?\n/)) {
    const m = raw.match(starterRe)
    if (m && m[1].trim()) items.push({ label: m[1].trim(), query: m[1].trim() })
  }
  return items.slice(0, 4)
})

const welcomeAgents = computed<AgentInfo[]>(() =>
  chat.agents.slice(0, 5).map((a: any) => ({ id: a.id, name: a.name, description: a.description, avatar_url: a.icon_url }))
)

// ComposerInput compatibility — map from chat.pendingFiles to UploadFile[]
const pendingFilesCompatible = computed<UploadFile[]>(() =>
  chat.pendingFiles.map((f: any) => ({ id: String(f.id), name: f.name, size: f.size, status: mapParseStatus(f.parse_status), error: f.parse_error }))
)

function mapParseStatus(s: string): UploadFile['status'] {
  if (s === 'parsing') return 'parsing'
  if (s === 'done' || s === 'skipped') return 'ready'
  if (s === 'failed') return 'error'
  return 'uploading'
}

function useStarter(q: string) {
  if (!q || sending.value || !chat.currentAgent) return
  onSend(q)
}

function closePreview() { previewFile.value = null }

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
    await new Promise((r) => setTimeout(r, 80))
  }
}

onMounted(async () => {
  if (!chat.loaded) await chat.loadInit()
  const convQuery = route.query.conv
  const convId = Array.isArray(convQuery) ? Number(convQuery[0]) : Number(convQuery)
  if (convId && !Number.isNaN(convId) && convId !== chat.currentConvId) {
    let conv = chat.convs.find((c: any) => c.id === convId)
    if (!conv) conv = { id: convId }
    try { await chat.selectConv(conv) } catch {}
  }
  await scrollBottom()
  const msgQuery = route.query.msg
  const msgId = Array.isArray(msgQuery) ? Number(msgQuery[0]) : Number(msgQuery)
  if (msgId && !Number.isNaN(msgId)) await scrollToMessage(msgId)
})

onBeforeUnmount(() => {
  if (highlightTimer) clearTimeout(highlightTimer)
})

watch(() => chat.currentConvId, async () => { await scrollBottom() })
watch(() => route.query.msg, async (val) => {
  const id = Array.isArray(val) ? Number(val[0]) : Number(val)
  if (id && !Number.isNaN(id)) await scrollToMessage(id)
})

const thinkingRefs = new WeakMap<object, HTMLElement>()
function setThinkingRef(el: unknown, m: object) { if (el instanceof HTMLElement) thinkingRefs.set(m, el) }

// ComposerInput -> Chat send bridge
function onSend(text: string) {
  if (!chat.currentAgent) {
    ElMessage.warning('请先选择数字员工')
    return
  }
  input.value = text
  send()
}
const input = ref('')

const slashSuggestions = computed(() => {
  const starters = activeStarters.value.length ? activeStarters.value : []
  return ['帮我把这段翻译成英文', '帮我写一份周报', '总结这个对话', ...starters]
})

function onEdit(msg: any) {
  editingMsg.value = msg
  editText.value = msg.content_json?.text || msg.content || ''
}

function onCancelEdit() {
  editingMsg.value = null
  editText.value = ''
}

async function onConfirmEdit() {
  if (!editingMsg.value || !editText.value.trim()) return
  const msg = editingMsg.value
  const idx = chat.messages.indexOf(msg)
  if (idx === -1) { onCancelEdit(); return }
  msg.content_json = msg.content_json || {}
  msg.content_json.text = editText.value.trim()
  chat.messages.splice(idx + 1)
  const text = editText.value.trim()
  editingMsg.value = null
  if (!chat.currentConvId) await chat.ensureConv()
  const placeholder = {
    _tmp: Date.now() + 1, role: 'assistant',
    content_json: { text: '' }, tool_calls_json: null,
    _meta: null, _thinking: '', _steps: [], _stepIndex: {} as Record<string, number>,
    _files: [], _uis: [], _streaming: true,
  }
  chat.messages.push(placeholder)
  const ph: any = chat.messages[chat.messages.length - 1]
  sending.value = true
  await scrollBottom()
  if (!chat.currentConvId) return
  await streamMessage({ convId: chat.currentConvId, text, fileIds: [], placeholder: ph })
}

async function onBranch(m: any) {
  if (!chat.currentConvId || !m.id) return
  try {
    const res = await api.branchConversation(chat.currentConvId, m.id)
    ElMessage.success('已创建分支对话')
    await chat.selectConv({ id: res.id, title: res.title })
    router.push('/chat').catch(() => {})
  } catch { ElMessage.error('创建分支失败') }
}

function safeRender(text: string): string {
  if (!text) return ''
  let safe = text
  const codeFenceCount = (safe.match(/```/g) || []).length
  if (codeFenceCount % 2 !== 0) safe += '\n```'
  return enhanceCodeBlocks(md.render(safe))
}

function renderText(text: string): string {
  return safeRender(text.replace(/```mermaid[\s\S]*?```/g, ''))
}

function enhanceCodeBlocks(html: string): string {
  return html.replace(
    /<pre><code class="language-(\w+)">([\s\S]*?)<\/code><\/pre>/g,
    (_, lang, code) => {
      const lines = code.split('\n').length
      const folded = lines > 12 ? ' folded' : ''
      return `<div class="code-wrap${folded}">
        <div class="code-head">
          <span class="code-lang">${lang}</span>
          <span class="code-actions">
            <button class="code-btn code-copy" onclick="(function(){
              navigator.clipboard.writeText(decodeURIComponent('${encodeURIComponent(unescapeHtml(code))}'));
              this.textContent='已复制';
              setTimeout(()=>this.textContent='复制',1500)
            })()">复制</button>
            ${lines > 12 ? `<button class="code-btn code-fold" onclick="this.closest('.code-wrap').classList.toggle('folded')">展开</button>` : ''}
          </span>
        </div>
        <pre><code class="language-${lang}">${code}</code></pre>
      </div>`
    }
  )
}

function unescapeHtml(text: string): string {
  return text.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'")
}

async function onPick(file: File) {
  if (!chat.currentAgent) { ElMessage.warning('请先选择数字员工'); return }
  if (!chat.currentConvId) await chat.ensureConv()
  try {
    const r = await api.uploadFile(file, chat.currentConvId!)
    chat.pendingFiles.push(r)
    pollFileStatus(r.id)
  } catch {}
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

async function removeFile(fileId: string) {
  const id = Number(fileId)
  chat.pendingFiles = chat.pendingFiles.filter((x: any) => x.id !== id)
  try { await api.deleteFile(id) } catch {}
}


function canPreview(f: any): boolean {
  if (!f) return false
  const e = (f.ext || (f.name || '').split('.').pop() || '').toLowerCase().replace(/^\./, '')
  return PREVIEWABLE.has(e)
}
function openPreview(f: any) {
  const url = f.download_url || (f.id ? `/api/files/${f.id}/raw` : '')
  previewFile.value = { ...f, download_url: url }
}

async function onAgentCall(text: string) {
  if (!chat.currentAgent || sending.value) return
  if (!chat.currentConvId) await chat.ensureConv()
  const placeholder: any = reactive({
    _tmp: Date.now(), role: 'assistant', content_json: { text: '' }, tool_calls_json: null,
    _meta: null, _thinking: '', _steps: [], _stepIndex: {}, _files: [], _uis: [], _streaming: true,
  })
  chat.messages.push(placeholder)
  sending.value = true
  await scrollBottom()
  if (!chat.currentConvId) return
  await streamMessage({ convId: chat.currentConvId, text, fileIds: [], placeholder })
}

function parseSegments(m: any) {
  return parseMessageContent(m.content_json?.text || '', !!m._streaming)
}

function onWidgetSendMessage(text: string) {
  if (!text || sending.value) return
  onSend(text)
}

function thinkingLabel(m: any): string { return m._meta ? '正在思考' : '正在连接数字员工' }

async function copyAnswer(m: any) {
  // 优先从 DOM 复制用户看到的完整内容（包括 widget、mermaid 等渲染结果）
  const mid = m.id || m._tmp
  if (mid) {
    const msgEl = document.querySelector(`.msg[data-mid="${mid}"]`)
    const bubbleEl = msgEl?.querySelector('.bubble-stack')
    if (bubbleEl) {
      const html = bubbleEl.innerHTML
      const plain = html.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim()
      try {
        if (typeof ClipboardItem === 'function' && navigator.clipboard?.write) {
          await navigator.clipboard.write([new ClipboardItem({
            'text/html': new Blob([html], { type: 'text/html' }),
            'text/plain': new Blob([plain], { type: 'text/plain' }),
          })])
        } else {
          await navigator.clipboard.writeText(plain)
        }
        ElMessage.success({ message: '已复制', duration: 2000 })
        return
      } catch {}
    }
  }
  // fallback: 复制原始文本
  const text = m.content_json?.text || ''
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success({ message: '已复制', duration: 2000 })
  } catch { ElMessage.error('复制失败') }
}

function isFavorited(m: any): boolean { return space.isFavorited(m?.id) }

async function toggleFavorite(m: any) {
  if (!m?.id) { ElMessage.warning('该消息还未保存,稍后再试'); return }
  if (isFavorited(m)) {
    try { await ElMessageBox.confirm('确定取消收藏吗?', '确认', { type: 'warning' }) } catch { return }
    try { await space.unfavorite(m.id); ElMessage.success('已取消收藏') } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '操作失败') }
  } else {
    try { await space.favorite(m.id); ElMessage.success('已加入空间') } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '操作失败') }
  }
}

const feedbackMap = ref<Record<number, { rating: string; id: number }>>({})
async function loadFeedbacks(msgIds: number[]) {
  if (!msgIds.length) return
  try {
    const res = await api.request(`/api/feedback/check?message_ids=${msgIds.join(',')}`)
    if (res) { for (const [mid, info] of Object.entries(res)) feedbackMap.value[Number(mid)] = info as any }
  } catch {}
}
function getFeedback(m: any): string | null { return feedbackMap.value[m?.id]?.rating || null }
async function toggleFeedback(m: any, rating: string) {
  if (!m?.id) return
  const current = getFeedback(m)
  try {
    if (current === rating) {
      const fbId = feedbackMap.value[m.id]?.id
      if (fbId) { await api.request(`/api/feedback/${fbId}`, { method: 'DELETE' }); delete feedbackMap.value[m.id] }
    } else {
      const res = await api.request('/api/feedback', { method: 'POST', data: { message_id: m.id, rating } })
      feedbackMap.value[m.id] = { rating, id: res.id }
      ElMessage.success(rating === 'like' ? '感谢反馈' : '已记录，我们会改进')
    }
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '反馈失败') }
}
watch(() => chat.messages, (msgs) => { loadFeedbacks(msgs.filter((m: any) => m.role === 'assistant' && m.id).map((m: any) => m.id)) }, { immediate: true })

async function scrollBottom() { await nextTick(); const el = scrollRef.value; if (el) el.scrollTop = el.scrollHeight }

async function send() {
  if (!chat.currentAgent || !input.value.trim()) return
  const policy = chat.currentAgent?.upload_policy_json || {}
  const maxPerSend = Number(policy.max_files_per_send || 0)
  if (maxPerSend > 0 && chat.pendingFiles.length > maxPerSend) { ElMessage.warning(`单次发送最多 ${maxPerSend} 个文件,请删减后再发送`); return }
  const stillParsing = chat.pendingFiles.filter((f: any) => f.parse_status === 'parsing')
  if (stillParsing.length) { ElMessage.warning(`还有 ${stillParsing.length} 个文件解析中,请稍候`); return }
  const isFirstMessage = chat.messages.length === 0
  if (!chat.currentConvId) await chat.ensureConv()
  const text = input.value.trim()
  const fileIds = chat.pendingFiles.map((f: any) => f.id)
  const fileBriefs = chat.pendingFiles.map((f: any) => ({ id: f.id, name: f.name, size: f.size, parse_status: f.parse_status, parsed_chars: f.parsed_chars }))
  chat.messages.push({ _tmp: Date.now(), role: 'user', content_json: { text, files: fileBriefs } })
  const placeholder = {
    _tmp: Date.now() + 1, role: 'assistant',
    content_json: { text: '' }, tool_calls_json: null,
    _meta: null, _thinking: '', _steps: [], _stepIndex: {} as Record<string, number>, _files: [], _uis: [], _streaming: true,
  }
  chat.messages.push(placeholder)
  const ph: any = chat.messages[chat.messages.length - 1]
  input.value = ''
  chat.pendingFiles = []
  sending.value = true
  await scrollBottom()
  if (!chat.currentConvId) return
  await streamMessage({ convId: chat.currentConvId, text, fileIds, placeholder: ph })

  if (isFirstMessage && chat.currentConvId) {
    const conv = chat.convs.find((c: any) => c.id === chat.currentConvId)
    if (conv) {
      const title = text.replace(/\s+/g, ' ').trim().slice(0, 30)
      if (title && title !== conv.title) chat.renameConv(conv, title).catch(() => {})
    }
  }
}
</script>

<style scoped>
.chat-wrap { position: absolute; inset: 0; display: flex; background: var(--m-bg); }
.chat-wrap.split-mode .conv { flex: 1 1 50%; max-width: 50%; }
.chat-wrap.split-mode :deep(.preview-panel) { flex: 1 1 50%; max-width: 50%; }
.files-block { display: flex; flex-direction: column; gap: 4px; }
.conv { flex: 1; display: flex; flex-direction: column; min-width: 0; min-height: 0; background: var(--m-surface); }
.messages { flex: 1; min-height: 0; overflow: auto; padding: 24px 0; }
.msg { display: flex; gap: 12px; max-width: 850px; margin: 0 auto 16px; padding: 0 24px; }
.msg.user { flex-direction: row-reverse; }
.avatar.bot { width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: var(--m-on-primary); font-size: 14px; font-weight: 600; flex-shrink: 0; }
.avatar.bot img { width: 100%; height: 100%; border-radius: 50%; object-fit: cover; }
.avatar.bot.is-thinking { border-color: var(--m-primary); box-shadow: 0 0 0 0 var(--m-primary-soft); animation: avatar-glow 1.6s ease-in-out infinite; }
@keyframes avatar-glow { 0%, 100% { box-shadow: 0 0 0 0 rgba(66,133,244,.18); } 50% { box-shadow: 0 0 0 4px rgba(66,133,244,.06); } }
.bubble-stack { display: flex; flex-direction: column; gap: 8px; flex: 1 1 0; max-width: 80%; min-width: 0; }
.msg.user .bubble-stack { align-items: flex-end; }
.thinking-pill { display: inline-flex; align-items: center; gap: 8px; padding: 8px 14px; background: var(--m-bg-soft); border-radius: var(--m-radius-pill); font-size: 13px; color: var(--m-text-secondary); align-self: flex-start; width: fit-content; }
.thinking-text { font-weight: 500; }
.thinking-dots { display: inline-flex; gap: 3px; }
.thinking-dots span { width: 5px; height: 5px; border-radius: 50%; background: currentColor; animation: dot-bounce 1.2s ease-in-out infinite; }
.thinking-dots span:nth-child(2) { animation-delay: .15s; }
.thinking-dots span:nth-child(3) { animation-delay: .3s; }
@keyframes dot-bounce { 0%, 80%, 100% { opacity: .3; transform: translateY(0); } 40% { opacity: 1; transform: translateY(-3px); } }
.bubble { max-width: 100%; padding: 12px 16px; background: var(--m-bg-soft); border: 1px solid transparent; border-radius: var(--m-radius-lg); font-size: 14.5px; line-height: 1.65; word-break: break-word; }
.msg.is-highlighted .bubble { animation: msg-flash 1.6s ease-out; }
@keyframes msg-flash { 0% { box-shadow: 0 0 0 0 var(--m-primary-soft); background: var(--m-primary-soft); } 60% { box-shadow: 0 0 0 6px transparent; background: var(--m-primary-soft); } 100% { box-shadow: 0 0 0 0 transparent; background: var(--m-bg-soft); } }
.msg-actions { display: flex; align-items: center; gap: 4px; margin-top: 4px; padding: 0 4px; opacity: .5; transition: opacity .15s ease; }
.msg:hover .msg-actions { opacity: 1; }
.msg-action { display: inline-flex; align-items: center; gap: 4px; padding: 4px 8px; font-size: 12px; color: var(--m-text-secondary); background: transparent; border: none; border-radius: var(--m-radius); cursor: pointer; transition: background .15s, color .15s; }
.msg-action:hover { background: var(--m-surface-variant); color: var(--m-text); }
.msg-action.active { color: var(--m-primary); }
.msg-action.feedback-like.active { color: #67c23a; }
.msg-action.feedback-dislike.active { color: #f56c6c; }
.edit-mode { padding: 8px; background: var(--m-surface-variant); border-radius: var(--m-radius); }
.edit-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 8px; }
.msg.user .bubble { background: var(--m-primary); color: var(--m-on-primary); border-color: transparent; border-radius: var(--m-radius-lg) var(--m-radius-sm) var(--m-radius-lg) var(--m-radius-lg); }
.bubble--clamped { max-height: 200px; overflow: hidden; position: relative; }
.bubble-clamp-fade { position: absolute; bottom: 0; left: 0; right: 0; height: 56px; background: linear-gradient(to bottom, transparent, var(--m-primary)); pointer-events: none; border-radius: 0 0 var(--m-radius-lg) var(--m-radius-sm); }
.bubble-expand-btn { display: inline-flex; align-items: center; gap: 3px; align-self: flex-end; padding: 2px 8px; margin-top: 2px; font-size: 12px; color: var(--m-primary); background: transparent; border: none; cursor: pointer; opacity: .75; transition: opacity .15s; }
.bubble-expand-btn:hover { opacity: 1; }
.bubble-expand-chevron { transition: transform .2s ease; }
.bubble-expand-chevron.rotated { transform: rotate(180deg); }
.msg.assistant .bubble { border-radius: var(--m-radius-sm) var(--m-radius-lg) var(--m-radius-lg) var(--m-radius-lg); }
.bubble :deep(p) { margin: 4px 0; }
.bubble :deep(p:first-child) { margin-top: 0; }
.bubble :deep(p:last-child) { margin-bottom: 0; }
.bubble :deep(pre) { background: var(--m-bg-soft); color: var(--m-text); padding: 14px 16px; border-radius: var(--m-radius); border: 1px solid var(--m-border); overflow: auto; max-height: 420px; font-size: 13px; line-height: 1.55; margin: 8px 0; font-family: 'Roboto Mono', ui-monospace, 'SFMono-Regular', Menlo, Consolas, monospace; scrollbar-width: thin; scrollbar-color: var(--m-border-strong) transparent; }
.bubble :deep(code) { font-family: 'Roboto Mono', ui-monospace, 'SFMono-Regular', Menlo, Consolas, monospace; }
.bubble :deep(:not(pre) > code) { background: var(--m-bg-soft); color: var(--m-danger); padding: 1px 6px; border-radius: 4px; font-size: 13px; border: 1px solid var(--m-border); }
.msg.user .bubble :deep(:not(pre) > code) { background: rgba(255,255,255,.18); }
.msg-meta { display: flex; align-items: center; gap: 6px; font-size: 11px; color: var(--m-text-secondary); padding: 0 4px; }
.msg-meta code { background: var(--m-surface-variant); padding: 1px 6px; border-radius: 4px; font-family: 'Roboto Mono', monospace; }
.dot-sep { color: var(--m-text-tertiary); }
.step-summary { display: flex; align-items: center; gap: 5px; padding: 4px 0; font-size: 11px; color: var(--m-text-tertiary); }
.thinking-card { border: 1px dashed var(--m-border-strong); border-radius: var(--m-radius); background: var(--m-bg-soft); font-size: 13px; }
.thinking-card summary { list-style: none; cursor: pointer; display: flex; align-items: center; gap: 6px; padding: 8px 12px; color: var(--m-text-secondary); font-weight: 500; }
.thinking-card summary::-webkit-details-marker { display: none; }
.thinking-card[open] summary { border-bottom: 1px dashed var(--m-border); }
.thinking-body { position: relative; }
.thinking-content { max-height: 200px; overflow-y: auto; padding: 10px 14px; white-space: pre-wrap; word-break: break-word; color: var(--m-text-secondary); line-height: 1.65; font-size: 13px; scrollbar-width: thin; scrollbar-color: var(--m-border-strong) transparent; }
.msg-files { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px; }
.msg-file-chip { display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; background: rgba(255,255,255,.18); border-radius: var(--m-radius-pill); font-size: 11px; }
.msg-file-chip.clickable { cursor: pointer; }
.msg-file-meta { color: rgba(255,255,255,.7); }

/* ===== 增强代码块 ===== */
.code-wrap { margin: 8px 0; border-radius: 10px; overflow: hidden; border: 1px solid var(--m-border); background: var(--m-bg-soft); }
.code-wrap.folded pre { max-height: 260px; overflow: hidden; position: relative; }
.code-wrap.folded pre::after { content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 40px; background: linear-gradient(to bottom, transparent, var(--m-bg-soft)); pointer-events: none; }
.code-wrap:not(.folded) .code-fold { display: none; }
.code-head { display: flex; align-items: center; justify-content: space-between; padding: 6px 12px; background: var(--m-surface-variant); border-bottom: 1px solid var(--m-border); font-size: 12px; }
.code-lang { font-weight: 600; color: var(--m-text-secondary); text-transform: lowercase; }
.code-lang::before { content: '▨ '; opacity: .5; }
.code-actions { display: flex; gap: 6px; }
.code-btn { padding: 2px 8px; font-size: 11px; border: none; border-radius: 4px; background: transparent; color: var(--m-text-secondary); cursor: pointer; }
.code-btn:hover { background: var(--m-bg-soft); color: var(--m-text); }

/* ===== 消息折叠 ===== */
.msg-body-fold { position: relative; max-height: 360px; overflow: hidden; }
.msg-body-fold::after { content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 60px; background: linear-gradient(to bottom, transparent, var(--m-bg-soft)); pointer-events: none; }
.msg-fold-btn { display: block; width: 100%; padding: 8px; font-size: 12px; color: var(--m-primary); background: transparent; border: none; cursor: pointer; text-align: center; }
.msg-fold-btn:hover { background: var(--m-primary-soft); border-radius: 6px; }
</style>
