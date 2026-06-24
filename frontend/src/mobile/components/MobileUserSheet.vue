<template>
  <div :class="['mb-drawer-mask', { open: visible }]" @click="$emit('close')" />
  <div :class="['mb-sheet', { open: visible }]">
    <div class="mb-sheet-handle" />
    <div class="mb-sheet-title">{{ user?.display_name || user?.username || '我' }}</div>
    <div class="mb-sheet-body">
      <div class="action-item" @click="$emit('change-password')">修改密码</div>
      <div class="action-item danger" @click="$emit('logout')">退出登录</div>
      <div class="action-item cancel" @click="$emit('close')">取消</div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  visible: boolean
  user: any
}>()

defineEmits<{
  'close': []
  'change-password': []
  'logout': []
}>()
</script>

<style scoped>
/* Action sheet items */
.action-item {
  padding: 14px 16px;
  text-align: center; font-size: 16px;
  border-bottom: none;
  position: relative;
}
.action-item + .action-item:not(.cancel)::before {
  content: '';
  position: absolute; left: 16px; right: 16px; top: 0;
  height: 1px; background: var(--m-border);
}
.action-item:active { background: var(--m-surface-variant); }
.action-item.danger { color: var(--m-danger); }
.action-item.cancel {
  margin-top: 8px;
  background: var(--m-bg-soft);
  font-weight: 600;
}
</style>