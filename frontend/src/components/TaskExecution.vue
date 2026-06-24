<template>
  <div class="task-execution" :class="{ 'is-expanded': isExpanded }">
    <!-- 执行头部 -->
    <div class="exec-header" @click="isExpanded = !isExpanded">
      <div class="exec-avatar" :style="{ background: agentColor }">
        <div class="avatar-eyes">
          <span class="eye"></span>
          <span class="eye"></span>
        </div>
      </div>
      <div class="exec-info">
        <div class="exec-name">{{ agentName }}</div>
        <div class="exec-status" :class="status">
          <span class="status-dot"></span>
          {{ statusLabel }}
        </div>
      </div>
      <div class="exec-progress-ring" v-if="status === 'working'">
        <svg viewBox="0 0 36 36">
          <path
            class="ring-bg"
            d="M18 2.0845
              a 15.9155 15.9155 0 0 1 0 31.831
              a 15.9155 15.9155 0 0 1 0 -31.831"
          />
          <path
            class="ring-fill"
            :stroke-dasharray="`${progress}, 100`"
            d="M18 2.0845
              a 15.9155 15.9155 0 0 1 0 31.831
              a 15.9155 15.9155 0 0 1 0 -31.831"
          />
        </svg>
        <span class="ring-text">{{ progress }}%</span>
      </div>
      <div class="expand-icon" :class="{ rotated: isExpanded }">▼</div>
    </div>

    <!-- 执行内容 -->
    <transition name="slide">
      <div class="exec-content" v-if="isExpanded">
        <!-- 步骤列表 -->
        <div class="steps">
          <div
            v-for="(step, index) in steps"
            :key="index"
            class="step"
            :class="step.status"
          >
            <div class="step-icon">
              <span v-if="step.status === 'completed'" class="check">✓</span>
              <span v-else-if="step.status === 'running'" class="spinner"></span>
              <span v-else-if="step.status === 'error'" class="error">✗</span>
              <span v-else class="pending">{{ index + 1 }}</span>
            </div>
            <div class="step-content">
              <div class="step-name">{{ step.name }}</div>
              <div class="step-detail" v-if="step.detail">{{ step.detail }}</div>
            </div>
            <div class="step-time" v-if="step.duration">{{ step.duration }}</div>
          </div>
        </div>

        <!-- 实时日志 -->
        <div class="log-panel" v-if="logs.length">
          <div class="log-header">
            <span>执行日志</span>
            <span class="log-count">{{ logs.length }} 条</span>
          </div>
          <div class="log-content" ref="logContainer">
            <div
              v-for="(log, index) in logs"
              :key="index"
              class="log-line"
              :class="log.type"
            >
              <span class="log-time">{{ log.time }}</span>
              <span class="log-msg">{{ log.message }}</span>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'

interface Step {
  name: string
  detail?: string
  status: 'pending' | 'running' | 'completed' | 'error'
  duration?: string
}

interface Log {
  time: string
  type: 'info' | 'success' | 'warning' | 'error'
  message: string
}

const props = defineProps<{
  agentName: string
  agentColor?: string
  status: 'idle' | 'thinking' | 'working' | 'completed' | 'error'
  progress?: number
  steps?: Step[]
  logs?: Log[]
}>()

const isExpanded = ref(true)
const logContainer = ref<HTMLElement>()

const statusLabel = computed(() => {
  const map = {
    idle: '待命中',
    thinking: '思考中',
    working: '执行中',
    completed: '已完成',
    error: '执行异常',
  }
  return map[props.status]
})

// 自动滚动到最新日志
watch(() => props.logs?.length, async () => {
  await nextTick()
  if (logContainer.value) {
    logContainer.value.scrollTop = logContainer.value.scrollHeight
  }
})
</script>

<style scoped>
.task-execution {
  background: var(--m-surface);
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  overflow: hidden;
  transition: all 0.3s ease;
}

.task-execution:hover {
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
}

/* 头部 */
.exec-header {
  display: flex;
  align-items: center;
  padding: 16px;
  gap: 12px;
  cursor: pointer;
}

.exec-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.avatar-eyes {
  display: flex;
  gap: 6px;
}

.eye {
  width: 4px;
  height: 4px;
  background: white;
  border-radius: 50%;
}

.exec-info {
  flex: 1;
  min-width: 0;
}

.exec-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--m-text);
}

.exec-status {
  font-size: 12px;
  color: var(--m-text-secondary);
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 2px;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--m-text-tertiary);
}

.exec-status.thinking .status-dot {
  background: var(--m-warning);
  animation: pulse 1s ease-in-out infinite;
}

.exec-status.working .status-dot {
  background: var(--m-success);
  animation: pulse 0.8s ease-in-out infinite;
}

.exec-status.error .status-dot {
  background: var(--m-danger);
}

/* 进度环 */
.exec-progress-ring {
  position: relative;
  width: 40px;
  height: 40px;
}

.exec-progress-ring svg {
  transform: rotate(-90deg);
}

.ring-bg {
  fill: none;
  stroke: var(--m-surface-variant);
  stroke-width: 3;
}

.ring-fill {
  fill: none;
  stroke: var(--m-success);
  stroke-width: 3;
  stroke-linecap: round;
  transition: stroke-dasharray 0.3s ease;
}

.ring-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 10px;
  font-weight: 600;
  color: var(--m-success);
}

/* 展开图标 */
.expand-icon {
  font-size: 10px;
  color: var(--m-text-tertiary);
  transition: transform 0.3s ease;
}

.expand-icon.rotated {
  transform: rotate(180deg);
}

/* 内容区 */
.exec-content {
  border-top: 1px solid var(--m-border);
  padding: 16px;
}

/* 步骤列表 */
.steps {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.step {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 8px;
  border-radius: 8px;
  transition: background 0.2s ease;
}

.step.running {
  background: var(--m-success-soft);
}

.step.error {
  background: var(--m-danger-soft);
}

.step-icon {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  flex-shrink: 0;
}

.step.completed .step-icon {
  background: var(--m-success);
  color: var(--m-text-inverse);
}

.step.running .step-icon {
  background: var(--m-success);
  color: var(--m-text-inverse);
}

.step.error .step-icon {
  background: var(--m-danger);
  color: var(--m-text-inverse);
}

.step.pending .step-icon {
  background: var(--m-surface-variant);
  color: var(--m-text-secondary);
}

.check, .error {
  font-weight: bold;
}

.spinner {
  width: 12px;
  height: 12px;
  border: 2px solid white;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.step-content {
  flex: 1;
  min-width: 0;
}

.step-name {
  font-size: 13px;
  color: var(--m-text);
  font-weight: 500;
}

.step-detail {
  font-size: 11px;
  color: var(--m-text-secondary);
  margin-top: 2px;
}

.step-time {
  font-size: 11px;
  color: var(--m-text-tertiary);
}

/* 日志面板 */
.log-panel {
  margin-top: 16px;
  border: 1px solid var(--m-border);
  border-radius: 8px;
  overflow: hidden;
}

.log-header {
  display: flex;
  justify-content: space-between;
  padding: 8px 12px;
  background: var(--m-bg);
  font-size: 12px;
  font-weight: 500;
  color: var(--m-text-secondary);
}

.log-content {
  max-height: 150px;
  overflow-y: auto;
  padding: 8px 12px;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 11px;
  line-height: 1.6;
  background: var(--m-text);
}

.log-line {
  color: var(--m-text-tertiary);
}

.log-line.success {
  color: var(--m-success);
}

.log-line.warning {
  color: var(--m-warning);
}

.log-line.error {
  color: var(--m-danger);
}

.log-time {
  color: var(--m-text-secondary);
  margin-right: 8px;
}

/* 动画 */
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.6; transform: scale(0.8); }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s ease;
}

.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}

.slide-enter-to,
.slide-leave-from {
  opacity: 1;
  max-height: 500px;
}
</style>
