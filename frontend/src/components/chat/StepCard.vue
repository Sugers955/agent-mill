<template>
  <div class="step-card" :class="[`step-${step.status}`, { expanded }]" @click="expanded = !expanded">
    <div class="step-header">
      <svg class="step-chevron" :class="{ rotated: expanded }" viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="6 4 10 8 6 12"/></svg>
      <span class="step-icon" v-text="step.status === 'running' ? '⟳' : step.status === 'done' ? '✓' : '✗'" />
      <span class="step-tool">{{ step.label || step.name || step.tool }}</span>
      <span class="step-duration" v-if="step.duration_ms">{{ step.duration_ms }}ms</span>
    </div>
    <div class="step-detail" v-if="expanded">
      <div class="step-section" v-if="hasInput">
        <div class="step-label">参数</div>
        <pre class="step-code">{{ formatVal(step.input) }}</pre>
      </div>
      <div class="step-section" v-if="hasOutput">
        <div class="step-label">结果</div>
        <pre class="step-code">{{ formatVal(step.output || step.result) }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const props = defineProps<{ step: any }>()
const expanded = ref(false)

const hasInput = computed(() => props.step.input && typeof props.step.input === 'object' && Object.keys(props.step.input).length)
const hasOutput = computed(() => props.step.output || props.step.result)

function formatVal(val: unknown): string {
  if (typeof val === 'string') return val.length > 500 ? val.slice(0, 500) + '…' : val
  try {
    const str = JSON.stringify(val, null, 2)
    return str.length > 500 ? str.slice(0, 500) + '…' : str
  } catch { return String(val) }
}
</script>

<style scoped>
.step-card {
  border: 1px solid var(--m-border);
  border-radius: var(--m-radius-sm);
  margin: 6px 0; overflow: hidden;
  background: var(--m-surface-variant);
  cursor: pointer;
  transition: box-shadow .15s;
}
.step-card:hover { box-shadow: 0 1px 4px rgba(0,0,0,.04); }
.step-header {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 10px; font-size: 12px;
  user-select: none;
}
.step-chevron { flex-shrink: 0; color: var(--m-text-tertiary); transition: transform .2s; }
.step-chevron.rotated { transform: rotate(90deg); }
.step-icon { font-size: 13px; width: 16px; text-align: center; }
.step-running .step-icon { color: var(--m-primary); animation: sp-pulse 1.2s infinite; }
.step-done .step-icon { color: var(--m-success); }
.step-error .step-icon { color: var(--m-danger); }
.step-tool { font-weight: 500; color: var(--m-text); }
.step-duration { margin-left: auto; color: var(--m-text-tertiary); font-size: 10px; }
.step-detail { border-top: 1px solid var(--m-border); padding: 8px 10px; }
.step-section { margin-bottom: 4px; }
.step-section:last-child { margin-bottom: 0; }
.step-label { font-size: 10px; color: var(--m-text-tertiary); margin-bottom: 2px; font-weight: 500; }
.step-code {
  font-size: 11px; line-height: 1.4; margin: 0;
  white-space: pre-wrap; word-break: break-all;
  color: var(--m-text-secondary);
}
@keyframes sp-pulse { 0%, 100% { opacity: 1; } 50% { opacity: .4; } }
</style>
