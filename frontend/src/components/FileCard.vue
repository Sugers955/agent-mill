<template>
  <div class="file-card">
    <div class="file-icon" :style="{ background: iconBg }">
      <el-icon :size="22"><component :is="iconComp" /></el-icon>
    </div>
    <div class="file-meta">
      <div class="file-name" :title="file.name">{{ file.name }}</div>
      <div class="file-info">
        <span>{{ formatSize(file.size) }}</span>
        <span class="dot">·</span>
        <span>{{ shortMime }}</span>
      </div>
    </div>
    <div class="file-actions">
      <button class="action-btn" v-if="canPreview" @click="$emit('preview', file)">
        <el-icon :size="14"><View /></el-icon>
        <span>预览</span>
      </button>
      <a class="action-btn" :href="downloadUrl" :download="file.name">
        <el-icon :size="14"><Download /></el-icon>
        <span>下载</span>
      </a>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ file: { name: string; size?: number; mime?: string; ext?: string; download_url: string; preview_url?: string } }>()
defineEmits<{ (e: 'preview', file: any): void }>()

const PREVIEWABLE = new Set(['html', 'htm', 'pdf', 'md', 'markdown', 'docx', 'txt', 'json', 'csv', 'svg', 'xml', 'js', 'ts', 'css', 'py', 'sql', 'yml', 'yaml'])

const ext = computed(() => {
  const e = (props.file.ext || props.file.name.split('.').pop() || '').toLowerCase().replace(/^\./, '')
  return e
})

const canPreview = computed(() => PREVIEWABLE.has(ext.value))

// Append JWT as ?t= so <a download> (which can't set Authorization) still works.
const downloadUrl = computed(() => {
  const token = localStorage.getItem('access_token') || ''
  const url = props.file.download_url || ''
  if (!url) return ''
  const sep = url.includes('?') ? '&' : '?'
  return token ? `${url}${sep}t=${encodeURIComponent(token)}` : url
})

const iconComp = computed(() => {
  const e = ext.value
  if (['html', 'htm'].includes(e)) return 'Monitor'
  if (e === 'pdf') return 'Document'
  if (['doc', 'docx'].includes(e)) return 'DocumentCopy'
  if (['ppt', 'pptx'].includes(e)) return 'PictureRounded'
  if (['md', 'markdown', 'txt'].includes(e)) return 'Notebook'
  if (['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp'].includes(e)) return 'Picture'
  if (['zip', 'tar', 'gz', '7z'].includes(e)) return 'FolderOpened'
  return 'Files'
})

const iconBg = computed(() => {
  const e = ext.value
  if (['html', 'htm'].includes(e)) return 'linear-gradient(135deg,#fb923c,#f97316)'
  if (e === 'pdf') return 'linear-gradient(135deg,#ef4444,#dc2626)'
  if (['doc', 'docx'].includes(e)) return 'linear-gradient(135deg,#3b82f6,#1d4ed8)'
  if (['ppt', 'pptx'].includes(e)) return 'linear-gradient(135deg,#f59e0b,#d97706)'
  if (['md', 'markdown'].includes(e)) return 'linear-gradient(135deg,#6366f1,#4f46e5)'
  return 'linear-gradient(135deg,#64748b,#475569)'
})

const shortMime = computed(() => {
  const m = props.file.mime || ''
  if (!m) return ext.value.toUpperCase() || 'FILE'
  return m.split('/').pop() || m
})

function formatSize(b?: number): string {
  if (!b && b !== 0) return ''
  if (b < 1024) return `${b} B`
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`
  return `${(b / 1024 / 1024).toFixed(2)} MB`
}
</script>

<style scoped>
.file-card {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 14px;
  background: var(--m-bg-soft);
  border: 1px solid var(--m-border);
  border-radius: var(--m-radius);
  margin: 8px 0;
  transition: border-color .15s, box-shadow .15s;
}
.file-card:hover { border-color: var(--m-border-strong); box-shadow: var(--m-shadow-1); }

.file-icon {
  width: 40px; height: 40px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  color: #fff; flex-shrink: 0;
}

.file-meta { flex: 1; min-width: 0; }
.file-name {
  font-size: 14px; font-weight: 500; color: var(--m-text);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.file-info {
  font-size: 12px; color: var(--m-text-secondary);
  margin-top: 2px;
  display: flex; align-items: center; gap: 6px;
}
.file-info .dot { color: var(--m-text-tertiary); }

.file-actions { display: flex; gap: 4px; flex-shrink: 0; }
.action-btn {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 6px 10px;
  border-radius: var(--m-radius-pill);
  font-size: 12px; font-weight: 500;
  color: var(--m-text-secondary);
  background: transparent;
  border: none;
  cursor: pointer;
  text-decoration: none;
  transition: background .15s, color .15s;
}
.action-btn:hover { background: var(--m-surface-variant); color: var(--m-primary); }
</style>
