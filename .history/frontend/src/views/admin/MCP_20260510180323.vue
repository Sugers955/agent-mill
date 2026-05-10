<template>
  <div class="page">
    <div class="page-head">
      <span class="page-title">MCP 连接器</span>
      <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon>新建连接</el-button>
    </div>
    <el-table :data="rows" stripe @row-click="openTools">
      <el-table-column prop="id" label="ID" width="40" />
      <el-table-column label="名称" min-width="200">
        <template #default="{ row }">
          <div style="display:flex;align-items:center;gap:10px;min-width:0">
            <div class="mcp-icon"><el-icon><Connection /></el-icon></div>
            <div style="min-width:0">
              <div style="font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" :title="row.name">{{ row.name }}</div>
              <div class="row-sub" :title="summarize(row)">{{ summarize(row) }}</div>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="协议" width="80" align="center">
        <template #default="{ row }"><el-tag size="small">{{ row.transport }}</el-tag></template>
      </el-table-column>
      <el-table-column label="使用说明" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.user_summary">{{ row.user_summary }}</span>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag v-if="statuses[row.id] === 'ok'" type="success" size="small">已连接 · {{ statuses[row.id + '_count'] || 0 }}</el-tag>
          <el-tag v-else-if="statuses[row.id] === 'fail'" type="danger" size="small">连接失败</el-tag>
          <el-tag v-else-if="statuses[row.id] === 'loading'" type="info" size="small">连接中…</el-tag>
          <el-tag v-else type="info" size="small">未测试</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="启用" width="60" align="center">
        <template #default="{ row }"><el-tag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? '是' : '否' }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{ row }">
          <div class="row-actions" @click.stop>
            <el-button size="small" text @click.stop="openTools(row)">查看工具</el-button>
            <el-button size="small" text @click.stop="testConnect(row)">测试连接</el-button>
            <el-button size="small" text @click.stop="openEdit(row)">编辑</el-button>
            <el-button size="small" text @click.stop="onResummarize(row)">重新说明</el-button>
            <el-button size="small" text type="danger" @click.stop="onDelete(row)">删除</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <!-- Create / edit dialog -->
    <el-dialog v-model="visible" :title="editing ? '编辑 MCP 连接' : '新建 MCP 连接'" width="640px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="名称">
          <el-input v-model="form.name" placeholder="例如 filesystem" />
        </el-form-item>
        <el-form-item label="协议">
          <el-radio-group v-model="form.transport" @change="onTransportChange">
            <el-radio-button value="stdio">stdio</el-radio-button>
            <el-radio-button value="sse">sse</el-radio-button>
            <el-radio-button value="http">http</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <!-- stdio fields -->
        <template v-if="form.transport === 'stdio'">
          <el-form-item label="命令">
            <el-input v-model="form.config_json.command" placeholder="如 npx" />
          </el-form-item>
          <el-form-item label="参数">
            <el-input v-model="argsText" placeholder='JSON 数组,如 ["@modelcontextprotocol/server-filesystem","/tmp"]' />
          </el-form-item>
          <el-form-item label="环境变量">
            <el-input v-model="envText" type="textarea" :rows="3" placeholder='JSON 对象,如 {"API_KEY":"xxx"}' />
          </el-form-item>
        </template>

        <!-- sse / http fields -->
        <template v-else>
          <el-form-item label="URL">
            <el-input v-model="form.config_json.url" :placeholder="form.transport === 'sse' ? 'https://server.com/sse' : 'https://server.com/mcp'" />
          </el-form-item>
          <el-form-item label="请求头">
            <el-input v-model="headersText" type="textarea" :rows="3" placeholder='JSON 对象,如 {"Authorization":"Bearer xxx"}' />
          </el-form-item>
        </template>

        <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" @click="onSubmit">保存</el-button>
      </template>
    </el-dialog>

    <!-- Tools drawer -->
    <el-drawer v-model="toolsVisible" :size="640" direction="rtl" :title="drawerTitle" :with-header="true">
      <div v-if="toolsLoading" style="text-align:center;padding:40px;color:var(--m-text-secondary)">
        <el-icon class="is-loading" :size="28"><Loading /></el-icon>
        <div style="margin-top:8px">连接中...</div>
      </div>
      <div v-else-if="toolsError" style="padding:20px">
        <el-alert :title="toolsError" type="error" :closable="false" show-icon />
      </div>
      <div v-else-if="toolsData">
        <div class="server-card">
          <div class="server-name">{{ toolsData.server.name }}</div>
          <div v-if="toolsData.server.version" class="muted" style="font-size:12px">v{{ toolsData.server.version }}</div>
          <div class="muted" style="margin-top:8px">共 {{ toolsData.tools.length }} 个工具</div>
        </div>
        <div v-for="(t, i) in toolsData.tools" :key="i" class="tool-card">
          <div class="tool-head">
            <el-icon style="color:var(--m-primary)"><Tools /></el-icon>
            <div class="tool-name mono">{{ t.name }}</div>
          </div>
          <div v-if="t.description" class="tool-desc">{{ t.description }}</div>
          <details v-if="t.input_schema && Object.keys(t.input_schema).length" class="tool-schema">
            <summary>输入参数</summary>
            <pre>{{ JSON.stringify(t.input_schema, null, 2) }}</pre>
          </details>
        </div>
        <div v-if="!toolsData.tools.length" style="padding:20px;color:var(--m-text-secondary)">该服务器没有暴露任何工具</div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'

const rows = ref<any[]>([])
const visible = ref(false)
const editing = ref<any | null>(null)
const form = reactive<any>({ name: '', transport: 'stdio', config_json: {}, enabled: true })
const argsText = ref('[]')
const envText = ref('{}')
const headersText = ref('{}')

const statuses = reactive<Record<string | number, any>>({})

// tools drawer
const toolsVisible = ref(false)
const toolsLoading = ref(false)
const toolsError = ref('')
const toolsData = ref<any>(null)
const currentRow = ref<any>(null)
const drawerTitle = computed(() => currentRow.value ? `${currentRow.value.name} · 工具列表` : '工具列表')

watch(visible, (v) => {
  if (!v) return
  argsText.value = JSON.stringify(form.config_json.args || [], null, 0)
  envText.value = JSON.stringify(form.config_json.env || {}, null, 2)
  headersText.value = JSON.stringify(form.config_json.headers || {}, null, 2)
})

async function load() { rows.value = await api.mcps() }
onMounted(load)

function summarize(row: any) {
  const c = row.config_json || {}
  if (row.transport === 'stdio') return `${c.command || '?'} ${(c.args || []).join(' ')}`.trim()
  return c.url || ''
}

function openCreate() {
  editing.value = null
  Object.assign(form, { name: '', transport: 'stdio', config_json: {}, enabled: true })
  argsText.value = '[]'; envText.value = '{}'; headersText.value = '{}'
  visible.value = true
}
function openEdit(row: any) {
  editing.value = row
  Object.assign(form, JSON.parse(JSON.stringify(row)))
  visible.value = true
}
function onTransportChange() {
  form.config_json = {}
  argsText.value = '[]'; envText.value = '{}'; headersText.value = '{}'
}

async function onSubmit() {
  try {
    if (form.transport === 'stdio') {
      form.config_json.args = JSON.parse(argsText.value || '[]')
      form.config_json.env = JSON.parse(envText.value || '{}')
    } else {
      form.config_json.headers = JSON.parse(headersText.value || '{}')
    }
  } catch {
    ElMessage.error('JSON 格式错误'); return
  }
  if (editing.value) await api.updateMcp(editing.value.id, form)
  else await api.createMcp(form)
  visible.value = false
  ElMessage.success('保存成功')
  await load()
}

async function onDelete(row: any) {
  try { await ElMessageBox.confirm(`删除 ${row.name}?`, '确认', { type: 'warning' }); await api.deleteMcp(row.id); await load() } catch {}
}

async function onResummarize(row: any) {
  try {
    await api.resummarizeMcp(row.id)
    ElMessage.success('已触发重新生成,稍后刷新列表查看')
    setTimeout(() => { load() }, 6000)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '触发失败')
  }
}

async function testConnect(row: any) {
  statuses[row.id] = 'loading'
  try {
    const r = await api.pingMcp(row.id)
    statuses[row.id] = 'ok'
    statuses[row.id + '_count'] = r.tools_count
    ElMessage.success(`连接成功: ${r.server?.name} · ${r.tools_count} 个工具`)
  } catch {
    statuses[row.id] = 'fail'
  }
}

async function openTools(row: any) {
  currentRow.value = row
  toolsVisible.value = true
  toolsLoading.value = true
  toolsError.value = ''
  toolsData.value = null
  try {
    toolsData.value = await api.mcpTools(row.id)
    statuses[row.id] = 'ok'
    statuses[row.id + '_count'] = toolsData.value.tools.length
  } catch (e: any) {
    toolsError.value = e.response?.data?.detail || e.message || '连接失败'
    statuses[row.id] = 'fail'
  } finally {
    toolsLoading.value = false
  }
}
</script>

<style scoped>
.row-sub {
  font-size: 12px;
  color: var(--m-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.row-actions {
  display: flex; align-items: center; gap: 2px;
  flex-wrap: nowrap;
}
.row-actions :deep(.el-button + .el-button) { margin-left: 0; }
.row-actions :deep(.el-button) { padding: 4px 6px; }
.row-actions :deep(.el-button.is-circle) { padding: 5px; }
.muted { color: var(--m-text-tertiary); font-size: 12px; }
.mcp-icon {
  width: 36px; height: 36px; border-radius: 10px;
  background: var(--m-primary-soft); color: var(--m-primary);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}

.server-card {
  padding: 16px 20px;
  border-bottom: 1px solid var(--m-border);
  margin-bottom: 8px;
}
.server-name { font-size: 16px; font-weight: 600; }

.tool-card {
  margin: 12px 16px;
  padding: 14px 16px;
  background: var(--m-surface);
  border: 1px solid var(--m-border);
  border-radius: var(--m-radius);
  transition: box-shadow .15s, border-color .15s;
}
.tool-card:hover { box-shadow: var(--m-shadow-1); border-color: var(--m-border-strong); }
.tool-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.tool-name { font-size: 14px; font-weight: 600; color: var(--m-text); }
.tool-desc { font-size: 13px; color: var(--m-text-secondary); line-height: 1.6; }
.tool-schema { margin-top: 10px; font-size: 12px; }
.tool-schema summary {
  cursor: pointer; color: var(--m-primary); font-weight: 500;
  padding: 4px 0;
}
.tool-schema pre {
  background: #f8f9fa; padding: 12px; border-radius: 8px;
  font-family: 'Roboto Mono', monospace; font-size: 12px;
  overflow: auto; max-height: 320px; margin: 8px 0 0;
}

.is-loading { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
