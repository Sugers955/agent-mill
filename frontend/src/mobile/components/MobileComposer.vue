<template>
  <div class="composer-wrap">
    <div v-if="pendingFiles.length" class="files-row">
      <div v-for="f in pendingFiles" :key="f.id" :class="['file-chip', f.parse_status]">
        <span class="chip-name">{{ f.name }}</span>
        <span v-if="f.parse_status === 'parsing'" class="chip-meta">解析中…</span>
        <span v-else-if="f.parse_status === 'done'" class="chip-meta">{{ f.parsed_chars }} 字</span>
        <span v-else-if="f.parse_status === 'skipped'" class="chip-meta">原始文件</span>
        <span v-else-if="f.parse_status === 'failed'" class="chip-meta err">解析失败</span>
        <button class="chip-close" @click="$emit('remove-file', f)" aria-label="移除">×</button>
      </div>
    </div>
    <div class="composer">
      <button class="icon-btn" :disabled="!hasAgent" @click="$emit('trigger-upload')" aria-label="上传文件">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>
      </button>
      <input ref="fileInputRef" type="file" multiple style="display:none" @change="$emit('file-pick', $event)" />
      <textarea
        :value="modelValue"
        ref="textareaRef"
        rows="1"
        :placeholder="hasAgent ? '发送消息…' : '请联系管理员授权数字员工'"
        :disabled="disabled || !hasAgent"
        @input="$emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
        @keydown.enter.exact.prevent="$emit('send')"
      />
      <button v-if="sending" class="stop-btn" aria-label="停止生成" @click="$emit('stop-stream')">
        <svg class="stop-spin" viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><path d="M12 2a10 10 0 0 1 10 10h-2a8 8 0 0 0-8-8V2z" opacity=".9"/><path d="M12 2a10 10 0 0 0-10 10h2a8 8 0 0 1 8-8V2z" opacity=".25"/></svg>
      </button>
      <button v-else class="send-btn" :disabled="!modelValue.trim() || !hasAgent" @click="$emit('send')" aria-label="发送">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'

const props = defineProps<{
  modelValue: string
  disabled: boolean
  sending: boolean
  hasAgent: boolean
  pendingFiles: any[]
}>()

defineEmits<{
  'update:modelValue': [value: string]
  'send': []
  'stop-stream': []
  'trigger-upload': []
  'file-pick': [event: Event]
  'remove-file': [file: any]
}>()

const textareaRef = ref<HTMLTextAreaElement | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)

// 自动调整高度
watch(() => props.modelValue, () => {
  nextTick(() => {
    const el = textareaRef.value
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 140) + 'px'
  })
})

// 暴露 fileInputRef 给父组件
defineExpose({
  fileInputRef,
  textareaRef
})
</script>

<style scoped>
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
  font-size: 14px;
  max-width: 220px;
  box-shadow: var(--m-shadow-1);
}
.file-chip.parsing { background: var(--m-primary-soft); }
.file-chip.failed { background: var(--m-danger-soft, #fee2e2); }
.chip-name {
  max-width: 110px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  font-weight: 500; color: var(--m-text);
}
.chip-meta { color: var(--m-text-secondary); font-size: 14px; }
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
  font-size: 16px; line-height: 1.4;
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
.stop-btn {
  width: 36px; height: 36px; border-radius: 50%;
  background: transparent; color: var(--m-text-secondary, #80868b);
  display: inline-flex; align-items: center; justify-content: center;
  flex-shrink: 0; border: none; cursor: pointer;
  transition: background .15s, color .15s;
}
.stop-btn:active { transform: scale(.93); background: var(--m-surface-variant, #e8eaed); }
.stop-spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>