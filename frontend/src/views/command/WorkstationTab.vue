<template>
  <div class="workstation-tab">
    <!-- 顶部概览栏 -->
    <div class="ws-overview">
      <div class="ws-overview-left">
        <h2 class="ws-title">数字员工工位
          <span class="ws-title-count">{{ agents.length }}</span>
        </h2>
      </div>
      <div class="ws-overview-center">
        <div class="ws-stat-item" v-for="s in stats" :key="s.label">
          <span class="ws-stat-value" :style="{ color: s.color }">{{ s.count }}</span>
          <span class="ws-stat-label">{{ s.label }}</span>
        </div>
      </div>
      <div class="ws-overview-right">
        <el-radio-group v-model="viewMode" size="small">
          <el-radio-button value="grid">
            <el-icon><Grid /></el-icon> 卡片
          </el-radio-button>
          <el-radio-button value="workstation">
            <el-icon><Monitor /></el-icon> 工位
          </el-radio-button>
        </el-radio-group>
      </div>
    </div>

    <!-- 卡片视图 -->
    <div v-if="viewMode === 'grid'" class="ws-card-view">
      <div v-for="agent in agents" :key="agent.id"
        class="ws-card" @click="openChat(agent)">
        <div class="ws-card-avatar" :style="{ background: agentGradient(agent) }">
          <img v-if="agent.icon_url" :src="agent.icon_url" />
          <span v-else>{{ agentInitial(agent) }}</span>
        </div>
        <div class="ws-card-body">
          <div class="ws-card-name">{{ agent.name }}</div>
          <div class="ws-card-desc">{{ agent.description || '暂无描述' }}</div>
          <div class="ws-card-footer">
            <span class="ws-card-status" :class="agent.enabled ? 'on' : 'off'">
              <span class="ws-card-dot" />{{ agent.enabled ? '在线' : '离线' }}
            </span>
            <el-button size="small" round @click.stop="openChat(agent)">
              <el-icon><ChatDotRound /></el-icon> 对话
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 工位视图 -->
    <div v-else class="ws-station-view">
      <AgentWorkstation
        v-for="agent in agents"
        :key="agent.id"
        :name="agent.name"
        :role="agent.description || '数字员工'"
        :state="getAgentState(agent)"
        :color="agentGradient(agent)"
        :is-current="chat.currentAgent?.id === agent.id"
        :tasks="agent.task_count"
        :last-active="agent.last_active"
        @click="openChat(agent)"
      />
    </div>

    <div v-if="!agents.length" class="ws-empty">
      <svg class="ws-empty-icon" viewBox="0 0 80 80" width="80" height="80" fill="none">
        <rect x="10" y="20" width="60" height="45" rx="6" stroke="currentColor" stroke-width="2" opacity="0.2" />
        <circle cx="40" cy="42" r="12" stroke="currentColor" stroke-width="2" opacity="0.2" />
        <path d="M30 65l4-8h12l4 8H30z" stroke="currentColor" stroke-width="2" opacity="0.2" />
        <animate attributeName="opacity" values="0.4;0.2;0.4" dur="3s" repeatCount="indefinite" />
      </svg>
      <p class="ws-empty-text">暂无可用数字员工</p>
      <p class="ws-empty-hint">前往后台创建数字员工后即可在此查看</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { api } from '@/api'
import { useChat } from '@/stores/chat'
import { agentGradient } from '@/utils/agent-colors'
import AgentWorkstation from '@/components/AgentWorkstation.vue'
import { Grid, Monitor, ChatDotRound } from '@element-plus/icons-vue'

const emit = defineEmits<{
  selectAgent: [agent: any]
}>()

const chat = useChat()
const agents = ref<any[]>([])
const viewMode = ref<'grid' | 'workstation'>('workstation')

onMounted(async () => {
  try {
    const res = await api.agents()
    agents.value = res.items ?? res
  } catch (e) {
    console.error('Failed to load agents:', e)
  }
})

function agentInitial(agent: any) {
  return (agent.name || '').charAt(0)
}

function getAgentState(agent: any): 'idle' | 'thinking' | 'working' | 'error' {
  if (!agent.enabled) return 'idle'
  return 'idle'
}

const stats = computed(() => {
  const total = agents.value.length
  const working = agents.value.filter(a => getAgentState(a) === 'working').length
  const idle = agents.value.filter(a => getAgentState(a) === 'idle').length
  const offline = agents.value.filter(a => !a.enabled).length
  return [
    { label: '总员工', count: total, color: 'var(--m-text)' },
    { label: '工作中', count: working, color: 'var(--m-success)' },
    { label: '空闲', count: idle, color: 'var(--m-text-secondary)' },
    { label: '离线', count: offline, color: 'var(--m-text-tertiary)' },
  ]
})

async function openChat(agent: any) {
  chat.currentAgent = agent
  emit('selectAgent', agent)
}
</script>

<style scoped>
.workstation-tab {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* overview bar */
.ws-overview {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 16px 20px;
  background: var(--m-surface);
  border: 1px solid var(--m-border);
  border-radius: 12px;
}
.ws-overview-left { flex-shrink: 0; }
.ws-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--m-text);
  display: flex;
  align-items: center;
  gap: 8px;
}
.ws-title-count {
  font-size: 12px;
  font-weight: 500;
  color: var(--m-text-secondary);
  background: var(--m-bg-soft);
  padding: 1px 8px;
  border-radius: 8px;
}
.ws-overview-center {
  flex: 1;
  display: flex;
  gap: 20px;
  justify-content: center;
}
.ws-stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}
.ws-stat-value {
  font-size: 20px;
  font-weight: 700;
  line-height: 1;
}
.ws-stat-label {
  font-size: 11px;
  color: var(--m-text-tertiary);
}
.ws-overview-right { flex-shrink: 0; }

/* card view */
.ws-card-view {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 14px;
  overflow-y: auto;
  align-content: start;
}
.ws-card {
  display: flex;
  gap: 16px;
  padding: 16px;
  background: var(--m-surface);
  border: 1px solid var(--m-border);
  border-radius: 12px;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}
.ws-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0,0,0,0.06);
}
.ws-card-avatar {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 18px;
  font-weight: 600;
  flex-shrink: 0;
}
.ws-card-avatar img {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  object-fit: cover;
}
.ws-card-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.ws-card-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--m-text);
}
.ws-card-desc {
  font-size: 12px;
  color: var(--m-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ws-card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 4px;
}
.ws-card-status {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: var(--m-text-secondary);
}
.ws-card-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}
.ws-card-status.on .ws-card-dot {
  background: var(--m-success);
  box-shadow: 0 0 0 2px var(--m-success-soft);
}
.ws-card-status.off .ws-card-dot {
  background: var(--m-text-tertiary);
}

/* station view */
.ws-station-view {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 18px;
  overflow-y: auto;
  align-content: start;
}

/* empty */
.ws-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--m-text-secondary);
}
.ws-empty-icon { margin-bottom: 4px; }
.ws-empty-text { font-size: 15px; font-weight: 500; margin: 0; }
.ws-empty-hint { font-size: 12px; color: var(--m-text-tertiary); margin: 0; }
</style>
