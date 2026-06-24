<template>
  <div class="wf-page">
    <div class="wf-toolbar">
      <el-button text @click="goBack">← 返回</el-button>
      <span class="wf-title">{{ isNew ? '新建工作流' : wf.name }}</span>
      <div class="wf-actions">
        <el-button size="small" @click="onSave">保存</el-button>
        <el-button size="small" @click="onCompile">编译</el-button>
        <el-button size="small" type="primary" :loading="runLoading" @click="onRun">运行</el-button>
      </div>
    </div>

    <div class="wf-body">
      <!-- 节点选择面板 -->
      <div class="wf-palette">
        <div class="palette-title">节点类型</div>
        <div v-for="nt in nodeTypes" :key="nt.type" class="palette-item" draggable="true" @dragstart="onDragStart($event, nt)">
          <div class="palette-icon">{{ nt.icon }}</div>
          <div class="palette-label">{{ nt.label }}</div>
        </div>
      </div>

      <!-- 画布 -->
      <div class="wf-canvas" ref="canvasRef">
        <VueFlow v-model:nodes="flowNodes" v-model:edges="flowEdges" @node-click="onNodeClick" @pane-click="onPaneClick" fit-view-on-init>
          <Background :style="{ '--pattern-color': 'var(--m-border)' }" :gap="20" />
          <Controls />
          <template #node-custom="props">
            <div class="custom-node" :class="`node-${props.data.type}`" @click.stop="onNodeClick(props)">
              <div class="node-icon">{{ nodeTypeIcon(props.data.type) }}</div>
              <div class="node-label">{{ props.data.label || props.id }}</div>
              <div v-if="props.data.type === 'condition'" class="node-badge">分支</div>
              <div v-if="props.data.type === 'human_approval'" class="node-badge approval">审批</div>
            </div>
          </template>
        </VueFlow>
      </div>

      <!-- 节点配置面板 -->
      <div v-if="selectedNode" class="wf-config">
        <div class="config-title">节点配置</div>
        <div class="config-field">
          <label>ID</label>
          <el-input v-model="selectedNode.id" size="small" disabled />
        </div>
        <div class="config-field">
          <label>名称</label>
          <el-input v-model="selectedNode.data.label" size="small" />
        </div>
        <div class="config-field" v-if="selectedNode.data.type === 'agent'">
          <label>Agent 编码</label>
          <el-input v-model="selectedNode.data.agent_code" size="small" placeholder="agent-code" />
        </div>
        <div class="config-field" v-if="selectedNode.data.type === 'skill'">
          <label>Skill 编码</label>
          <el-input v-model="selectedNode.data.skill_id" size="small" placeholder="skill-code" />
        </div>
        <div class="config-field" v-if="selectedNode.data.type === 'human_approval'">
          <label>审批角色</label>
          <el-select v-model="selectedNode.data.role" size="small" style="width:100%">
            <el-option label="管理员" value="admin" />
            <el-option label="运营者" value="operator" />
          </el-select>
        </div>
        <div class="config-field" v-if="selectedNode.data.type === 'notification'">
          <label>通知消息</label>
          <el-input v-model="selectedNode.data.message" size="small" type="textarea" :rows="2" />
        </div>
        <div class="config-actions"><el-button size="small" type="danger" @click="deleteNode">删除节点</el-button></div>
      </div>
      <div v-else class="wf-config wf-config-empty">
        <p>点击节点编辑配置<br/>拖拽左侧节点到画布</p>
      </div>
    </div>

    <!-- YAML 预览 -->
    <el-dialog v-model="yamlVisible" title="编译结果" width="720px">
      <pre class="yaml-pre">{{ compiledYaml }}</pre>
    </el-dialog>

    <!-- 运行状态面板 -->
    <el-drawer v-model="runDrawerVisible" title="运行状态" direction="rtl" size="420px">
      <div v-if="currentRun" class="run-detail">
        <div class="run-status-row">
          <span class="run-label">状态</span>
          <el-tag :type="runStatusType(currentRun.status)" size="small">{{ runStatusText(currentRun.status) }}</el-tag>
        </div>
        <div class="run-status-row">
          <span class="run-label">开始时间</span>
          <span>{{ currentRun.started_at || '-' }}</span>
        </div>
        <div class="run-status-row">
          <span class="run-label">完成时间</span>
          <span>{{ currentRun.finished_at || '-' }}</span>
        </div>
        <div v-if="currentRun.error" class="run-error">
          <div class="run-label">错误信息</div>
          <pre>{{ currentRun.error }}</pre>
        </div>
        <div v-if="currentRun.output" class="run-output">
          <div class="run-label">输出结果</div>
          <pre>{{ JSON.stringify(currentRun.output, null, 2) }}</pre>
        </div>
      </div>
      <div v-else class="run-empty">暂无运行记录</div>

      <el-divider />
      <div class="run-history-title">运行历史</div>
      <div v-if="runHistory.length === 0" class="run-empty">暂无历史</div>
      <div v-for="r in runHistory" :key="r.id" class="run-history-item" @click="currentRun = r">
        <span class="run-history-id">#{{ r.id }}</span>
        <el-tag :type="runStatusType(r.status)" size="small">{{ runStatusText(r.status) }}</el-tag>
        <span class="run-history-time">{{ r.started_at }}</span>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '@/api'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'

const route = useRoute()
const router = useRouter()
const wfId = route.params.id as string
const isNew = wfId === 'new'
const wf = ref<any>({ name: '新建工作流', description: '' })
const flowNodes = ref<any[]>([])
const flowEdges = ref<any[]>([])
const selectedNode = ref<any>(null)
const compiledYaml = ref('')
const yamlVisible = ref(false)

// 运行状态相关
const runLoading = ref(false)
const runDrawerVisible = ref(false)
const currentRun = ref<any>(null)
const runHistory = ref<any[]>([])
let pollTimer: ReturnType<typeof setInterval> | null = null

const nodeTypes = [
  { type: 'skill', label: '执行技能', icon: '⚡', defaultConfig: {} },
  { type: 'agent', label: 'Agent 处理', icon: '🤖', defaultConfig: { agent_code: '' } },
  { type: 'human_approval', label: '人工审批', icon: '👤', defaultConfig: { role: 'admin' } },
  { type: 'condition', label: '条件分支', icon: '🔀', defaultConfig: {} },
  { type: 'notification', label: '发送通知', icon: '🔔', defaultConfig: { message: '' } },
  { type: 'parallel_group', label: '并行执行', icon: '⚡', defaultConfig: { wait_strategy: 'all_success' } },
]

function nodeTypeIcon(type: string) {
  return nodeTypes.find(n => n.type === type)?.icon || '⚙'
}

function onDragStart(event: DragEvent, nt: any) {
  event.dataTransfer?.setData('application/json', JSON.stringify(nt))
}

const { onConnect, addEdges, fitView } = useVueFlow('workflow-editor')
onConnect((connection: any) => {
  flowEdges.value.push({ ...connection, type: 'smoothstep', animated: true })
})

async function load() {
  if (isNew) return
  try {
    const r = await api.request(`/api/admin/workflows/${wfId}`)
    wf.value = r
    const def = r.definition_json || {}
    flowNodes.value = (def.nodes || []).map((n: any) => ({
      id: n.id, type: 'custom', position: n.position || { x: 100, y: 100 },
      data: { label: n.label, type: n.type, ...n.config },
    }))
    flowEdges.value = (def.edges || []).map((e: any) => ({
      id: `${e.source}->${e.target}`, source: e.source, target: e.target,
      type: 'smoothstep', animated: true, label: e.label || '',
    }))
  } catch { ElMessage.error('加载失败') }
}

function onNodeClick(node: any) {
  selectedNode.value = node
}

function onPaneClick() {
  selectedNode.value = null
}

function deleteNode() {
  if (!selectedNode.value) return
  flowNodes.value = flowNodes.value.filter((n: any) => n.id !== selectedNode.value.id)
  flowEdges.value = flowEdges.value.filter((e: any) => e.source !== selectedNode.value.id && e.target !== selectedNode.value.id)
  selectedNode.value = null
}

function serialize() {
  return {
    nodes: flowNodes.value.map((n: any) => {
      const config = { ...n.data }
      delete config.label; delete config.type
      return { id: n.id, label: n.data?.label || n.id, type: n.data?.type || 'skill', position: n.position, config }
    }),
    edges: flowEdges.value.map((e: any) => ({ source: e.source, target: e.target, label: e.label })),
  }
}

async function onSave() {
  const data = { name: wf.value.name, description: wf.value.description, definition_json: serialize() }
  try {
    if (isNew) {
      const r = await api.request('/api/admin/workflows', { method: 'POST', data })
      wf.value = r
      router.replace(`/admin/workflows/${r.id}`).catch(() => {})
    } else {
      await api.request(`/api/admin/workflows/${wfId}`, { method: 'PUT', data })
    }
    ElMessage.success('已保存')
  } catch { ElMessage.error('保存失败') }
}

async function onCompile() {
  const data = { name: wf.value.name, description: wf.value.description, definition_json: serialize() }
  try {
    if (isNew) {
      const r = await api.request('/api/admin/workflows', { method: 'POST', data })
      wf.value = r
      router.replace(`/admin/workflows/${r.id}`).catch(() => {})
    } else {
      await api.request(`/api/admin/workflows/${wfId}`, { method: 'PUT', data })
    }
    const r = await api.request(`/api/admin/workflows/${wf.value.id}/compile`, { method: 'POST' })
    compiledYaml.value = r.yaml
    yamlVisible.value = true
  } catch { ElMessage.error('编译失败') }
}

async function onRun() {
  runLoading.value = true
  try {
    // 先保存
    await onSave()
    // 发起运行
    const r = await api.request(`/api/admin/workflows/${wf.value.id}/run`, { method: 'POST' })
    ElMessage.success(`工作流已运行，run_id: ${r.run_id}`)

    // 打开运行状态面板
    runDrawerVisible.value = true
    currentRun.value = { id: r.run_id, status: 'running', started_at: new Date().toISOString() }

    // 开始轮询状态
    startPolling(r.run_id)
    await refreshRunHistory()
  } catch {
    ElMessage.error('运行失败')
  } finally {
    runLoading.value = false
  }
}

function startPolling(runId: number) {
  stopPolling()
  pollTimer = setInterval(async () => {
    try {
      const r = await api.request(`/api/admin/workflows/runs/${runId}`)
      currentRun.value = r
      if (r.status === 'success' || r.status === 'failed') {
        stopPolling()
        await refreshRunHistory()
        if (r.status === 'success') {
          ElMessage.success('工作流执行完成')
        } else {
          ElMessage.error(`工作流执行失败: ${r.error || '未知错误'}`)
        }
      }
    } catch { /* 静默 */ }
  }, 2000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function refreshRunHistory() {
  if (isNew || !wf.value.id) return
  try {
    const r = await api.request(`/api/admin/workflows/${wf.value.id}/runs?limit=20`)
    runHistory.value = r
  } catch { /* 静默 */ }
}

function runStatusType(status: string) {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'danger'
  return 'warning'
}

function runStatusText(status: string) {
  const map: Record<string, string> = { running: '运行中', success: '成功', failed: '失败' }
  return map[status] || status
}

function goBack() { router.push('/admin/workflows').catch(() => {}) }

onMounted(() => {
  load()
  if (!isNew) refreshRunHistory()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.wf-page { display: flex; flex-direction: column; height: calc(100vh - 60px); }
.wf-toolbar { display: flex; align-items: center; gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--m-border); }
.wf-title { font-size: 16px; font-weight: 600; flex: 1; }
.wf-actions { display: flex; gap: 8px; }
.wf-body { display: flex; flex: 1; min-height: 0; }
.wf-palette { width: 140px; border-right: 1px solid var(--m-border); padding: 12px; overflow-y: auto; }
.palette-title { font-size: 12px; font-weight: 600; color: var(--m-text-secondary); margin-bottom: 8px; }
.palette-item { display: flex; align-items: center; gap: 8px; padding: 6px 8px; border-radius: 6px; cursor: grab; margin-bottom: 4px; }
.palette-item:hover { background: var(--m-surface-variant); }
.palette-icon { font-size: 18px; }
.palette-label { font-size: 12px; }
.wf-canvas { flex: 1; min-width: 0; }
.wf-canvas :deep(.vue-flow__background) { --pattern-color: var(--m-border); }
.wf-config { width: 260px; border-left: 1px solid var(--m-border); padding: 12px; overflow-y: auto; }
.wf-config-empty { display: flex; align-items: center; justify-content: center; text-align: center; color: var(--m-text-tertiary); font-size: 13px; }
.config-title { font-size: 13px; font-weight: 600; margin-bottom: 12px; }
.config-field { margin-bottom: 10px; }
.config-field label { display: block; font-size: 11px; color: var(--m-text-secondary); margin-bottom: 4px; }
.config-actions { margin-top: 16px; }
.custom-node { padding: 10px 16px; border-radius: 8px; background: var(--m-surface); border: 2px solid var(--m-border); font-size: 12px; text-align: center; min-width: 100px; cursor: pointer; }
.custom-node:hover { border-color: var(--m-primary); }
.node-skill { border-color: var(--m-primary); }
.node-agent { border-color: var(--m-success); }
.node-human_approval { border-color: var(--m-warning); }
.node-condition { border-color: var(--m-danger); }
.node-notification { border-color: var(--m-info, #ab47bc); }
.node-badge { font-size: 10px; background: var(--m-danger); color: var(--m-on-primary); border-radius: 4px; padding: 1px 6px; display: inline-block; margin-top: 4px; }
.node-badge.approval { background: var(--m-warning); color: var(--m-text); }
.node-icon { font-size: 20px; }
.node-label { font-size: 11px; margin-top: 4px; color: var(--m-text); }
.yaml-pre { margin: 0; padding: 12px; background: var(--m-bg-soft); border-radius: 8px; font-size: 12px; max-height: 60vh; overflow: auto; }

/* 运行状态面板样式 */
.run-detail { padding: 0; }
.run-status-row { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid var(--m-border); }
.run-label { font-size: 12px; font-weight: 600; color: var(--m-text-secondary); }
.run-error { margin-top: 12px; }
.run-error pre { margin: 4px 0 0; padding: 8px; background: rgba(217, 48, 37, 0.08); border-radius: 6px; font-size: 12px; color: var(--m-danger); white-space: pre-wrap; word-break: break-all; }
.run-output { margin-top: 12px; }
.run-output pre { margin: 4px 0 0; padding: 8px; background: var(--m-bg-soft); border-radius: 6px; font-size: 11px; max-height: 300px; overflow: auto; white-space: pre-wrap; }
.run-empty { text-align: center; color: var(--m-text-tertiary); font-size: 13px; padding: 24px 0; }
.run-history-title { font-size: 13px; font-weight: 600; margin-bottom: 8px; }
.run-history-item { display: flex; align-items: center; gap: 8px; padding: 8px; border-radius: 6px; cursor: pointer; margin-bottom: 4px; }
.run-history-item:hover { background: var(--m-surface-variant); }
.run-history-id { font-size: 12px; font-weight: 600; color: var(--m-text-secondary); }
.run-history-time { font-size: 11px; color: var(--m-text-tertiary); margin-left: auto; }

@media (max-width: 1024px) {
  .wf-body { flex-direction: column; }
  .wf-palette { width: 100%; max-height: 120px; overflow-x: auto; flex-direction: row; flex-wrap: wrap; border-right: none; border-bottom: 1px solid var(--m-border); }
  .palette-title { display: none; }
  .palette-item { min-width: 100px; }
  .wf-canvas { min-height: 300px; }
  .wf-config { width: 100%; border-left: none; border-top: 1px solid var(--m-border); max-height: 200px; }
}
</style>
