<template>
  <div class="page mcp-page">
    <div class="page-head">
      <span class="page-title">连接器管理</span>
      <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon>新建连接</el-button>
    </div>

    <!-- 连接器卡片网格 -->
    <div class="mcp-grid">
      <div
        v-for="mcp in rows"
        :key="mcp.id"
        class="mcp-card"
        :class="{ 'is-connected': statuses[mcp.id] === 'ok', 'is-disabled': !mcp.enabled }"
        @click="openTools(mcp)"
      >
        <!-- 连接状态光效 -->
        <div class="connection-glow" :class="statuses[mcp.id] || 'unknown'"></div>

        <!-- 卡片内容 -->
        <div class="card-content">
          <!-- 头部：图标 + 状态 -->
          <div class="card-header">
            <div class="mcp-icon" :style="getIconStyle(mcp)" @click.stop="openIconUpload(mcp)">
              <img v-if="mcp.icon_url" :src="mcp.icon_url" alt="" class="icon-img" />
              <el-icon v-else><Connection /></el-icon>
            </div>
            <div class="status-badge" :class="statuses[mcp.id] || 'unknown'">
              <span class="status-dot"></span>
              <span class="status-text">{{ getStatusText(statuses[mcp.id]) }}</span>
            </div>
          </div>

          <!-- 名称和描述 -->
          <div class="card-body">
            <h3 class="mcp-name">{{ mcp.name }}</h3>
            <p class="mcp-command">{{ summarize(mcp) }}</p>
            <p class="mcp-desc">{{ mcp.user_summary || '暂无使用说明' }}</p>
          </div>

          <!-- 协议标签 -->
          <div class="card-tags">
            <span class="transport-tag" :class="mcp.transport">
              {{ mcp.transport.toUpperCase() }}
            </span>
            <span v-if="statuses[mcp.id + '_count']" class="tool-count">
              {{ statuses[mcp.id + '_count'] }} 个工具
            </span>
          </div>

          <!-- 操作按钮 -->
          <div class="card-actions">
            <button class="action-btn" @click.stop="testConnect(mcp)">
              <el-icon><VideoPlay /></el-icon>
              测试
            </button>
            <button class="action-btn" @click.stop="openEdit(mcp)">
              <el-icon><Edit /></el-icon>
              编辑
            </button>
            <button class="action-btn danger" @click.stop="onDelete(mcp)">
              <el-icon><Delete /></el-icon>
            </button>
          </div>
        </div>
      </div>

      <!-- 新建卡片 -->
      <div class="mcp-card add-card" @click="openCreate">
        <div class="add-content">
          <el-icon class="add-icon"><Plus /></el-icon>
          <span class="add-text">新建连接</span>
        </div>
      </div>
    </div>

    <!-- 编辑弹窗 -->
    <el-dialog v-model="visible" :title="editing ? '编辑连接器' : '新建连接器'" width="640px">
      <el-form :model="form" label-width="100px">
        <!-- 图标上传 -->
        <el-form-item label="图标">
          <div class="icon-upload-area">
            <div class="icon-preview" :style="getIconStyle(form)">
              <img v-if="form.icon_url" :src="form.icon_url" alt="" class="icon-img" />
              <el-icon v-else><Connection /></el-icon>
            </div>
            <div class="icon-actions">
              <el-upload
                :show-file-list="false"
                :before-upload="beforeIconUpload"
                :on-success="onIconUploadSuccess"
                :action="`/api/admin/mcp/${editing?.id || 'new'}/icon`"
                accept="image/*"
              >
                <el-button size="small" type="primary" :disabled="!editing">
                  <el-icon><Upload /></el-icon>
                  上传 Logo
                </el-button>
              </el-upload>
              <div class="icon-tip">支持 JPG/PNG，建议 128x128px</div>
            </div>
          </div>
        </el-form-item>

        <el-form-item label="名称">
          <el-input v-model="form.name" placeholder="例如 filesystem" />
        </el-form-item>
        <el-form-item label="协议">
          <el-radio-group v-model="form.transport">
            <el-radio-button value="stdio">stdio</el-radio-button>
            <el-radio-button value="sse">sse</el-radio-button>
            <el-radio-button value="http">http</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <!-- stdio -->
        <template v-if="form.transport === 'stdio'">
          <el-form-item label="命令">
            <el-input v-model="form.config_json.command" placeholder="如 npx" />
          </el-form-item>
          <el-form-item label="参数">
            <el-input v-model="argsText" placeholder='JSON 数组' />
          </el-form-item>
          <el-form-item label="环境变量">
            <el-input v-model="envText" type="textarea" :rows="3" placeholder='JSON 对象' />
          </el-form-item>
        </template>

        <!-- sse / http -->
        <template v-else>
          <el-form-item label="URL">
            <el-input v-model="form.config_json.url" placeholder="https://server.com/sse" />
          </el-form-item>
          <el-form-item label="请求头">
            <el-input v-model="headersText" type="textarea" :rows="3" placeholder='JSON 对象' />
          </el-form-item>
        </template>

        <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" @click="onSubmit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 工具列表抽屉 -->
    <el-drawer v-model="toolsVisible" :size="640" direction="rtl" :title="drawerTitle">
      <div v-if="toolsLoading" class="loading-state">
        <el-icon class="is-loading" :size="28"><Loading /></el-icon>
        <div>连接中...</div>
      </div>
      <div v-else-if="toolsError" class="error-state">
        <el-alert :title="toolsError" type="error" :closable="false" show-icon />
      </div>
      <div v-else-if="toolsData" class="tools-content">
        <!-- 服务器信息 -->
        <div class="server-info">
          <div class="server-icon-wrapper" :style="getIconStyle(currentRow)">
            <img v-if="currentRow?.icon_url" :src="currentRow.icon_url" alt="" class="server-icon-img" />
            <el-icon v-else class="server-icon"><Connection /></el-icon>
          </div>
          <div class="server-details">
            <h3>{{ toolsData.server.name }}</h3>
            <p v-if="toolsData.server.version">v{{ toolsData.server.version }}</p>
            <p class="tool-count">共 {{ toolsData.tools.length }} 个工具</p>
          </div>
        </div>

        <!-- 工具列表 -->
        <div class="tools-list">
          <div v-for="(t, i) in toolsData.tools" :key="i" class="tool-card">
            <div class="tool-header">
              <div class="tool-icon">⚡</div>
              <div class="tool-name">{{ t.name }}</div>
            </div>
            <p v-if="t.description" class="tool-desc">{{ t.description }}</p>
            <details v-if="t.input_schema && Object.keys(t.input_schema).length" class="tool-schema">
              <summary>输入参数</summary>
              <pre>{{ JSON.stringify(t.input_schema, null, 2) }}</pre>
            </details>
          </div>
        </div>

        <div v-if="!toolsData.tools.length" class="empty-tools">
          该服务器没有暴露任何工具
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'
import { agentGradient } from '@/utils/agent-colors'

const rows = ref<any[]>([])
const visible = ref(false)
const editing = ref<any | null>(null)
const form = reactive<any>({ name: '', transport: 'stdio', config_json: {}, enabled: true, icon_url: '' })
const argsText = ref('[]')
const envText = ref('{}')
const headersText = ref('{}')
const statuses = reactive<Record<string | number, any>>({})

const toolsVisible = ref(false)
const toolsLoading = ref(false)
const toolsError = ref('')
const toolsData = ref<any>(null)
const currentRow = ref<any>(null)
const drawerTitle = computed(() => currentRow.value ? `${currentRow.value.name} · 工具列表` : '工具列表')

function getIconStyle(mcp: any) {
  if (mcp.icon_url) return {}
  return { background: agentGradient(mcp) }
}

watch(visible, (v) => {
  if (!v) return
  argsText.value = JSON.stringify(form.config_json.args || [], null, 0)
  envText.value = JSON.stringify(form.config_json.env || {}, null, 2)
  headersText.value = JSON.stringify(form.config_json.headers || {}, null, 2)
})

async function load() {
  const res = await api.mcps()
  rows.value = res.items || res
}
onMounted(load)

function summarize(row: any) {
  const c = row.config_json || {}
  if (row.transport === 'stdio') return `${c.command || '?'} ${(c.args || []).join(' ')}`.trim()
  return c.url || ''
}

function getStatusText(status: string) {
  const map: Record<string, string> = {
    ok: '已连接',
    fail: '连接失败',
    loading: '连接中...',
  }
  return map[status] || '未测试'
}

function openCreate() {
  editing.value = null
  Object.assign(form, { name: '', transport: 'stdio', config_json: {}, enabled: true, icon_url: '' })
  argsText.value = '[]'; envText.value = '{}'; headersText.value = '{}'
  visible.value = true
}

function openEdit(row: any) {
  editing.value = row
  Object.assign(form, JSON.parse(JSON.stringify(row)))
  visible.value = true
}

function openIconUpload(mcp: any) {
  // 如果是编辑模式，可以上传图标
}

function beforeIconUpload(file: File) {
  const isImage = file.type.startsWith('image/')
  const isLt2M = file.size / 1024 / 1024 < 2

  if (!isImage) {
    ElMessage.error('只能上传图片文件')
    return false
  }
  if (!isLt2M) {
    ElMessage.error('图片大小不能超过 2MB')
    return false
  }
  return true
}

function onIconUploadSuccess(response: any) {
  if (response.icon_url) {
    form.icon_url = response.icon_url
    ElMessage.success('图标上传成功')
  }
}

async function onSubmit() {
  try {
    const payload = JSON.parse(JSON.stringify(form))
    if (payload.transport === 'stdio') {
      try { payload.config_json.args = JSON.parse(argsText.value) } catch { payload.config_json.args = [] }
      try { payload.config_json.env = JSON.parse(envText.value) } catch { payload.config_json.env = {} }
    } else {
      try { payload.config_json.headers = JSON.parse(headersText.value) } catch { payload.config_json.headers = {} }
    }
    if (editing.value) await api.updateMcp(editing.value.id, payload)
    else await api.createMcp(payload)
    visible.value = false
    ElMessage.success('保存成功')
    await load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '保存失败')
  }
}

async function onDelete(row: any) {
  try {
    await ElMessageBox.confirm(`确认删除 ${row.name}？`, '确认', { type: 'warning' })
    await api.deleteMcp(row.id)
    ElMessage.success('已删除')
    await load()
  } catch {}
}

async function testConnect(row: any) {
  statuses[row.id] = 'loading'
  try {
    const r = await api.pingMcp(row.id)
    if (r.ok) {
      statuses[row.id] = 'ok'
      statuses[row.id + '_count'] = r.tool_count ?? r.tools?.length ?? 0
      ElMessage.success(`连接成功，${statuses[row.id + '_count']} 个工具`)
    } else {
      statuses[row.id] = 'fail'
      ElMessage.error(r.error || '连接失败')
    }
  } catch (e: any) {
    statuses[row.id] = 'fail'
    ElMessage.error(e?.response?.data?.detail || '连接失败')
  }
}

async function openTools(row: any) {
  currentRow.value = row
  toolsVisible.value = true
  toolsLoading.value = true
  toolsError.value = ''
  toolsData.value = null
  try {
    const r = await api.pingMcp(row.id)
    if (r.ok) {
      toolsData.value = { server: r.server || { name: row.name }, tools: r.tools || [] }
      statuses[row.id] = 'ok'
      statuses[row.id + '_count'] = r.tool_count ?? r.tools?.length ?? 0
    } else {
      toolsError.value = r.error || '连接失败'
      statuses[row.id] = 'fail'
    }
  } catch (e: any) {
    toolsError.value = e?.response?.data?.detail || '连接失败'
    statuses[row.id] = 'fail'
  } finally {
    toolsLoading.value = false
  }
}
</script>

<style scoped>
.mcp-page {
  background: var(--m-bg);
  min-height: 100vh;
}

/* 卡片网格 */
.mcp-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 24px;
}

/* 连接器卡片 */
.mcp-card {
  position: relative;
  border-radius: 16px;
  background: var(--m-surface);
  border: 1px solid var(--m-border);
  overflow: hidden;
  cursor: pointer;
  transition: all 0.2s ease;
}

.mcp-card:hover {
  border-color: var(--m-border-strong);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

/* 连接状态光效 */
.connection-glow {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: var(--m-border);
  transition: all 0.3s ease;
}

.connection-glow.ok {
  background: var(--m-success);
}

.connection-glow.fail {
  background: var(--m-danger);
}

.connection-glow.loading {
  background: var(--m-primary);
  animation: loadingPulse 1.5s ease infinite;
}

@keyframes loadingPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* 卡片内容 */
.card-content {
  padding: 20px;
  position: relative;
  z-index: 1;
  background: var(--m-surface);
}

/* 头部 */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

/* 图标 */
.mcp-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  color: var(--m-surface);
  background: var(--m-primary);
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.2s ease;
}

.mcp-icon:hover {
  transform: scale(1.05);
}

.icon-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* 状态徽章 */
.status-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
}

.status-badge.ok {
  background: rgba(34, 197, 94, 0.1);
  color: var(--m-success);
}

.status-badge.fail {
  background: rgba(220, 38, 38, 0.1);
  color: var(--m-danger);
}

.status-badge.loading {
  background: var(--m-primary-soft);
  color: var(--m-primary);
}

.status-badge.unknown {
  background: var(--m-bg-soft);
  color: var(--m-text-secondary);
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

/* 名称 */
.mcp-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--m-text);
  margin: 0 0 4px 0;
}

.mcp-command {
  font-size: 12px;
  color: var(--m-text-tertiary);
  font-family: 'Roboto Mono', monospace;
  margin: 0 0 12px 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mcp-desc {
  font-size: 14px;
  color: var(--m-text-secondary);
  margin: 0 0 16px 0;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 标签 */
.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.transport-tag {
  padding: 4px 10px;
  border-radius: 8px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.transport-tag.stdio {
  background: var(--m-primary-soft);
  color: var(--m-primary);
}

.transport-tag.sse {
  background: rgba(34, 197, 94, 0.1);
  color: var(--m-success);
}

.transport-tag.http {
  background: rgba(234, 88, 12, 0.1);
  color: var(--m-warning);
}

.tool-count {
  padding: 4px 10px;
  border-radius: 8px;
  font-size: 12px;
  background: var(--m-bg-soft);
  color: var(--m-text-secondary);
}

/* 操作按钮 */
.card-actions {
  display: flex;
  gap: 8px;
  padding-top: 16px;
  border-top: 1px solid var(--m-border);
}

.action-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 8px 12px;
  border: none;
  border-radius: 8px;
  background: var(--m-bg-soft);
  color: var(--m-text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.action-btn:hover {
  background: var(--m-border);
  color: var(--m-text);
}

.action-btn.danger {
  flex: 0;
  padding: 8px 12px;
}

.action-btn.danger:hover {
  background: rgba(220, 38, 38, 0.1);
  color: var(--m-danger);
}

/* 新建卡片 */
.add-card {
  border: 2px dashed var(--m-border);
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 280px;
}

.add-card:hover {
  border-color: var(--m-primary);
  background: var(--m-primary-soft);
}

.add-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: var(--m-text-secondary);
}

.add-icon {
  font-size: 32px;
  color: var(--m-primary);
}

.add-text {
  font-size: 14px;
  font-weight: 500;
}

/* 禁用状态 */
.is-disabled {
  opacity: 0.6;
}

/* 图标上传区域 */
.icon-upload-area {
  display: flex;
  align-items: center;
  gap: 16px;
}

.icon-preview {
  width: 64px;
  height: 64px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--m-primary);
  overflow: hidden;
  flex-shrink: 0;
  color: var(--m-surface);
  font-size: 24px;
}

.icon-preview .icon-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.icon-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.icon-tip {
  font-size: 12px;
  color: var(--m-text-tertiary);
}

/* 工具抽屉 */
.loading-state,
.error-state {
  text-align: center;
  padding: 40px;
  color: var(--m-text-secondary);
}

.tools-content {
  padding: 0;
}

.server-info {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: var(--m-bg-soft);
  border-bottom: 1px solid var(--m-border);
}

.server-icon-wrapper {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--m-primary);
  overflow: hidden;
  color: var(--m-surface);
  font-size: 20px;
  flex-shrink: 0;
}

.server-icon-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.server-details h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 4px 0;
}

.server-details p {
  font-size: 13px;
  color: var(--m-text-secondary);
  margin: 0;
}

.tools-list {
  padding: 16px;
}

.tool-card {
  padding: 16px;
  background: var(--m-surface);
  border: 1px solid var(--m-border);
  border-radius: 12px;
  margin-bottom: 12px;
}

.tool-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.tool-icon {
  font-size: 16px;
}

.tool-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--m-text);
  font-family: 'Roboto Mono', monospace;
}

.tool-desc {
  font-size: 13px;
  color: var(--m-text-secondary);
  margin: 0 0 12px 0;
  line-height: 1.5;
}

.tool-schema {
  border: 1px solid var(--m-border);
  border-radius: 8px;
  overflow: hidden;
}

.tool-schema summary {
  padding: 8px 12px;
  background: var(--m-bg-soft);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
}

.tool-schema pre {
  margin: 0;
  padding: 12px;
  font-size: 12px;
  line-height: 1.5;
  overflow-x: auto;
  background: var(--m-bg-soft);
}

.empty-tools {
  text-align: center;
  padding: 40px;
  color: var(--m-text-secondary);
}
</style>
