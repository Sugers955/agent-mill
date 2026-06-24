<template>
  <div class="welcome">
    <div class="welcome-brand">
      <img class="welcome-logo" src="/logo-icon.png" alt="Agent Mill" />
      <div class="welcome-title">Agent Mill</div>
      <div class="welcome-sub">你的数字员工工厂</div>
    </div>

    <div class="welcome-workers" v-if="agents.length">
      <div
        class="worker-card"
        v-for="a in agents.slice(0, 5)" :key="a.id"
        @click="$emit('pick-agent', a.id)"
        role="button"
        tabindex="0"
        :aria-label="`选择数字员工 ${a.name}${a.description ? '：' + a.description : ''}`"
      >
        <img class="worker-avatar" :src="a.avatar_url || '/logo-icon.png'" :alt="a.name" />
        <div class="worker-name">{{ a.name }}</div>
        <div class="worker-desc" v-if="a.description">{{ a.description }}</div>
      </div>
    </div>

    <div class="welcome-starters" v-if="starters.length">
      <button
        class="starter-chip"
        v-for="s in starters" :key="s.label"
        @click="$emit('pick-starter', s.query)"
      >
        {{ s.label }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { AgentInfo, StarterItem } from '@/shared/types/chat'

defineProps<{
  agents?: AgentInfo[]
  starters?: StarterItem[]
}>()

defineEmits<{
  'pick-agent': [id: number]
  'pick-starter': [query: string]
}>()
</script>

<style scoped>
.welcome {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; flex: 1; gap: 28px;
  padding: 60px 24px; text-align: center;
}
.welcome-brand { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.welcome-logo { width: 72px; height: 72px; border-radius: 16px; margin-bottom: 8px; }
.welcome-title { font-size: 24px; font-weight: 700; color: var(--m-text); }
.welcome-sub { font-size: 14px; color: var(--m-text-tertiary); }
.welcome-workers { display: flex; gap: 16px; flex-wrap: wrap; justify-content: center; }
.worker-card {
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  width: 120px; padding: 16px 8px;
  background: var(--m-surface); border: 1px solid var(--m-border);
  border-radius: var(--m-radius); cursor: pointer;
  transition: box-shadow .2s, transform .2s;
}
.worker-card:hover { box-shadow: var(--m-shadow-2); transform: translateY(-2px); }
.worker-avatar { width: 48px; height: 48px; border-radius: 50%; object-fit: cover; }
.worker-name { font-size: 13px; font-weight: 600; color: var(--m-text); }
.worker-desc { font-size: 11px; color: var(--m-text-tertiary); line-height: 1.3; }
.welcome-starters { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }
.starter-chip {
  padding: 8px 18px; border: 1px solid var(--m-border);
  border-radius: var(--m-radius-pill); background: var(--m-surface);
  font-size: 13px; color: var(--m-text-secondary); cursor: pointer;
  transition: all .2s;
}
.starter-chip:hover { border-color: var(--m-primary); color: var(--m-primary); background: var(--m-primary-soft); }
</style>
