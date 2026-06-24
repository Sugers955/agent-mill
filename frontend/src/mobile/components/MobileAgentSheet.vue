<template>
  <div :class="['mb-drawer-mask', { open: visible }]" @click="$emit('close')" />
  <div :class="['mb-sheet', { open: visible }]">
    <div class="mb-sheet-handle" />
    <div class="mb-sheet-title">选择数字员工</div>
    <div class="mb-sheet-body">
      <div v-if="!agents.length" class="empty">暂无可用数字员工</div>
      <div
        v-for="a in agents" :key="a.id"
        :class="['agent-item', { active: a.id === currentAgentId }]"
        @click="$emit('select', a)"
      >
        <div class="agent-avatar">{{ (a.name || '?').slice(0, 1) }}</div>
        <div class="agent-text">
          <div class="agent-name">{{ a.name }}</div>
          <div v-if="a.description" class="agent-desc">{{ a.description }}</div>
        </div>
        <svg v-if="a.id === currentAgentId" class="check" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  visible: boolean
  agents: any[]
  currentAgentId: number | null
}>()

defineEmits<{
  'close': []
  'select': [agent: any]
}>()
</script>

<style scoped>
/* Agent sheet items */
.agent-item {
  display: flex; align-items: center; gap: 12px;
  padding: 14px 16px;
  border-bottom: none;
}
.agent-item:active { background: var(--m-surface-variant); }
.agent-item.active { background: var(--m-primary-soft); }
.agent-avatar {
  width: 36px; height: 36px; border-radius: 50%;
  background: var(--m-primary); color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-weight: 600; flex-shrink: 0;
}
.agent-text { flex: 1; min-width: 0; }
.agent-name { font-size: 16px; font-weight: 500; color: var(--m-text); }
.agent-desc {
  margin-top: 2px;
  font-size: 14px; color: var(--m-text-secondary); line-height: 1.5;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.agent-item.active .agent-name { color: var(--m-primary); }
.check { color: var(--m-primary); flex-shrink: 0; }
</style>