<template>
  <div class="mb-wrap">
    <div ref="containerRef" class="mb-svg" />
    <div v-if="loading" class="mb-loading">
      <span class="mb-spinner" />
      <span>渲染图中…</span>
    </div>
    <div v-if="error" class="mb-error">
      <svg viewBox="0 0 16 16" width="14" height="14"><circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M8 5v3M8 11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
      图渲染失败
    </div>
    <div class="mb-actions" v-if="!error && !loading">
      <button class="mb-btn" @click="downloadSvg" title="下载 SVG">
        <svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M8 11V3M5 8l3 3 3-3"/><path d="M2 12v2h12v-2"/></svg>
      </button>
      <button class="mb-btn" @click="copySvg" title="复制 SVG">
        <svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><rect x="4" y="2" width="10" height="12" rx="1"/><path d="M2 6v8a1 1 0 001 1h7"/></svg>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps<{ code: string }>()

const containerRef = ref<HTMLElement | null>(null)
const loading = ref(true)
const error = ref(false)
let mermaidInstance: any = null

async function render() {
  if (!containerRef.value || !props.code) return
  loading.value = true
  error.value = false
  try {
    if (!mermaidInstance) {
      const mermaid = await import('mermaid')
      mermaidInstance = mermaid.default
      mermaidInstance.initialize({
        startOnLoad: false,
        theme: document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'default',
        fontFamily: 'inherit',
        securityLevel: 'loose',
      })
    }
    containerRef.value.innerHTML = ''
    const id = `mermaid-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
    const { svg } = await mermaidInstance.render(id, props.code)
    containerRef.value.innerHTML = svg
    loading.value = false
  } catch (e) {
    console.error('Mermaid render error:', e)
    error.value = true
    loading.value = false
  }
}

function copySvg() {
  const svg = containerRef.value?.innerHTML
  if (!svg) return
  navigator.clipboard.writeText(svg).then(() => ElMessage.success('已复制 SVG')).catch(() => {})
}

function downloadSvg() {
  const svg = containerRef.value?.innerHTML
  if (!svg) return
  const blob = new Blob([svg], { type: 'image/svg+xml' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = `diagram-${Date.now()}.svg`
  a.click(); URL.revokeObjectURL(url)
  ElMessage.success('已下载 SVG')
}

watch(() => props.code, () => render())

onMounted(() => render())
</script>

<style scoped>
.mb-wrap {
  position: relative;
  margin: 8px 0;
  padding: 12px;
  background: var(--m-bg-soft);
  border: 1px solid var(--m-border);
  border-radius: 10px;
  overflow-x: auto;
}
.mb-svg {
  display: flex; justify-content: center;
  min-height: 60px;
}
.mb-svg :deep(svg) {
  max-width: 100%;
  height: auto;
}
.mb-loading {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  padding: 24px; font-size: 13px; color: var(--m-text-secondary);
}
.mb-spinner {
  width: 16px; height: 16px;
  border: 2px solid var(--m-border); border-top-color: var(--m-primary);
  border-radius: 50%;
  animation: mb-spin .6s linear infinite;
}
@keyframes mb-spin { to { transform: rotate(360deg); } }
.mb-error {
  display: flex; align-items: center; justify-content: center; gap: 6px;
  padding: 16px; font-size: 13px; color: var(--m-danger);
}
.mb-actions {
  position: absolute; top: 6px; right: 6px;
  display: flex; gap: 4px;
  opacity: 0; transition: opacity .15s;
}
.mb-wrap:hover .mb-actions { opacity: .7; }
.mb-actions:hover { opacity: 1 !important; }
.mb-btn {
  width: 28px; height: 28px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 6px; border: none;
  background: var(--m-surface); color: var(--m-text-secondary);
  cursor: pointer;
}
.mb-btn:hover { background: var(--m-surface-variant); }
</style>
