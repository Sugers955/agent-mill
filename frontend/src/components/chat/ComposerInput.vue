<template>
  <div class="composer" style="position:relative">
    <!-- 斜杠菜单浮层 -->
    <div v-if="slashVisible" class="slash-menu">
      <div
        v-for="(s, i) in filteredSuggestions" :key="i"
        class="slash-item"
        :class="{ active: slashSelected === i }"
        @click="applySuggestion(s)"
        @mouseenter="slashSelected = i"
      >
        {{ s }}
      </div>
      <div v-if="!filteredSuggestions.length" class="slash-item muted">无匹配模板</div>
    </div>

    <div class="file-chips" v-if="files.length">
      <div class="file-chip" v-for="f in files" :key="f.id">
        <span class="file-name">{{ f.name }}</span>
        <span class="file-status" :class="f.status">{{ statusLabel(f.status) }}</span>
        <button class="file-remove" @click="$emit('remove-file', f.id)" aria-label="删除文件">×</button>
      </div>
    </div>

    <div class="composer-inner">
      <button class="attach-btn" @click="onAttach" aria-label="上传文件" title="上传文件">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>
      </button>
      <textarea
        ref="taRef"
        class="composer-textarea"
        v-model="text"
        :placeholder="sending ? '请等待回复...' : '输入消息...'"
        :disabled="sending"
        rows="1"
        @keydown="onKeydown"
        @keydown.enter.exact.prevent="onSendOrSelect"
        @input="onInput"
        aria-label="输入消息"
      />
      <button
        v-if="sending"
        class="send-btn stop-btn"
        @click="$emit('stop')"
        aria-label="停止生成"
        title="停止"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>
      </button>
      <button
        v-else
        class="send-btn"
        :disabled="!text.trim()"
        @click="onSend"
        aria-label="发送消息"
        title="发送"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { UploadFile } from '@/shared/types/chat'

const props = defineProps<{
  files?: UploadFile[]
  sending?: boolean
  suggestions?: string[]
}>()

const emit = defineEmits<{
  send: [text: string]
  stop: []
  'add-file': [file: File]
  'remove-file': [fileId: string]
}>()

const text = ref('')
const taRef = ref<HTMLTextAreaElement | null>(null)
const slashVisible = ref(false)
const slashSelected = ref(0)
const slashFilter = ref('')

const filteredSuggestions = computed(() => {
  if (!slashVisible.value) return []
  const list = props.suggestions || []
  if (!slashFilter.value) return list
  return list.filter(s => s.includes(slashFilter.value))
})

watch(text, (val) => {
  if (val.startsWith('/')) {
    slashFilter.value = val.slice(1)
    slashVisible.value = true
    slashSelected.value = 0
  } else if (slashVisible.value && !val.startsWith('/')) {
    slashVisible.value = false
  }
})

function applySuggestion(s: string) {
  text.value = s
  slashVisible.value = false
  autoResize()
  taRef.value?.focus()
}

function onInput() {
  autoResize()
}

function onKeydown(e: KeyboardEvent) {
  if (!slashVisible.value) return
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    slashSelected.value = Math.min(slashSelected.value + 1, filteredSuggestions.value.length - 1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    slashSelected.value = Math.max(slashSelected.value - 1, 0)
  } else if (e.key === 'Escape') {
    e.preventDefault()
    slashVisible.value = false
  }
}

function onSendOrSelect() {
  if (slashVisible.value && filteredSuggestions.value.length > 0) {
    applySuggestion(filteredSuggestions.value[slashSelected.value])
  } else {
    onSend()
  }
}

function onSend() {
  const t = text.value.trim()
  if (!t) return
  slashVisible.value = false
  emit('send', t)
  text.value = ''
  autoResize()
}

function autoResize() {
  const ta = taRef.value
  if (!ta) return
  ta.style.height = 'auto'
  ta.style.height = Math.min(ta.scrollHeight, 160) + 'px'
}

function onAttach() {
  const input = document.createElement('input')
  input.type = 'file'
  input.multiple = true
  input.onchange = () => {
    if (input.files) {
      Array.from(input.files).forEach(f => emit('add-file', f))
    }
  }
  input.click()
}

function statusLabel(s: string): string {
  const map: Record<string, string> = { uploading: '上传中...', parsing: '解析中...', ready: '就绪', error: '失败' }
  return map[s] || s
}
</script>

<style scoped>
.composer { border-top: 1px solid var(--m-border); padding: 12px 16px; background: var(--m-surface); }

.slash-menu {
  position: absolute; bottom: 100%; left: 16px; right: 16px;
  z-index: 100; max-height: 240px; overflow-y: auto;
  background: var(--m-surface); border: 1px solid var(--m-border);
  border-radius: var(--m-radius); box-shadow: var(--m-shadow-3);
  margin-bottom: 4px; padding: 4px 0;
}
.slash-item {
  padding: 8px 14px; font-size: 13px; color: var(--m-text); cursor: pointer;
}
.slash-item:hover, .slash-item.active { background: var(--m-primary-soft); color: var(--m-primary); }
.slash-item.muted { color: var(--m-text-tertiary); cursor: default; }

.file-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
.file-chip {
  display: flex; align-items: center; gap: 6px;
  padding: 4px 8px; background: var(--m-surface-variant);
  border-radius: var(--m-radius-sm); font-size: 12px;
}
.file-name { color: var(--m-text); max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-status { font-size: 11px; }
.file-status.ready { color: var(--m-success); }
.file-status.uploading, .file-status.parsing { color: var(--m-warning); }
.file-status.error { color: var(--m-danger); }
.file-remove { border: none; background: none; cursor: pointer; color: var(--m-text-tertiary); font-size: 16px; padding: 0 2px; }
.file-remove:hover { color: var(--m-danger); }
.composer-inner { display: flex; align-items: flex-end; gap: 8px; }
.attach-btn {
  display: flex; align-items: center; justify-content: center;
  width: 36px; height: 36px; border: none; border-radius: 50%;
  background: transparent; color: var(--m-text-tertiary); cursor: pointer; flex-shrink: 0;
}
.attach-btn:hover { background: var(--m-surface-variant); color: var(--m-text-secondary); }
.composer-textarea {
  flex: 1; border: none; outline: none; resize: none;
  font-family: inherit; font-size: 14px; line-height: 1.5;
  min-height: 24px; max-height: 160px;
  background: transparent; color: var(--m-text);
}
.composer-textarea::placeholder { color: var(--m-text-tertiary); }
.send-btn {
  display: flex; align-items: center; justify-content: center;
  width: 36px; height: 36px; border: none; border-radius: 50%;
  background: var(--m-primary); color: var(--m-on-primary); cursor: pointer; flex-shrink: 0;
  transition: background .15s;
}
.send-btn:hover { background: var(--m-primary-hover); }
.send-btn:disabled { opacity: .4; cursor: not-allowed; }
.stop-btn { background: var(--m-danger); }
.stop-btn:hover { background: #b3261e; }
</style>
