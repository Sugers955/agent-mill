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
const STREAM_MIN_HEIGHT = 400
const MIN_WIDTH = 350
const STREAM_MIN_WIDTH = 420
const MAX_HEIGHT = 12000
const POST_FINAL_DEAD_ZONE = 8  // ignore growth smaller than this px after finalize

// Hard cap: widget must never exceed 90% of the browser viewport height.
// Evaluated lazily so SSR / test environments without window don't break.
function viewportCap(): number {
  return typeof window !== 'undefined'
    ? Math.floor(window.innerHeight * 0.9)
    : MAX_HEIGHT
}

const iframeRef = ref<HTMLIFrameElement | null>(null)
const iframeReady = ref(false)
// `cachedHeight` is the iframe height — set ONCE per phase:
//   - on first widget code: predicted from viewBox (or STREAM_MIN_HEIGHT)
//   - on finalize: measured from the rendered SVG/HTML (one shot)
// We deliberately ignore continuous ResizeObserver streams during streaming
// to prevent the panel from flickering as SVG nodes paint in.
const cachedHeight = ref(STREAM_MIN_HEIGHT)
const isFinalized = ref(false)
const lastSentCode = ref('')
const finalizedCode = ref('')

const srcdoc = computed(() => buildReceiverSrcdoc(getWidgetIframeStyleBlock()))

/** Predict the iframe height from the SVG viewBox.
 *  Uses the actual viewBox width (not a hardcoded 640) to compute the aspect ratio.
 *  For HTML widgets returns 0 so the panel starts at MIN_HEIGHT and snaps at finalize. */
function predictHeight(code: string): number {
  if (!code) return 0
  const looksHtml = /<(div|section|article|main|canvas|input|button)\b/i.test(code) && !code.trim().startsWith('<svg')
  if (looksHtml) return 0
  const vb = code.match(/viewBox\s*=\s*["']\s*[\d.]+\s+[\d.]+\s+([\d.]+)\s+([\d.]+)/i)
  if (vb) {
    const vbW = parseFloat(vb[1])
    const vbH = parseFloat(vb[2])
    if (vbW > 0 && vbH > 0) {
      // The iframe fills its container (~100% of chat bubble width, typically 600-760px).
      // We use the viewBox aspect ratio directly: rendered_h = vbH * (rendered_w / vbW).
      // Without knowing the exact container width, use vbW itself as the reference —
      // SVG scales proportionally so the ratio vbH/vbW is all we need.
      const ratio = vbH / vbW
      // Estimate container width conservatively at 680px (matches most chat layouts).
      const estimatedW = 680
      const predicted = Math.round(ratio * estimatedW)
      return Math.min(viewportCap(), MAX_HEIGHT, Math.max(STREAM_MIN_HEIGHT, predicted))
    }
  }
  return 0
}

// Seed predicted height as soon as we have (partial) code.
const seeded = predictHeight(props.widgetCode)
if (seeded > 0) cachedHeight.value = seeded
watch(() => props.widgetCode, (code) => {
  if (!code || isFinalized.value) return
  const predicted = predictHeight(code)
  // For SVGs: always update upward so a taller-than-expected viewBox doesn't get clipped.
  // For HTML (predicted=0): keep the streaming floor until finalize.
  if (predicted > cachedHeight.value) cachedHeight.value = predicted
})

const wrapperStyle = computed(() => {
  const widthFloor = props.isStreaming ? STREAM_MIN_WIDTH : MIN_WIDTH
  const heightFloor = props.isStreaming ? STREAM_MIN_HEIGHT : MIN_HEIGHT
  const cap = viewportCap()
  return {
    minHeight: `${Math.min(Math.max(cachedHeight.value, heightFloor), cap)}px`,
    maxHeight: `${cap}px`,
    minWidth: `${widthFloor}px`,
  }
})
const iframeStyle = computed(() => ({
  height: `${Math.min(cachedHeight.value, viewportCap())}px`,
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

function applyHeight(h: number) {
  // After finalize: snap to true content height from getBBox/ResizeObserver.
  // Allow both shrink (HTML smaller than streaming reservation) and grow
  // (SVG content that exceeds viewBox). Dead-zone prevents micro-wobble.
  // Hard cap: never exceed 90% of the visible viewport.
  if (!isFinalized.value) return
  const next = Math.max(MIN_HEIGHT, Math.min(h, viewportCap(), MAX_HEIGHT))
  if (Math.abs(next - cachedHeight.value) < POST_FINAL_DEAD_ZONE) return
  cachedHeight.value = next
}

function pushFinalize() {
  if (!props.widgetCode) return
  if (finalizedCode.value === props.widgetCode) return
  finalizedCode.value = props.widgetCode
  postMessage('widget:finalize', sanitizeForIframe(props.widgetCode))
  // Mark finalized AFTER receiver has had a chance to re-render and re-measure.
  // 600ms covers Chart.js + script init; afterwards applyHeight is allowed
  // to grow the panel if true content height exceeds the prediction.
  setTimeout(() => { isFinalized.value = true }, 600)
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

</style>
