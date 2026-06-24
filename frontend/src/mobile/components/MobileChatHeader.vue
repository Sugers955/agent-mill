<template>
  <header class="mb-header soft">
    <button class="mb-icon-btn" @click="$emit('toggle-drawer')" aria-label="菜单">
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
    </button>
    <div class="mb-header-title" @click="$emit('open-settings')">
      <span class="name">{{ agent?.name || '选择数字员工' }}</span>
      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
    </div>
    <button class="mb-icon-btn" @click="$emit('new-conv')" aria-label="新建对话">
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12h14"/></svg>
    </button>
  </header>
</template>

<script setup lang="ts">
defineProps<{
  agent?: any
}>()

defineEmits<{
  'toggle-drawer': []
  'open-settings': []
  'new-conv': []
}>()
</script>

<style scoped>
/* Soft header — no bottom border */
.mb-header.soft { background: var(--m-bg); border-bottom: none; }
</style>