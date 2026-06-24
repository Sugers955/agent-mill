<template>
  <div class="page">
    <div class="page-head"><span class="page-title">审批</span></div>

    <el-tabs v-model="tab">
      <el-tab-pane label="方案审批" name="pack">
        <div class="surface" style="padding:0">
          <el-table :data="packRows" stripe v-loading="loading">
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="run_id" label="Run ID" width="180" show-overflow-tooltip />
            <el-table-column prop="node_id" label="节点" width="120" />
            <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getStatusInfo(row.status).type">{{ getStatusInfo(row.status).label }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="170" />
            <el-table-column label="操作" width="220" fixed="right">
              <template #default="{ row }">
                <el-button size="small" text @click="showDetail(row)">详情</el-button>
                <template v-if="row.status==='pending'">
                  <el-button size="small" text type="primary" @click="decidePack(row,'approved')">通过</el-button>
                  <el-button size="small" text type="danger" @click="decidePack(row,'rejected')">拒绝</el-button>
                </template>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <el-tab-pane label="操作审批" name="operation">
        <div class="surface" style="padding:0">
          <el-table :data="opRows" stripe v-loading="loading">
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="operation_type" label="操作类型" width="140" />
            <el-table-column prop="target_name" label="目标" min-width="160" show-overflow-tooltip />
            <el-table-column prop="reason" label="原因" min-width="200" show-overflow-tooltip />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getStatusInfo(row.status).type">{{ getStatusInfo(row.status).label }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="170" />
            <el-table-column label="操作" width="220" fixed="right">
              <template #default="{ row }">
                <el-button size="small" text @click="showDetail(row)">详情</el-button>
                <template v-if="row.status==='pending'">
                  <el-button size="small" text type="primary" @click="decideOp(row,'approved')">通过</el-button>
                  <el-button size="small" text type="danger" @click="decideOp(row,'rejected')">拒绝</el-button>
                </template>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="detailVisible" title="审批详情" width="720px">
      <pre class="detail-pre">{{ detailJson }}</pre>
      <template #footer><el-button @click="detailVisible=false">关闭</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'

const tab = ref('pack')
const loading = ref(false)
const packRows = ref<any[]>([])
const opRows = ref<any[]>([])
const detailVisible = ref(false)
const detailJson = ref('')

const statusMap: Record<string, { label: string; type: string }> = {
  pending: { label: '待审批', type: 'warning' },
  approved: { label: '已通过', type: 'success' },
  rejected: { label: '已拒绝', type: 'danger' },
}

function getStatusInfo(status: string) {
  return statusMap[status] || { label: status, type: 'info' }
}

async function load() {
  loading.value = true
  try {
    const [packRes, opRes] = await Promise.all([
      api.approvals({ status: 'pending' }),
      api.request('/api/admin/operation-approvals?status=pending'),
    ])
    packRows.value = packRes.items || packRes || []
    opRows.value = opRes.items || []
  } finally { loading.value = false }
}
onMounted(load)

function showDetail(row: any) {
  detailJson.value = JSON.stringify(row, null, 2)
  detailVisible.value = true
}

async function decidePack(row: any, decision: 'approved' | 'rejected') {
  let reason = ''
  if (decision === 'rejected') {
    try { const r = await ElMessageBox.prompt('请输入拒绝原因', '拒绝审批', { inputType: 'textarea' }); reason = r.value || '' } catch { return }
  } else {
    try { await ElMessageBox.confirm('确认通过该审批?', '确认', { type: 'warning' }) } catch { return }
  }
  await api.decideApproval(row.id, { decision, reason })
  ElMessage.success('已提交审批结果')
  await load()
}

async function decideOp(row: any, decision: 'approved' | 'rejected') {
  let reason = ''
  if (decision === 'rejected') {
    try { const r = await ElMessageBox.prompt('请输入拒绝原因', '拒绝审批', { inputType: 'textarea' }); reason = r.value || '' } catch { return }
  } else {
    try { await ElMessageBox.confirm('确认通过该审批?', '确认', { type: 'warning' }) } catch { return }
  }
  await api.request(`/api/admin/operation-approvals/${row.id}/decide`, { method: 'POST', data: { decision, reason } })
  ElMessage.success('已提交审批结果')
  await load()
}
</script>

<style scoped>
.detail-pre {
  margin: 0; padding: 12px; background: var(--m-bg-soft); border-radius: 8px;
  max-height: 60vh; overflow: auto; font-size: 12px; font-family: 'Roboto Mono', monospace;
}
</style>
