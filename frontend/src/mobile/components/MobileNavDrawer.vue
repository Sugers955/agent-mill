<template>
  <div :class="['mb-drawer-mask', { open: visible }]" @click="$emit('close')" />
  <aside :class="['mb-drawer', { open: visible }]">
    <div class="drawer-brand">
      <img class="brand-logo" src="/logo-icon.png" alt="Agent Mill" />
      <div class="brand-text">
        <div class="brand-name">Agent Mill</div>
        <div class="brand-sub">数字员工助手</div>
      </div>
    </div>

    <button class="conv-new" @click="$emit('new-conv')">
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12h14"/></svg>
      <span>新建对话</span>
    </button>

    <div class="drawer-nav">
      <button class="nav-item" @click="$emit('go-route', '/tasks')">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
        <span>任务</span>
      </button>
      <button class="nav-item" @click="$emit('go-route', '/space')">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
        <span>空间</span>
      </button>
      <button class="nav-item" @click="$emit('go-route', '/notifications')">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
        <span>通知</span>
        <span v-if="unreadCount > 0" class="badge">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
      </button>
    </div>

    <div class="drawer-section-label">最近对话</div>
    <div class="drawer-list">
      <div v-if="!conversations.length" class="empty">暂无历史对话</div>
      <div
        v-for="c in conversations"
        :key="c.id"
        :class="['conv-item', { active: c.id === currentConvId }]"
        @click="$emit('select-conv', c)"
      >
        <svg class="conv-icon" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        <div class="conv-name">{{ c.title || '未命名' }}</div>
        <button class="conv-action" @click.stop="$emit('conv-actions', c)" aria-label="更多">⋯</button>
      </div>
    </div>

    <div class="drawer-footer" @click="$emit('open-user-settings')">
      <div class="user-avatar">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
      </div>
      <div class="user-info">
        <div class="user-name">{{ user?.display_name || user?.username || '-' }}</div>
        <div class="user-role">{{ user?.role?.name || '' }}</div>
      </div>
      <button class="user-settings" aria-label="设置">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h0a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51h0a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v0a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
      </button>
    </div>
  </aside>
</template>

<script setup lang="ts">
defineProps<{
  visible: boolean
  conversations: any[]
  currentConvId: number | null
  user: any
  unreadCount: number
}>()

defineEmits<{
  'close': []
  'new-conv': []
  'go-route': [path: string]
  'select-conv': [conv: any]
  'conv-actions': [conv: any]
  'open-user-settings': []
}>()
</script>

<style scoped>
/* Drawer */
.mb-drawer {
  background: var(--m-bg);
  display: flex; flex-direction: column;
}
.drawer-brand {
  display: flex; align-items: center; gap: 10px;
  padding: env(safe-area-inset-top, 16px) 16px 12px;
  padding-top: calc(env(safe-area-inset-top, 0px) + 18px);
  flex-shrink: 0;
}
.brand-logo {
  width: 38px; height: 38px; border-radius: 10px;
  object-fit: cover; object-position: center 35%;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(0,0,0,.08);
  background: var(--m-surface);
}
.brand-text { line-height: 1.2; }
.brand-name { font-size: 16px; font-weight: 600; color: var(--m-text); letter-spacing: -.01em; }
.brand-sub { font-size: 14px; color: var(--m-text-secondary); margin-top: 2px; }

.conv-new {
  margin: 4px 12px 14px;
  display: flex; align-items: center; gap: 8px; justify-content: center;
  height: 42px; border-radius: 12px;
  background: var(--m-primary-soft); color: var(--m-primary);
  font-weight: 500; font-size: 16px;
  flex-shrink: 0;
}
.conv-new:active { background: rgba(66,133,244,.15); }

.drawer-nav {
  display: flex; flex-direction: column;
  margin: 0 8px 8px;
  gap: 2px;
}
.nav-item {
  display: flex; align-items: center; gap: 10px;
  height: 38px; padding: 0 12px;
  border-radius: 10px;
  font-size: 16px; color: var(--m-text);
  background: transparent;
  position: relative;
}
.nav-item:active { background: var(--m-surface-variant); }
.nav-item .badge {
  position: absolute; right: 12px;
  min-width: 16px; height: 16px; padding: 0 5px;
  border-radius: 8px;
  background: var(--m-danger); color: #fff;
  font-size: 10px; font-weight: 600; line-height: 16px;
  text-align: center;
}

.drawer-section-label {
  padding: 4px 18px 6px;
  font-size: 14px; font-weight: 600;
  color: var(--m-text-tertiary); letter-spacing: .04em;
  text-transform: uppercase;
}
.drawer-list { flex: 1; overflow: auto; padding: 0 8px 12px; }
.empty {
  text-align: center; color: var(--m-text-tertiary);
  padding: 24px; font-size: 16px;
}
.conv-item {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 12px;
  margin: 2px 0;
  border-radius: 10px;
  font-size: 16px;
  color: var(--m-text);
}
.conv-item:active { background: var(--m-surface-variant); }
.conv-item.active { background: var(--m-primary-soft); color: var(--m-primary); }
.conv-icon { color: var(--m-text-tertiary); flex-shrink: 0; }
.conv-item.active .conv-icon { color: var(--m-primary); }
.conv-name {
  flex: 1; min-width: 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.conv-action {
  width: 26px; height: 26px; border-radius: 50%;
  color: var(--m-text-secondary); font-size: 16px; line-height: 1;
}
.conv-action:active { background: var(--m-surface-variant); }

.drawer-footer {
  flex-shrink: 0;
  display: flex; align-items: center; gap: 12px;
  padding: 12px 14px calc(12px + var(--safe-bottom));
  margin-top: 4px;
  background: var(--m-surface);
  border-top: 1px solid var(--m-border);
}
.drawer-footer:active { background: var(--m-surface-variant); }
.user-avatar {
  width: 38px; height: 38px; border-radius: 50%;
  background: var(--m-primary-soft); color: var(--m-primary);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.user-info { flex: 1; min-width: 0; }
.user-name {
  font-size: 16px; font-weight: 600; color: var(--m-text);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.user-role {
  font-size: 14px; color: var(--m-text-secondary); margin-top: 2px;
}
.user-settings {
  width: 36px; height: 36px; border-radius: 50%;
  color: var(--m-text-secondary);
  display: flex; align-items: center; justify-content: center;
}
.user-settings:active { background: var(--m-surface-variant); }
</style>