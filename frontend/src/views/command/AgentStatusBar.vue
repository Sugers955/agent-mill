<template>
  <div class="agent-status-bar">
    <div class="asb-agent">
      <div class="asb-avatar" :style="{ background: agentGradient }">
        <img v-if="agent?.icon_url" :src="agent.icon_url" />
        <span v-else>{{ agentInitial }}</span>
      </div>
      <div class="asb-meta">
        <div class="asb-name">{{ agent?.name || '未选择员工' }}</div>
        <div class="asb-pos">{{ agent?.description || '数字员工' }}</div>
      </div>
    </div>
    <div class="asb-info">
      <div class="asb-status" :class="statusClass">
        <span class="asb-dot" />
        <span>{{ statusText }}</span>
      </div>
      <div v-if="currentTask" class="asb-task">
        <svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.3"><circle cx="8" cy="8" r="6"/><path d="M8 4v4l3 2"/></svg>
        {{ currentTask }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { agentGradient as getAgentGradient } from '@/utils/agent-colors'

const props = defineProps<{
  agent: any
  status?: 'working' | 'idle' | 'offline'
  currentTask?: string
  workDuration?: string
}>()

const statusClass = computed(() => props.status || 'idle')
const statusText = computed(() => ({ working: '工作中', idle: '空闲', offline: '离线' })[statusClass.value] || '空闲')
const agentGradient = computed(() => getAgentGradient(props.agent))
const agentInitial = computed(() => props.agent?.name?.charAt(0) || '?')
</script>

<style scoped>
.agent-status-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 14px;
  background: var(--m-surface); border: 1px solid var(--m-border); border-radius: 10px;
}
.asb-agent { display: flex; align-items: center; gap: 10px; }
.asb-avatar {
  width: 36px; height: 36px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-size: 14px; font-weight: 600; flex-shrink: 0;
}
.asb-avatar img { width: 100%; height: 100%; border-radius: 50%; object-fit: cover; }
.asb-meta { display: flex; flex-direction: column; gap: 1px; }
.asb-name { font-size: 14px; font-weight: 600; color: var(--m-text); }
.asb-pos { font-size: 12px; color: var(--m-text-secondary); }
.asb-info { display: flex; align-items: center; gap: 12px; }
.asb-status { display: flex; align-items: center; gap: 5px; font-size: 12px; color: var(--m-text-secondary); }
.asb-dot { width: 7px; height: 7px; border-radius: 50%; }
.asb-status.working .asb-dot { background: var(--m-success); animation: asb-pulse 1.5s ease-in-out infinite; }
.asb-status.idle .asb-dot { background: var(--m-text-tertiary); }
.asb-status.offline .asb-dot { background: var(--m-text-tertiary); opacity: 0.4; }
@keyframes asb-pulse { 0%, 100% { box-shadow: 0 0 0 0 var(--m-success-soft); } 50% { box-shadow: 0 0 0 4px transparent; } }
.asb-task { display: flex; align-items: center; gap: 4px; font-size: 12px; color: var(--m-primary); }
</style>
