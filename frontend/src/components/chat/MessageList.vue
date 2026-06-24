<template>
  <div class="msg-list" ref="listRef" role="log" aria-live="polite">
    <template v-for="msg in messages" :key="msg.id">
      <!-- 用户消息 -->
      <div v-if="msg.role === 'user'" class="msg-row msg-user" role="article" aria-label="用户消息">
        <div class="msg-bubble user-bubble">{{ msg.content }}</div>
      </div>

      <!-- 助手消息 -->
      <div v-else class="msg-row msg-assistant" role="article" :aria-label="`来自${msg.agent_name || '助手'}的消息`">
        <div class="msg-meta" v-if="msg.agent_name || msg.model_id">
          <img v-if="msg.agent_avatar" class="msg-avatar" :src="msg.agent_avatar" :alt="msg.agent_name" />
          <span class="msg-agent">{{ msg.agent_name || '助手' }}</span>
          <span class="msg-model" v-if="msg.model_provider">{{ msg.model_provider }}</span>
        </div>

        <!-- 思考过程 -->
        <details class="thinking-card" v-if="msg.thinking" @toggle="onToggleThinking($event, msg.id)">
          <summary class="thinking-summary"><span class="thinking-dot" /> 思考过程</summary>
          <div class="thinking-content">{{ msg.thinking }}</div>
        </details>

        <!-- 工具步骤 -->
        <div class="step-list" v-if="msg.steps?.length">
          <StepCard v-for="(step, i) in msg.steps" :key="i" :step="step" />
        </div>

        <!-- 消息内容 -->
        <div v-if="msg.content" class="msg-bubble assistant-bubble" v-html="renderMarkdown(msg.content)" />

        <!-- 操作栏 -->
        <div class="msg-actions" v-if="!compact">
          <button class="action-btn" @click="$emit('copy', msg.content)" aria-label="复制回复" title="复制">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
          </button>
          <button class="action-btn" @click="$emit('toggle-fav', msg.id)" :aria-label="msg.favorite ? '取消收藏' : '收藏'" title="收藏">
            <svg width="14" height="14" viewBox="0 0 24 24" :fill="msg.favorite ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
          </button>
          <button class="action-btn" @click="$emit('feedback', msg.id, 'like')" :class="{ active: msg.feedback === 'like' }" aria-label="点赞" title="有用">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg>
          </button>
          <button class="action-btn" @click="$emit('feedback', msg.id, 'dislike')" :class="{ active: msg.feedback === 'dislike' }" aria-label="点踩" title="无用">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/></svg>
          </button>
        </div>
      </div>
    </template>

    <!-- 加载动画 -->
    <div class="msg-row" v-if="loading">
      <div class="thinking-pill">
        <span class="thinking-dot" />
        <span class="bounce-dot" />
        <span class="bounce-dot" />
        <span class="bounce-dot" />
      </div>
    </div>

    <div ref="anchorRef" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { ChatMessage } from '@/shared/types/chat'
import StepCard from './StepCard.vue'

defineProps<{
  messages: ChatMessage[]
  loading?: boolean
  compact?: boolean
}>()

defineEmits<{
  copy: [text: string]
  'toggle-fav': [msgId: string]
  feedback: [msgId: string, type: 'like' | 'dislike']
}>()

const listRef = ref<HTMLElement | null>(null)
const anchorRef = ref<HTMLElement | null>(null)

function scrollToBottom() {
  anchorRef.value?.scrollIntoView({ behavior: 'smooth' })
}

function onToggleThinking(_e: Event, _msgId: string) {
  // 允许折叠/展开思考过程，无需额外逻辑
}

function renderMarkdown(text: string): string {
  if (!text) return ''
  let html = text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  const codeFenceCount = (html.match(/```/g) || []).length
  if (codeFenceCount % 2 !== 0) html += '\n```'
  html = html
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code class="language-$1">$2</code></pre>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*(\S[^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br/>')
  return html
}

defineExpose({ scrollToBottom })
</script>

<style scoped>
.msg-list { flex: 1; overflow-y: auto; padding: 16px 24px; display: flex; flex-direction: column; gap: 8px; }
.msg-row { display: flex; flex-direction: column; }
.msg-user { align-items: flex-end; }
.msg-assistant { align-items: flex-start; }
.msg-bubble {
  max-width: 72%; padding: 10px 16px; border-radius: var(--m-radius);
  font-size: 14px; line-height: 1.6; word-break: break-word;
}
.user-bubble {
  background: var(--m-primary); color: var(--m-on-primary);
  border-bottom-right-radius: 4px;
}
.assistant-bubble {
  background: var(--m-surface); border: 1px solid var(--m-border);
  border-bottom-left-radius: 4px;
}
.msg-avatar { width: 24px; height: 24px; border-radius: 50%; object-fit: cover; }
.msg-meta { display: flex; align-items: center; gap: 6px; margin: 4px 0; font-size: 12px; color: var(--m-text-secondary); }
.msg-agent { font-weight: 500; }
.msg-model { color: var(--m-text-tertiary); }
.msg-actions { display: flex; gap: 2px; padding: 4px 0; opacity: 0; transition: opacity .15s; }
.msg-assistant:hover .msg-actions { opacity: 1; }
.action-btn {
  display: flex; align-items: center; justify-content: center;
  width: 28px; height: 28px; border: none; border-radius: var(--m-radius-sm);
  background: transparent; color: var(--m-text-tertiary); cursor: pointer;
}
.action-btn:hover { background: var(--m-surface-variant); color: var(--m-text-secondary); }
.action-btn.active { color: var(--m-primary); }
.thinking-card {
  border: 1px solid var(--m-border); border-radius: var(--m-radius-sm);
  margin: 6px 0; background: var(--m-surface-variant); overflow: hidden;
}
.thinking-summary {
  padding: 6px 12px; font-size: 12px; color: var(--m-text-secondary);
  cursor: pointer; user-select: none;
}
.thinking-content { padding: 6px 12px 10px; font-size: 12px; color: var(--m-text-tertiary); line-height: 1.5; white-space: pre-wrap; }
.thinking-dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: var(--m-primary); margin-right: 6px; vertical-align: middle; }
.thinking-pill {
  display: flex; align-items: center; gap: 4px;
  padding: 10px 16px; background: var(--m-surface); border: 1px solid var(--m-border);
  border-radius: var(--m-radius-pill);
}
.bounce-dot {
  width: 6px; height: 6px; border-radius: 50%; background: var(--m-text-tertiary);
  animation: bounce 1.4s infinite both;
}
.bounce-dot:nth-child(2) { animation-delay: .2s; }
.bounce-dot:nth-child(3) { animation-delay: .4s; }
.bounce-dot:nth-child(4) { animation-delay: .6s; }
@keyframes bounce { 0%,80%,100% { transform: translateY(0); } 40% { transform: translateY(-6px); } }

@media (max-width: 768px) {
  .msg-list { padding: 12px; }
  .msg-bubble { max-width: 90%; font-size: 15px; }
}
</style>
