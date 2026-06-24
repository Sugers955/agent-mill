<template>
  <div class="chat-tab">
    <div class="chat-layout">
      <!-- 侧边栏 - 当前员工信息 -->
      <aside class="chat-sidebar">
        <div v-if="chat.currentAgent" class="sidebar-agent">
          <div class="sa-top">
            <div class="sa-avatar" :style="{ background: agentGradient(chat.currentAgent) }">
              <img v-if="chat.currentAgent.icon_url" :src="chat.currentAgent.icon_url" />
              <span v-else>{{ chat.currentAgent.name?.charAt(0) }}</span>
            </div>
            <div class="sa-info">
              <div class="sa-name">{{ chat.currentAgent.name }}</div>
              <div class="sa-status" :class="agentStatus">
                <span class="sa-dot" />
                {{ agentStatus === 'working' ? '工作中' : agentStatus === 'idle' ? '空闲' : '离线' }}
              </div>
            </div>
          </div>
          <div v-if="currentTaskName" class="sa-task">
            <svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="8" r="6"/><path d="M8 4v4l3 2"/></svg>
            {{ currentTaskName }}
          </div>
          <div class="sa-meta">
            <div class="sa-meta-item">
              <span class="sa-meta-label">模型</span>
              <span class="sa-meta-val">{{ chat.currentAgent.model_id || '--' }}</span>
            </div>
            <div class="sa-meta-item">
              <span class="sa-meta-label">已对话</span>
              <span class="sa-meta-val">{{ chat.convs.filter(c => c.agent_id === chat.currentAgent?.id).length }} 次</span>
            </div>
          </div>
          <div class="sa-actions">
            <el-button size="small" text @click="startNewChat">
              <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M8 3v10M3 8h10"/></svg>
              新建对话
            </el-button>
          </div>
        </div>
        <div v-else class="sidebar-empty">
          <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" stroke-width="1.2" opacity="0.3">
            <circle cx="12" cy="8" r="4"/><path d="M5 20c0-3.866 3.134-7 7-7s7 3.134 7 7"/>
          </svg>
          <p>请先选择<br />数字员工</p>
        </div>
      </aside>

      <!-- 主聊天区域 -->
      <main class="chat-main">
        <div ref="scrollRef" class="cm-messages">
          <!-- 未选择员工 -->
          <div v-if="!chat.currentAgent" class="cm-welcome">
            <div class="cm-welcome-icon">
              <svg viewBox="0 0 80 80" width="80" height="80" fill="none">
                <circle cx="40" cy="28" r="12" stroke="currentColor" stroke-width="1.2" opacity="0.2" />
                <path d="M20 68c0-11.046 8.954-20 20-20s20 8.954 20 20" stroke="currentColor" stroke-width="1.2" opacity="0.2" />
                <rect x="28" y="44" width="24" height="16" rx="4" stroke="currentColor" stroke-width="1.2" opacity="0.15" />
                <animateTransform attributeName="transform" type="rotate" from="0 40 40" to="360 40 40" dur="20s" repeatCount="indefinite" />
              </svg>
            </div>
            <h2 class="cm-welcome-title">指挥中心</h2>
            <p class="cm-welcome-desc">从工位看板选择一位数字员工开始对话</p>
          </div>

          <!-- 新对话欢迎（已选员工） -->
          <div v-else-if="chat.messages.length === 0 && !chat.currentConvId" class="cm-welcome-agent">
            <div class="cm-wa-avatar" :style="{ background: agentGradient(chat.currentAgent) }">
              <img v-if="chat.currentAgent.icon_url" :src="chat.currentAgent.icon_url" />
              <span v-else>{{ chat.currentAgent.name?.charAt(0) }}</span>
            </div>
            <h3 class="cm-wa-name">{{ chat.currentAgent.name }}</h3>
            <p class="cm-wa-desc">{{ chat.currentAgent.description || '开始一段新对话' }}</p>
            <div class="cm-wa-starters" v-if="starterItems.length">
              <button v-for="s in starterItems" :key="s.label"
                class="cm-starter-btn" @click="useStarter(s.query)">
                <svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M8 3v10M3 8h10"/></svg>
                {{ s.label }}
              </button>
            </div>
          </div>

          <!-- 对话消息 -->
          <template v-else>
            <div v-for="m in chat.messages" :key="m.id || m._tmp" :class="['cm-msg', m.role]">
              <div v-if="m.role === 'assistant'" class="cm-msg-avatar" :style="{ background: agentGradient(chat.currentAgent?.id || 0) }">
                <img v-if="chat.currentAgent?.icon_url" :src="chat.currentAgent.icon_url" />
                <span>{{ chat.currentAgent?.name?.charAt(0) }}</span>
              </div>

              <div class="cm-msg-body">
                <div v-if="isWaiting(m)" class="cm-thinking">
                  <span class="cm-thinking-dots">
                    <span /><span /><span />
                  </span>
                  <span>思考中</span>
                </div>

                <details v-if="m.content_json?.thinking || m._thinking" class="cm-thinking-card" :open="m._thinkingOpen ?? !m.content_json?.text">
                  <summary>
                    <svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="8" cy="8" r="6"/><path d="M8 5v4M8 11.5"/></svg>
                    思考过程
                    <span class="cm-tc-muted">{{ (m.content_json?.thinking || m._thinking || '').length }} 字</span>
                  </summary>
                  <div class="cm-thinking-body">{{ m.content_json?.thinking || m._thinking }}</div>
                </details>

                <div v-if="m._steps?.length || m.tool_calls_json?.trace?.length" class="cm-steps">
                  <StepCard v-for="(s, i) in (m._steps || normalizeTrace(m.tool_calls_json?.trace))" :key="i" :step="s" />
                </div>

                <div v-if="m.content_json?.text || m.role === 'user'" class="cm-bubble" :class="m.role">
                  <div class="cm-bubble-text" v-html="md.render(m.content_json?.text || '')"></div>
                </div>

                <div class="cm-msg-footer">
                  <span v-if="m.created_at" class="cm-time">{{ formatTime(m.created_at) }}</span>
                  <div v-if="m.role === 'assistant' && m.content_json?.text && !m._streaming" class="cm-actions">
                    <button class="cm-action-btn" @click="copyAnswer(m)" title="复制">
                      <svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><rect x="4" y="2" width="10" height="12" rx="1"/><path d="M2 6v8a1 1 0 001 1h7"/></svg>
                      复制
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </template>
        </div>

        <!-- 输入区 -->
        <div class="cm-input-area">
          <ComposerInput
            :files="[]"
            :sending="sending"
            :suggestions="starterItems.map(s => s.label)"
            @send="onSend"
            @stop="stopStream"
          />
        </div>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { useChat } from '@/stores/chat'
import MarkdownIt from 'markdown-it'
import ComposerInput from '@/components/chat/ComposerInput.vue'
import StepCard from '@/components/chat/StepCard.vue'
import { normalizeTrace, plainTextFromMarkdown, agentGradient } from '@/shared/constants'
import { useChatStream } from '@/composables/useChatStream'
import type { StarterItem } from '@/shared/types/chat'

const md = new MarkdownIt({ breaks: true, linkify: true })
const chat = useChat()
const input = ref('')
const scrollRef = ref<HTMLElement | null>(null)

const { sending, streamAbortController, send: streamSend, isWaiting } = useChatStream({
  chatStore: chat,
  scrollBottom: async () => {
    await nextTick()
    const el = scrollRef.value
    if (!el) return
    const threshold = 120
    if (el.scrollHeight - el.scrollTop - el.clientHeight > threshold) return
    el.scrollTop = el.scrollHeight
  },
  input,
  onAfterSend: (text) => {
    if (chat.currentConvId) {
      const conv = chat.convs.find((c: any) => c.id === chat.currentConvId)
      if (conv) {
        const title = text.replace(/\s+/g, ' ').trim().slice(0, 30)
        if (title && title !== conv.title) chat.renameConv(conv, title).catch(() => {})
      }
    }
  },
})

const agentStatus = computed<'working' | 'idle' | 'offline'>(() => sending.value ? 'working' : 'idle')
const currentTaskName = computed(() => sending.value ? '正在对话...' : null)

const starterItems = computed<StarterItem[]>(() => {
  const desc = chat.currentAgent?.description || ''
  if (!desc) return []
  const re = /^\s*(?:[-•*]|\d+[.、])\s+(.+)$/
  return desc.split(/\r?\n/).map(l => l.match(re)).filter(Boolean).map(m => ({ label: m![1].trim(), query: m![1].trim() })).slice(0, 4)
})

onMounted(async () => { if (!chat.loaded) await chat.loadInit() })

function onSend(text: string) {
  if (!chat.currentAgent) { ElMessage.warning('请先选择数字员工'); return }
  input.value = text
  streamSend()
}

function useStarter(q: string) { if (!q || sending.value || !chat.currentAgent) return; onSend(q) }
function stopStream() { streamAbortController.value?.abort() }

function startNewChat() {
  chat.currentConvId = null
  chat.messages = []
  chat.pendingFiles = []
}

function formatTime(ts: string): string {
  const d = new Date(ts)
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function copyAnswer(m: any) {
  const mid = m.id || m._tmp
  if (mid) {
    const el = document.querySelector(`.msg[data-mid="${mid}"] .bubble-stack`)
    if (el) {
      const html = el.innerHTML
      try {
        await navigator.clipboard.writeText(html.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim())
        ElMessage.success('已复制')
        return
      } catch {}
    }
  }
  const text = m.content_json?.text || ''
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制')
  } catch { ElMessage.error('复制失败') }
}
</script>

<style scoped>
.chat-tab { height: 100%; display: flex; flex-direction: column; }
.chat-layout { display: flex; height: 100%; gap: 16px; }

/* sidebar */
.chat-sidebar {
  width: 220px; flex-shrink: 0;
  display: flex; flex-direction: column;
}
.sidebar-agent {
  background: var(--m-surface);
  border: 1px solid var(--m-border);
  border-radius: 12px;
  padding: 16px;
  display: flex; flex-direction: column; gap: 14px;
}
.sa-top { display: flex; align-items: center; gap: 12px; }
.sa-avatar {
  width: 44px; height: 44px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-size: 16px; font-weight: 600; flex-shrink: 0;
}
.sa-avatar img { width: 100%; height: 100%; border-radius: 50%; object-fit: cover; }
.sa-info { display: flex; flex-direction: column; gap: 3px; }
.sa-name { font-size: 15px; font-weight: 600; color: var(--m-text); }
.sa-status {
  display: flex; align-items: center; gap: 5px; font-size: 12px;
  color: var(--m-text-secondary);
}
.sa-dot { width: 7px; height: 7px; border-radius: 50%; }
.sa-status.working .sa-dot { background: var(--m-success); animation: sa-pulse 1.2s ease-in-out infinite; }
.sa-status.idle .sa-dot { background: var(--m-text-tertiary); }
@keyframes sa-pulse { 0%, 100% { box-shadow: 0 0 0 0 var(--m-success-soft); } 50% { box-shadow: 0 0 0 4px transparent; } }

.sa-task { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--m-primary); padding: 6px 10px; background: var(--m-primary-soft); border-radius: 8px; }
.sa-meta { display: flex; flex-direction: column; gap: 6px; }
.sa-meta-item { display: flex; justify-content: space-between; font-size: 12px; }
.sa-meta-label { color: var(--m-text-tertiary); }
.sa-meta-val { color: var(--m-text); font-weight: 500; }
.sa-actions { display: flex; gap: 8px; }

.sidebar-empty {
  flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 10px; color: var(--m-text-tertiary); font-size: 13px; text-align: center; line-height: 1.5;
}

/* main */
.chat-main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.cm-messages { flex: 1; overflow-y: auto; padding: 8px 0; display: flex; flex-direction: column; gap: 6px; scroll-behavior: smooth; }

/* welcome */
.cm-welcome { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; gap: 12px; text-align: center; }
.cm-welcome-icon { opacity: 0.35; }
.cm-welcome-title { margin: 0; font-size: 22px; font-weight: 600; color: var(--m-text); }
.cm-welcome-desc { margin: 0; font-size: 13px; color: var(--m-text-tertiary); }

.cm-welcome-agent { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; gap: 10px; text-align: center; padding: 24px; }
.cm-wa-avatar { width: 56px; height: 56px; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 22px; font-weight: 600; box-shadow: 0 4px 16px rgba(0,0,0,0.1); }
.cm-wa-avatar img { width: 100%; height: 100%; border-radius: 50%; object-fit: cover; }
.cm-wa-name { margin: 0; font-size: 18px; font-weight: 600; color: var(--m-text); }
.cm-wa-desc { margin: 0; font-size: 13px; color: var(--m-text-secondary); }
.cm-wa-starters { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-top: 8px; }
.cm-starter-btn {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 8px 16px; border: 1px solid var(--m-border); border-radius: 20px;
  background: var(--m-surface); font-size: 12px; color: var(--m-text-secondary);
  cursor: pointer; transition: all 0.2s;
}
.cm-starter-btn:hover { border-color: var(--m-primary); color: var(--m-primary); background: var(--m-primary-soft); }

/* messages */
.cm-msg { display: flex; gap: 10px; padding: 4px 0; animation: msgIn 0.2s ease; }
@keyframes msgIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
.cm-msg.user { flex-direction: row-reverse; }
.cm-msg-avatar { width: 30px; height: 30px; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 12px; font-weight: 600; flex-shrink: 0; margin-top: 2px; }
.cm-msg-avatar img { width: 100%; height: 100%; border-radius: 50%; object-fit: cover; }
.cm-msg-body { display: flex; flex-direction: column; gap: 6px; flex: 1; max-width: 75%; }
.cm-msg.user .cm-msg-body { align-items: flex-end; }

/* thinking */
.cm-thinking { display: inline-flex; align-items: center; gap: 8px; padding: 6px 14px; background: var(--m-primary-soft); border-radius: 20px; font-size: 12px; color: var(--m-primary); width: fit-content; }
.cm-thinking-dots { display: inline-flex; gap: 3px; }
.cm-thinking-dots span { width: 5px; height: 5px; border-radius: 50%; background: var(--m-primary); animation: td-bounce 1.2s ease-in-out infinite; }
.cm-thinking-dots span:nth-child(2) { animation-delay: .15s; }
.cm-thinking-dots span:nth-child(3) { animation-delay: .3s; }
@keyframes td-bounce { 0%, 80%, 100% { opacity: .3; transform: translateY(0); } 40% { opacity: 1; transform: translateY(-3px); } }

/* thinking card */
.cm-thinking-card { border: 1px dashed var(--m-border-strong); border-radius: 10px; background: var(--m-bg-soft); overflow: hidden; }
.cm-thinking-card summary { display: flex; align-items: center; gap: 6px; padding: 8px 12px; cursor: pointer; font-size: 12px; color: var(--m-text-secondary); list-style: none; }
.cm-thinking-card summary::-webkit-details-marker { display: none; }
.cm-thinking-card[open] summary { border-bottom: 1px dashed var(--m-border); }
.cm-tc-muted { color: var(--m-text-tertiary); font-size: 11px; margin-left: auto; }
.cm-thinking-body { padding: 10px 14px; font-size: 12px; color: var(--m-text-secondary); white-space: pre-wrap; max-height: 160px; overflow-y: auto; line-height: 1.6; }

/* steps */
.cm-steps { display: flex; flex-direction: column; gap: 4px; }

/* bubble */
.cm-bubble { padding: 10px 14px; border-radius: 12px; font-size: 14px; line-height: 1.6; word-break: break-word; }
.cm-bubble.assistant { background: var(--m-bg-soft); border: 1px solid var(--m-border); }
.cm-bubble.user { background: var(--m-primary); color: #fff; }
.cm-bubble-text :deep(p) { margin: 4px 0; }
.cm-bubble-text :deep(p:first-child) { margin-top: 0; }
.cm-bubble-text :deep(p:last-child) { margin-bottom: 0; }

/* footer */
.cm-msg-footer { display: flex; align-items: center; gap: 8px; padding: 0 4px; }
.cm-time { font-size: 11px; color: var(--m-text-tertiary); }
.cm-actions { display: flex; gap: 4px; opacity: 0; transition: opacity 0.15s; }
.cm-msg:hover .cm-actions { opacity: 1; }
.cm-action-btn {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 8px; font-size: 11px; color: var(--m-text-secondary);
  background: transparent; border: none; border-radius: 6px; cursor: pointer;
}
.cm-action-btn:hover { background: var(--m-surface-variant); }

/* input */
.cm-input-area { padding-top: 12px; border-top: 1px solid var(--m-border); margin-top: 8px; }
</style>
