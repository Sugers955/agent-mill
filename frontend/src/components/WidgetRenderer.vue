<template>
  <div class="widget-wrapper" :style="wrapperStyle">
    <iframe
      ref="iframeRef"
      class="widget-iframe"
      :class="{ 'widget-iframe--ready': iframeReady }"
      :style="iframeStyle"
      sandbox="allow-scripts"
      :srcdoc="srcdoc"
      @load="handleIframeLoad"
    />
    <!-- Claude-style streaming overlay: subtle pulsing gradient veil -->
    <div
      class="widget-stream-veil"
      :class="{ 'widget-stream-veil--active': isStreaming }"
      aria-hidden="true"
    />
    <div v-if="title" class="widget-title-chip">{{ title }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { buildReceiverSrcdoc, sanitizeForStreaming, sanitizeForIframe } from '@/lib/widget-sanitizer'
import { getWidgetIframeStyleBlock } from '@/lib/widget-theme'

const props = defineProps<{
  widgetCode: string
  title?: string
  isStreaming?: boolean
}>()

const emit = defineEmits<{ ready: []; resize: [number]; sendMessage: [string] }>()

const MIN_HEIGHT = 350
const STREAM_MIN_HEIGHT = 450
const MIN_WIDTH = 350
const STREAM_MIN_WIDTH = 420
const MAX_HEIGHT = 8000

const iframeRef = ref<HTMLIFrameElement | null>(null)
const iframeReady = ref(false)
// Streaming starts at STREAM_MIN_HEIGHT; ResizeObserver may grow it as
// content fills in (never shrink below the floor while streaming).
const cachedHeight = ref(STREAM_MIN_HEIGHT)
const lastSentCode = ref('')
const finalizedCode = ref('')

const srcdoc = computed(() => buildReceiverSrcdoc(getWidgetIframeStyleBlock()))

const wrapperStyle = computed(() => {
  const widthFloor = props.isStreaming ? STREAM_MIN_WIDTH : MIN_WIDTH
  const heightFloor = props.isStreaming ? STREAM_MIN_HEIGHT : MIN_HEIGHT
  return {
    minHeight: `${Math.max(cachedHeight.value, heightFloor)}px`,
    minWidth: `${widthFloor}px`,
  }
})
const iframeStyle = computed(() => ({
  height: `${cachedHeight.value}px`,
}))

function postMessage(type: string, html?: string, extra?: Record<string, any>) {
  const win = iframeRef.value?.contentWindow
  if (!win || !iframeReady.value) return
  if (type === 'widget:update' && html === lastSentCode.value) return
  if (html !== undefined) lastSentCode.value = html
  try { win.postMessage({ type, html, ...extra }, '*') } catch { /* ignore extension noise */ }
}

function pushUpdate() {
  if (!props.widgetCode) return
  postMessage('widget:setStreaming', undefined, { on: true })
  postMessage('widget:update', sanitizeForStreaming(props.widgetCode))
}

function pushFinalize() {
  if (!props.widgetCode) return
  if (finalizedCode.value === props.widgetCode) return
  finalizedCode.value = props.widgetCode
  postMessage('widget:finalize', sanitizeForIframe(props.widgetCode))
}

function applyHeight(h: number) {
  const floor = props.isStreaming ? STREAM_MIN_HEIGHT : MIN_HEIGHT
  const next = Math.max(floor, Math.min(h, MAX_HEIGHT))
  if (Math.abs(next - cachedHeight.value) < 2) return
  cachedHeight.value = next
  emit('resize', next)
}

function handleIframeLoad() {
  if (iframeReady.value) return
  iframeReady.value = true
  setTimeout(() => {
    if (props.isStreaming) pushUpdate()
    else pushFinalize()
    emit('ready')
  }, 30)
}

function handleMessage(e: MessageEvent) {
  const data = e.data || {}
  if (typeof data.type !== 'string' || !data.type.startsWith('widget:')) return
  if (iframeRef.value?.contentWindow && e.source !== iframeRef.value.contentWindow) return
  switch (data.type) {
    case 'widget:ready':
      iframeReady.value = true
      if (props.isStreaming) pushUpdate()
      else pushFinalize()
      emit('ready')
      break
    case 'widget:resize':
      if (typeof data.height === 'number') applyHeight(data.height)
      break
    case 'widget:link':
      if (data.href) window.open(data.href, '_blank', 'noopener,noreferrer')
      break
    case 'widget:sendMessage':
      if (data.text) emit('sendMessage', data.text)
      break
  }
}

watch(() => props.widgetCode, (code, oldCode) => {
  if (!code || !iframeReady.value) return
  if (oldCode !== code) finalizedCode.value = ''
  if (props.isStreaming) pushUpdate()
  else pushFinalize()
})

watch(() => props.isStreaming, (streaming) => {
  if (!props.widgetCode || !iframeReady.value) return
  if (streaming) pushUpdate()
  else pushFinalize()
})

onMounted(() => {
  window.addEventListener('message', handleMessage)
})

onUnmounted(() => {
  window.removeEventListener('message', handleMessage)
})
</script>

<style scoped>
.widget-wrapper {
  position: relative;
  width: 100%;
  margin: 8px 0;
  border-radius: var(--m-radius, 12px);
  background: transparent;
  overflow: hidden;
}

.widget-iframe {
  width: 100%;
  border: none;
  display: block;
  background: transparent;
  /* Claude-style entrance: fade + tiny lift */
  opacity: 0;
  transform: translateY(8px);
  transition: opacity .35s cubic-bezier(.2,.8,.2,1),
              transform .35s cubic-bezier(.2,.8,.2,1),
              height .18s ease-out;
}
.widget-iframe--ready {
  opacity: 1;
  transform: translateY(0);
}

/* Streaming veil: light Google-blue gradient that gently breathes while
   the widget is being generated. Dissolves on completion. */
.widget-stream-veil {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    linear-gradient(
      180deg,
      rgba(232, 240, 254, 0) 0%,
      rgba(232, 240, 254, 0.18) 60%,
      rgba(232, 240, 254, 0.32) 100%
    ),
    linear-gradient(
      90deg,
      rgba(232, 240, 254, 0) 0%,
      rgba(232, 240, 254, 0.20) 50%,
      rgba(232, 240, 254, 0) 100%
    );
  background-size: 100% 100%, 200% 100%;
  background-position: 0 0, -50% 0;
  opacity: 0;
  transition: opacity .4s ease;
}
.widget-stream-veil--active {
  opacity: 1;
  animation: widget-veil-sweep 2.4s ease-in-out infinite;
}
@keyframes widget-veil-sweep {
  0%   { background-position: 0 0, -100% 0; }
  100% { background-position: 0 0, 200% 0; }
}

/* Title chip — sits above the widget while streaming, fades after */
.widget-title-chip {
  position: absolute;
  top: 10px; left: 12px;
  font-size: 11px; font-weight: 500;
  letter-spacing: 0.04em; text-transform: uppercase;
  color: var(--m-text-secondary, #5f6368);
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(4px);
  padding: 3px 9px;
  border-radius: 999px;
  border: 1px solid var(--m-border, #e8eaed);
  pointer-events: none;
  user-select: none;
}
</style>
