<template>
  <teleport to="body">
    <div :class="['mb-preview-mask', { open: !!file }]" @click.self="$emit('close')">
      <div :class="['mb-preview-sheet', { open: !!file }]">
        <div class="grabber" />
        <header class="head">
          <div class="title-wrap">
            <div class="title" :title="file?.name">{{ file?.name || '预览' }}</div>
            <div v-if="subTitle" class="sub">{{ subTitle }}</div>
          </div>
          <div class="actions">
            <a v-if="tokenizedUrl" class="act-btn" :href="tokenizedUrl" :download="file?.name" aria-label="下载">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            </a>
            <button class="act-btn" @click="$emit('close')" aria-label="关闭">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
        </header>

        <div class="body">
          <div v-if="loading" class="state">
            <div class="spinner" /><span>加载中…</span>
          </div>
          <div v-else-if="error" class="state error">{{ error }}</div>

          <iframe
            v-else-if="kind === 'html' && blobUrl"
            class="frame"
            sandbox="allow-scripts allow-popups"
            :src="blobUrl"
          />
          <iframe
            v-else-if="kind === 'pdf' && blobUrl"
            class="frame"
            :src="blobUrl"
          />
          <div v-else-if="kind === 'svg' && textContent" class="svg-body" v-html="textContent"></div>
          <div v-else-if="kind === 'md'" class="md-body" v-html="mdHtml"></div>
          <pre v-else-if="kind === 'text'" class="text-body">{{ textContent }}</pre>
          <div v-else-if="kind === 'image' && blobUrl" class="image-body">
            <img :src="blobUrl" :alt="file?.name" />
          </div>
          <div v-else class="state">
            <div>该文件类型暂不支持在线预览</div>
            <a v-if="tokenizedUrl" class="dl-link" :href="tokenizedUrl" :download="file?.name">下载查看</a>
          </div>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import MarkdownIt from 'markdown-it'

const props = defineProps<{ file: any | null }>()
defineEmits<{ (e: 'close'): void }>()

const md = new MarkdownIt({ breaks: true, linkify: true, html: false })

const loading = ref(false)
const error = ref('')
const textContent = ref('')
const mdHtml = ref('')
const blobUrl = ref('')

const ext = computed(() => {
  if (!props.file) return ''
  return (props.file.ext || (props.file.name || '').split('.').pop() || '').toLowerCase().replace(/^\./, '')
})

const kind = computed<'html' | 'pdf' | 'md' | 'text' | 'image' | 'svg' | 'other'>(() => {
  const e = ext.value
  if (['html', 'htm'].includes(e)) return 'html'
  if (e === 'pdf') return 'pdf'
  if (['md', 'markdown'].includes(e)) return 'md'
  if (e === 'svg') return 'svg'
  if (['txt', 'json', 'csv', 'xml', 'js', 'ts', 'css', 'py', 'sql', 'yml', 'yaml', 'sh', 'log'].includes(e)) return 'text'
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'].includes(e)) return 'image'
  return 'other'
})

const subTitle = computed(() => {
  const f: any = props.file
  if (!f) return ''
  const parts: string[] = []
  if (f.parsed_chars) parts.push(`${f.parsed_chars} 字`)
  else if (f.size) parts.push(formatSize(f.size))
  if (ext.value) parts.push(ext.value.toUpperCase())
  return parts.join(' · ')
})

function formatSize(n: number) {
  if (!n) return ''
  if (n < 1024) return n + ' B'
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + ' KB'
  return (n / 1024 / 1024).toFixed(1) + ' MB'
}

const tokenizedUrl = computed(() => {
  const url = props.file?.download_url || ''
  if (!url) return ''
  const tok = localStorage.getItem('access_token') || ''
  if (!tok) return url
  const sep = url.includes('?') ? '&' : '?'
  return `${url}${sep}t=${encodeURIComponent(tok)}`
})

watch(() => props.file?.download_url, async (url) => {
  if (blobUrl.value) { URL.revokeObjectURL(blobUrl.value); blobUrl.value = '' }
  if (!url || !props.file) return
  error.value = ''
  textContent.value = ''
  mdHtml.value = ''
  loading.value = true
  try {
    const tok = localStorage.getItem('access_token') || ''
    const r = await fetch(url, { headers: tok ? { Authorization: `Bearer ${tok}` } : {} })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    const k = kind.value
    if (k === 'md' || k === 'text' || k === 'svg') {
      const txt = await r.text()
      textContent.value = txt
      if (k === 'md') mdHtml.value = md.render(txt)
    } else if (k === 'html' || k === 'pdf' || k === 'image') {
      const blob = await r.blob()
      blobUrl.value = URL.createObjectURL(blob)
    }
  } catch (e: any) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}, { immediate: true })

onBeforeUnmount(() => { if (blobUrl.value) URL.revokeObjectURL(blobUrl.value) })
</script>

<style scoped>
.mb-preview-mask {
  position: fixed; inset: 0; z-index: 300;
  background: rgba(0,0,0,.4);
  opacity: 0; pointer-events: none;
  transition: opacity .22s ease;
  display: flex; align-items: flex-end; justify-content: center;
}
.mb-preview-mask.open { opacity: 1; pointer-events: auto; }

.mb-preview-sheet {
  position: relative;
  width: 100%; max-width: 720px;
  height: 88vh;
  background: var(--m-surface);
  border-radius: 18px 18px 0 0;
  display: flex; flex-direction: column;
  transform: translateY(100%);
  transition: transform .28s cubic-bezier(.2,.8,.2,1);
  padding-bottom: var(--safe-bottom);
  overflow: hidden;
}
.mb-preview-sheet.open { transform: translateY(0); }

.grabber {
  align-self: center;
  margin: 8px 0 4px;
  width: 36px; height: 4px;
  background: var(--m-border-strong);
  border-radius: 2px;
  flex-shrink: 0;
}

.head {
  display: flex; align-items: center; gap: 10px;
  padding: 6px 12px 10px;
  flex-shrink: 0;
}
.title-wrap { flex: 1; min-width: 0; }
.title {
  font-size: 15px; font-weight: 600;
  color: var(--m-text);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.sub {
  margin-top: 2px;
  font-size: 11.5px; color: var(--m-text-secondary);
}
.actions { display: flex; gap: 4px; flex-shrink: 0; }
.act-btn {
  width: 36px; height: 36px; border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
  color: var(--m-text-secondary);
  text-decoration: none;
  background: transparent;
}
.act-btn:active { background: var(--m-surface-variant); color: var(--m-text); }

.body {
  flex: 1; min-height: 0; overflow: auto;
  background: var(--m-bg-soft);
  -webkit-overflow-scrolling: touch;
}
.frame { width: 100%; height: 100%; border: none; background: #fff; display: block; }

.state {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  height: 100%; gap: 10px; color: var(--m-text-secondary); font-size: 13px;
  padding: 32px 24px;
}
.state.error { color: var(--m-danger); }
.spinner {
  width: 22px; height: 22px; border-radius: 50%;
  border: 2px solid var(--m-border-strong);
  border-top-color: var(--m-primary);
  animation: spin 1s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.dl-link {
  margin-top: 4px;
  padding: 8px 16px;
  background: var(--m-primary); color: #fff;
  border-radius: var(--m-radius-pill);
  font-size: 13px; font-weight: 500;
  text-decoration: none;
}

.md-body {
  padding: 18px 18px 32px;
  background: var(--m-surface);
  font-size: 14.5px; line-height: 1.7; color: var(--m-text);
}
.md-body :deep(h1), .md-body :deep(h2), .md-body :deep(h3) {
  font-weight: 600; margin: 1em 0 .5em;
}
.md-body :deep(pre) {
  background: #f1f3f4; padding: 12px; border-radius: 8px;
  overflow: auto; font-size: 12.5px;
}
.md-body :deep(:not(pre) > code) {
  background: var(--m-surface-variant);
  padding: 1px 6px; border-radius: 4px; font-size: 13px;
}
.md-body :deep(table) { border-collapse: collapse; width: 100%; }
.md-body :deep(th), .md-body :deep(td) {
  border: 1px solid var(--m-border); padding: 6px 10px;
}

.text-body {
  margin: 0;
  padding: 16px 18px 32px;
  background: var(--m-surface);
  font-family: ui-monospace, Menlo, Consolas, monospace;
  font-size: 12.5px; line-height: 1.65;
  white-space: pre-wrap; word-break: break-word;
  color: var(--m-text);
}

.svg-body {
  display: flex; align-items: center; justify-content: center;
  padding: 24px; min-height: 100%; box-sizing: border-box;
  background: var(--m-surface);
}
.svg-body :deep(svg) { max-width: 100%; height: auto; }

.image-body {
  display: flex; align-items: center; justify-content: center;
  min-height: 100%; padding: 16px;
  background: #000;
}
.image-body img { max-width: 100%; max-height: 100%; }
</style>
