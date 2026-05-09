<template>
  <div class="pack-card" :class="statusClass">
    <div class="pack-head">
      <el-icon v-if="status === 'success'" class="pack-status-icon ok"><CircleCheckFilled /></el-icon>
      <el-icon v-else-if="status === 'waiting_approval'" class="pack-status-icon warn"><Bell /></el-icon>
      <el-icon v-else-if="status === 'failed'" class="pack-status-icon fail"><CircleCloseFilled /></el-icon>
      <el-icon v-else class="pack-status-icon"><Box /></el-icon>
      <span class="pack-kind">PACK</span>
      <code class="pack-name">{{ packCode || '(unknown)' }}</code>
      <el-tag :type="tagType" size="small" effect="light">{{ statusLabel }}</el-tag>
      <span v-if="output?.run_id" class="pack-run-id" :title="output.run_id">#{{ shortRunId }}</span>
    </div>

    <div v-if="message" class="pack-message">{{ message }}</div>

    <div v-if="trace.length" class="pack-trace">
      <div v-for="(t, ti) in trace" :key="ti" class="pack-node">
        <el-icon
          v-if="t.status === 'success' || t.status === 'approved'"
          style="color:var(--m-success)"
        ><CircleCheckFilled /></el-icon>
        <el-icon
          v-else-if="t.status === 'failed' || t.status === 'rejected'"
          style="color:var(--m-danger)"
        ><CircleCloseFilled /></el-icon>
        <el-icon
          v-else-if="t.status === 'waiting_approval'"
          style="color:var(--m-warning)"
        ><Bell /></el-icon>
        <el-icon
          v-else-if="t.status === 'running'"
          class="is-loading"
        ><Loading /></el-icon>
        <el-icon v-else style="color:var(--m-text-tertiary)"><MoreFilled /></el-icon>
        <span class="pack-node-id">{{ t.node_id }}</span>
        <span class="pack-node-type">{{ t.node_type || '' }}</span>
        <span v-if="t.duration_ms" class="muted" style="font-size:11px">{{ t.duration_ms }}ms</span>
        <span v-if="t.error" class="pack-node-error" :title="t.error">{{ t.error }}</span>
      </div>
    </div>

    <details v-if="hasIO" class="pack-detail">
      <summary class="muted">查看 输入/输出</summary>
      <div v-if="input" class="pack-block"><div class="pack-label">Input</div><pre>{{ formatJson(input) }}</pre></div>
      <div v-if="outputs && Object.keys(outputs).length" class="pack-block"><div class="pack-label">Outputs</div><pre>{{ formatJson(outputs) }}</pre></div>
    </details>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { CircleCheckFilled, CircleCloseFilled, Bell, Box, Loading, MoreFilled } from '@element-plus/icons-vue'

const props = defineProps<{
  packCode?: string
  input?: any
  output?: any
}>()

const parsed = computed(() => {
  const o = props.output
  if (!o) return null
  if (typeof o === 'string') {
    try { return JSON.parse(o) } catch { return null }
  }
  return o
})

const status = computed<string>(() => parsed.value?.status || (props.output ? 'running' : 'pending'))
const message = computed<string>(() => parsed.value?.message || parsed.value?.error || '')
const trace = computed<any[]>(() => Array.isArray(parsed.value?.trace) ? parsed.value.trace : [])
const outputs = computed<any>(() => parsed.value?.outputs || null)

const statusClass = computed(() => {
  switch (status.value) {
    case 'success': return 'ok'
    case 'failed': return 'fail'
    case 'waiting_approval': return 'warn'
    case 'running': return 'running'
    default: return ''
  }
})

const tagType = computed<'success' | 'warning' | 'danger' | 'info'>(() => {
  switch (status.value) {
    case 'success': return 'success'
    case 'waiting_approval': return 'warning'
    case 'failed': return 'danger'
    default: return 'info'
  }
})

const statusLabel = computed(() => {
  switch (status.value) {
    case 'success': return '完成'
    case 'failed': return '失败'
    case 'waiting_approval': return '待审批'
    case 'running': return '运行中'
    default: return status.value || '-'
  }
})

const shortRunId = computed(() => {
  const r = parsed.value?.run_id
  return r ? String(r).slice(0, 8) : ''
})

const hasIO = computed(() => !!props.input || (outputs.value && Object.keys(outputs.value).length))

function formatJson(v: any) {
  if (v == null) return ''
  if (typeof v === 'string') {
    try { return JSON.stringify(JSON.parse(v), null, 2) } catch { return v }
  }
  return JSON.stringify(v, null, 2)
}
</script>

<style scoped>
.pack-card {
  border: 1px solid var(--m-border);
  border-radius: var(--m-radius);
  background: var(--m-surface);
  padding: 10px 12px;
  font-size: 13px;
}
.pack-card.running { background: var(--m-primary-soft); border-color: var(--m-primary); }
.pack-card.warn { border-color: var(--m-warning); background: color-mix(in srgb, var(--m-warning) 8%, var(--m-surface)); }
.pack-card.fail { border-color: var(--m-danger); }

.pack-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.pack-status-icon { font-size: 16px; }
.pack-status-icon.ok { color: var(--m-success); }
.pack-status-icon.warn { color: var(--m-warning); }
.pack-status-icon.fail { color: var(--m-danger); }
.pack-kind {
  text-transform: uppercase; font-size: 10px; font-weight: 700; letter-spacing: .06em;
  color: #fff; background: var(--m-primary); padding: 2px 8px; border-radius: 4px;
}
.pack-name { font-family: 'Roboto Mono', monospace; font-size: 12px; color: var(--m-text); }
.pack-run-id { font-family: 'Roboto Mono', monospace; font-size: 11px; color: var(--m-text-tertiary); }

.pack-message {
  margin-top: 6px; padding: 6px 8px; border-radius: 6px;
  background: var(--m-bg-soft); color: var(--m-text-secondary); font-size: 12px;
}

.pack-trace { margin-top: 8px; display: flex; flex-direction: column; gap: 4px; }
.pack-node {
  display: flex; align-items: center; gap: 8px;
  padding: 4px 6px; border-radius: 6px; background: var(--m-bg-soft);
}
.pack-node-id { font-family: 'Roboto Mono', monospace; font-size: 12px; color: var(--m-text); }
.pack-node-type {
  font-size: 10px; text-transform: uppercase; letter-spacing: .04em;
  color: var(--m-text-secondary); background: var(--m-surface-variant);
  padding: 1px 6px; border-radius: 3px;
}
.pack-node-error { font-size: 11px; color: var(--m-danger); margin-left: 4px; }

.pack-detail { margin-top: 8px; }
.pack-detail summary { cursor: pointer; font-size: 12px; padding: 2px 0; }
.pack-block { margin-top: 6px; }
.pack-label {
  font-size: 10px; text-transform: uppercase; letter-spacing: .06em;
  color: var(--m-text-secondary); margin-bottom: 4px;
}
.pack-block pre {
  margin: 0; padding: 8px 10px; background: var(--m-bg-soft);
  border-radius: 6px; font-size: 12px; font-family: 'Roboto Mono', monospace;
  overflow: auto; max-height: 240px;
}
.is-loading { animation: rotate 1.2s linear infinite; }
@keyframes rotate { from { transform: rotate(0); } to { transform: rotate(360deg); } }

.muted { color: var(--m-text-tertiary); }
</style>
