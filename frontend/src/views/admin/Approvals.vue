<template>
  <div class="page">
    <div class="page-head">
      <span class="page-title">审批待办</span>
      <el-segmented v-model="status" :options="['pending','approved','rejected']" @change="load" />
    </div>

    <div class="surface" style="padding:0">
      <el-table :data="rows" stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="run_id" label="Run ID" width="220" show-overflow-tooltip />
        <el-table-column prop="node_id" label="节点" width="160" />
        <el-table-column prop="title" label="标题" min-width="220" show-overflow-tooltip />
        <el-table-column label="状态" width="100">
          <template #default="{ row }"><el-tag :type="row.status==='pending' ? 'warning' : (row.status==='approved' ? 'success' : 'info')">{{ row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text @click="showDetail(row)">详情</el-button>
            <template v-if="row.status==='pending'">
              <el-button size="small" text type="primary" @click="decide(row,'approved')">通过</el-button>
              <el-button size="small" text type="danger" @click="decide(row,'rejected')">拒绝</el-button>
            </template>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="detailVisible" title="审批详情" width="720px">
      <pre class="detail-pre">{{ detailJson }}</pre>
      <template #footer><el-button @click="detailVisible=false">关闭</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'

const status = ref<'pending' | 'approved' | 'rejected'>('pending')
const rows = ref<any[]>([])
const detailVisible = ref(false)
const detailJson = ref('')

async function load() { rows.value = await api.approvals({ status: status.value }) }
onMounted(load)

function showDetail(row: any) {
  detailJson.value = JSON.stringify(row, null, 2)
  detailVisible.value = true
}

async function decide(row: any, decision: 'approved' | 'rejected') {
  let reason = ''
  if (decision === 'rejected') {
    try {
      const r = await ElMessageBox.prompt('请输入拒绝原因', '拒绝审批', { inputType: 'textarea' })
      reason = r.value || ''
    } catch { return }
  } else {
    try { await ElMessageBox.confirm('确认通过该审批?', '确认', { type: 'warning' }) } catch { return }
  }
  await api.decideApproval(row.id, { decision, reason })
  ElMessage.success('已提交审批结果,后台继续执行')
  await load()
}
</script>

<style scoped>
.detail-pre {
  margin: 0; padding: 12px; background: var(--m-bg-soft); border-radius: 8px;
  max-height: 60vh; overflow: auto; font-size: 12px; font-family: 'Roboto Mono', monospace;
}
</style>
