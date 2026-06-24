<template>
  <div class="command-center">
    <div class="command-header">
      <div class="ch-left">
        <div class="ch-icon">
          <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <rect x="2" y="3" width="20" height="14" rx="2" />
            <path d="M8 21h8M12 17v4" />
          </svg>
        </div>
        <div class="ch-text">
          <h1 class="ch-title">指挥中心</h1>
          <p class="ch-sub">管理你的数字员工团队，实时监控任务执行</p>
        </div>
      </div>
      <div class="ch-right">
        <QuickAskCards :questions="quickQuestions" @select="onQuickAsk" v-if="activeTab === 'workstation'" />
      </div>
    </div>

    <el-tabs v-model="activeTab" class="command-tabs">
      <el-tab-pane label="工位看板" name="workstation">
        <WorkstationTab @select-agent="onSelectAgent" />
      </el-tab-pane>
      <el-tab-pane label="对话" name="chat">
        <ChatTab />
      </el-tab-pane>
      <el-tab-pane label="任务" name="tasks">
        <TaskTab />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import WorkstationTab from './WorkstationTab.vue'
import ChatTab from './ChatTab.vue'
import TaskTab from './TaskTab.vue'
import QuickAskCards from './QuickAskCards.vue'

const router = useRouter()
const activeTab = ref('workstation')

const quickQuestions = [
  '查看所有在线数字员工',
  '创建批量任务',
  '查看任务执行报告',
  '系统运行状态概览',
]

function onQuickAsk(q: string) {
  if (q === '查看所有在线数字员工') { activeTab.value = 'workstation'; return }
  if (q === '创建批量任务') { router.push('/tasks').catch(() => {}); return }
  if (q === '查看任务执行报告') { router.push('/admin/logs').catch(() => {}); return }
  if (q === '系统运行状态概览') { router.push('/admin/dashboard').catch(() => {}); return }
}

function onSelectAgent(agent: any) {
  activeTab.value = 'chat'
}
</script>

<style scoped>
.command-center {
  padding: 24px 32px;
  height: 100%;
  display: flex;
  flex-direction: column;
  animation: fadeIn 0.3s ease;
}
@keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }

.command-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}
.ch-left { display: flex; align-items: center; gap: 14px; }
.ch-icon {
  width: 44px; height: 44px;
  display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, var(--m-primary), var(--m-primary-hover));
  color: #fff;
  border-radius: 12px;
  flex-shrink: 0;
}
.ch-title {
  font-size: 22px; font-weight: 700;
  color: var(--m-text); margin: 0;
  letter-spacing: -0.3px;
}
.ch-sub {
  font-size: 13px; color: var(--m-text-secondary);
  margin: 4px 0 0 0;
}
.ch-right { flex-shrink: 0; }

.command-tabs { flex: 1; display: flex; flex-direction: column; }
.command-tabs :deep(.el-tabs__header) {
  margin: 0 0 20px 0;
  border-bottom: 1px solid var(--m-border);
}
.command-tabs :deep(.el-tabs__nav-wrap::after) { display: none; }
.command-tabs :deep(.el-tabs__item) {
  font-size: 14px;
  font-weight: 500;
  color: var(--m-text-secondary);
  padding: 0 20px 14px;
  transition: color 0.2s;
}
.command-tabs :deep(.el-tabs__item:hover) { color: var(--m-text); }
.command-tabs :deep(.el-tabs__item.is-active) {
  color: var(--m-primary);
  font-weight: 600;
}
.command-tabs :deep(.el-tabs__active-bar) {
  height: 2.5px;
  border-radius: 2px;
  background: var(--m-primary);
}
.command-tabs :deep(.el-tabs__content) { flex: 1; }
.command-tabs :deep(.el-tab-pane) { height: 100%; }

</style>
