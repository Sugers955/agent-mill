<template>
  <aside class="preview-panel">
    <div class="preview-head">
      <div class="head-left">
        <el-icon :size="18"><component :is="iconComp" /></el-icon>
        <span class="file-name" :title="file?.name">{{ file?.name || '预览' }}</span>
      </div>
      <div class="head-right">
        <a class="head-btn" :href="tokenizedUrl" :download="file?.name" title="下载">
          <el-icon :size="16"><Download /></el-icon>
        </a>
        <button class="head-btn" @click="openInNewTab" title="新窗口打开">
          <el-icon :size="16"><Promotion /></el-icon>
        </button>
        <button class="head-btn" @click="$emit('close')" title="关闭">
          <el-icon :size="16"><Close /></el-icon>
        </button>
      </div>
    </div>
    <div class="preview-body">
      <div v-if="loading" class="state">
        <el-icon :size="22" class="spin"><Loading /></el-icon>
        <span>加载中...</span>
      </div>
      <div v-else-if="error" class="state error">
        <el-icon :size="22"><WarningFilled /></el-icon>
        <span>{{ error }}</span>
      </div>

      <!-- HTML: iframe sandbox (loaded via blob URL so auth header works) -->
      <iframe
        v-else-if="kind === 'html' && blobUrl"
        class="renderer-frame"
        sandbox="allow-scripts allow-popups"
        :src="blobUrl"
      />

      <!-- PDF: native browser viewer (blob URL) -->
      <iframe
        v-else-if="kind === 'pdf' && blobUrl"
        class="renderer-frame"
        :src="blobUrl"
      />

      <!-- SVG: render inline -->
      <div v-else-if="kind === 'svg' && textContent" class="svg-body" v-html="textContent"></div>

      <!-- Markdown: render with markdown-it -->
      <div v-else-if="kind === 'md'" class="md-body" v-html="mdHtml"></div>

      <!-- DOCX: docx-preview library -->
      <div v-else-if="kind === 'docx'" ref="docxRef" class="docx-body"></div>

      <!-- Plain text / code -->
      <pre v-else-if="kind === 'text'" class="text-body">{{ textContent }}</pre>

      <!-- Image -->
      <div v-else-if="kind === 'image' && blobUrl" class="image-body">
        <img :src="blobUrl" :alt="file?.name" />
      </div>

      <!-- Unsupported -->
      <div v-else class="state">
        <el-icon :size="22"><InfoFilled /></el-icon>
        <span>该文件类型不支持预览,请下载查看</span>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import MarkdownIt from 'markdown-it'

const props = defineProps<{ file: any | null }>()
defineEmits<{ (e: 'close'): void }>()

const md = new MarkdownIt({ breaks: true, linkify: true, html: false })

const loading = ref(false)
const error = ref('')
const textContent = ref('')
const mdHtml = ref('')
const blobUrl = ref<string>('')
const docxRef = ref<HTMLDivElement | null>(null)

const ext = computed(() => {
  if (!props.file) return ''
  return (props.file.ext || (props.file.name || '').split('.').pop() || '').toLowerCase().replace(/^\./, '')
})

const kind = computed<'html' | 'pdf' | 'md' | 'docx' | 'text' | 'image' | 'svg' | 'other'>(() => {
  const e = ext.value
  if (['html', 'htm'].includes(e)) return 'html'
  if (e === 'pdf') return 'pdf'
  if (['md', 'markdown'].includes(e)) return 'md'
  if (e === 'docx') return 'docx'
  if (e === 'svg') return 'svg'
  if (['txt', 'json', 'csv', 'xml', 'js', 'ts', 'css', 'py', 'sql', 'yml', 'yaml', 'sh', 'log'].includes(e)) return 'text'
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'].includes(e)) return 'image'
  return 'other'
})

const iconComp = computed(() => {
  const k = kind.value
  if (k === 'html') return 'Monitor'
  if (k === 'pdf') return 'Document'
  if (k === 'md') return 'Notebook'
  if (k === 'docx') return 'DocumentCopy'
  if (k === 'image') return 'Picture'
  return 'Files'
})

watch(() => props.file?.download_url, async (url) => {
  // revoke any stale blob
  if (blobUrl.value) { URL.revokeObjectURL(blobUrl.value); blobUrl.value = '' }
  if (!url || !props.file) return
  error.value = ''
  textContent.value = ''
  mdHtml.value = ''
  loading.value = true
  try {
    const r = await fetch(url, { headers: getAuthHeader() })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    const k = kind.value
    if (k === 'md' || k === 'text' || k === 'svg') {
      const txt = await r.text()
      textContent.value = txt
      if (k === 'md') mdHtml.value = md.render(txt)
    } else if (k === 'html' || k === 'pdf' || k === 'image') {
      const blob = await r.blob()
      blobUrl.value = URL.createObjectURL(blob)
    } else if (k === 'docx') {
      const blob = await r.blob()
      await nextTick()
      const { renderAsync } = await import('docx-preview')
      if (docxRef.value) {
        docxRef.value.innerHTML = ''
        await renderAsync(blob, docxRef.value, undefined, {
          className: 'docx', inWrapper: true, ignoreWidth: false, ignoreHeight: false,
        })
      }
    }
  } catch (e: any) {
    error.value = e.message || '加载失败'
  } finally { loading.value = false }
}, { immediate: true })

import { onBeforeUnmount } from 'vue'
onBeforeUnmount(() => { if (blobUrl.value) URL.revokeObjectURL(blobUrl.value) })

function getAuthHeader(): Record<string, string> {
  const t = localStorage.getItem('access_token')
  return t ? { Authorization: `Bearer ${t}` } : {}
}

// For browser-native links (download / new tab) we can't set headers,
// so expose the JWT via ?t= on the URL.
const tokenizedUrl = computed(() => {
  const url = props.file?.download_url || ''
  if (!url) return ''
  const tok = localStorage.getItem('access_token') || ''
  if (!tok) return url
  const sep = url.includes('?') ? '&' : '?'
  return `${url}${sep}t=${encodeURIComponent(tok)}`
})

function openInNewTab() {
  if (tokenizedUrl.value) window.open(tokenizedUrl.value, '_blank')
}
</script>

<style scoped>
.preview-panel {
  height: 100%; display: flex; flex-direction: column;
  background: var(--m-surface);
  border-left: 1px solid var(--m-border);
  min-width: 0;
}
.preview-head {
  height: 52px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 16px;
  border-bottom: 1px solid var(--m-border);
}
.head-left { display: flex; align-items: center; gap: 8px; min-width: 0; flex: 1; }
.head-left .file-name {
  font-size: 14px; font-weight: 500;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.head-right { display: flex; gap: 4px; flex-shrink: 0; }
.head-btn {
  width: 32px; height: 32px; border-radius: 50%;
  border: none; background: transparent; cursor: pointer;
  color: var(--m-text-secondary);
  display: flex; align-items: center; justify-content: center;
  text-decoration: none;
  transition: background .15s;
}
.head-btn:hover { background: var(--m-surface-variant); color: var(--m-text); }

.preview-body { flex: 1; min-height: 0; overflow: auto; background: var(--m-bg-soft); }

.state {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  height: 100%; gap: 8px; color: var(--m-text-secondary); font-size: 13px;
}
.state.error { color: var(--m-danger); }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.renderer-frame { width: 100%; height: 100%; border: none; background: #fff; }

.md-body {
  padding: 24px 32px; max-width: 920px; margin: 0 auto;
  background: var(--m-surface); min-height: 100%; box-sizing: border-box;
  font-size: 14.5px; line-height: 1.7; color: var(--m-text);
}
.md-body :deep(h1), .md-body :deep(h2), .md-body :deep(h3) { font-weight: 600; letter-spacing: -0.01em; margin: 1.2em 0 .6em; }
.md-body :deep(pre) { background: #202124; color: #e8eaed; padding: 14px; border-radius: 8px; overflow: auto; font-size: 13px; }
.md-body :deep(code) { font-family: 'Roboto Mono', monospace; }
.md-body :deep(:not(pre) > code) { background: var(--m-surface-variant); padding: 1px 6px; border-radius: 4px; font-size: 13px; }
.md-body :deep(table) { border-collapse: collapse; }
.md-body :deep(th), .md-body :deep(td) { border: 1px solid var(--m-border); padding: 6px 12px; }

.docx-body { padding: 24px 32px; background: var(--m-surface); min-height: 100%; box-sizing: border-box; }
.docx-body :deep(.docx-wrapper) { background: transparent !important; padding: 0 !important; }

.text-body {
  padding: 16px 24px; margin: 0;
  background: var(--m-surface); min-height: 100%; box-sizing: border-box;
  font-family: 'Roboto Mono', ui-monospace, Menlo, monospace;
  font-size: 13px; line-height: 1.65;
  white-space: pre-wrap; word-break: break-word;
}

.image-body {
  display: flex; align-items: center; justify-content: center;
  height: 100%; padding: 16px;
}
.image-body img { max-width: 100%; max-height: 100%; }

.svg-body {
  display: flex; align-items: center; justify-content: center;
  padding: 24px; min-height: 100%; box-sizing: border-box;
  background: var(--m-surface);
}
.svg-body :deep(svg) { max-width: 100%; height: auto; }
</style>
