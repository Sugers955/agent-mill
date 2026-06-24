<template>
  <div class="workstation-grid">
    <div class="grid-header">
      <h3>数字员工工位</h3>
      <div class="grid-stats">
        <span class="stat working">{{ workingCount }} 工作中</span>
        <span class="stat idle">{{ idleCount }} 空闲</span>
      </div>
    </div>
    <div class="grid-container">
      <AgentWorkstation
        v-for="agent in agents"
        :key="agent.id"
        :name="agent.name"
        :role="agent.role || '数字员工'"
        :state="agent.state"
        :color="agent.color"
        :is-current="currentAgentId === agent.id"
        :progress="agent.progress"
        @click="$emit('select', agent)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AgentWorkstation from './AgentWorkstation.vue'

interface Agent {
  id: number
  name: string
  role?: string
  state: 'idle' | 'thinking' | 'working' | 'error'
  color?: string
  progress?: number
}

const props = defineProps<{
  agents: Agent[]
  currentAgentId?: number
}>()

defineEmits<{
  select: [agent: Agent]
}>()

const workingCount = computed(() => props.agents.filter(a => a.state === 'working').length)
const idleCount = computed(() => props.agents.filter(a => a.state === 'idle').length)
</script>

<style scoped>
.workstation-grid {
  padding: 20px;
}

.grid-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.grid-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #1e293b;
}

.grid-stats {
  display: flex;
  gap: 12px;
}

.stat {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 12px;
  font-weight: 500;
}

.stat.working {
  background: #dcfce7;
  color: #16a34a;
}

.stat.idle {
  background: #e2e8f0;
  color: #64748b;
}

.grid-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 20px;
}
</style>
