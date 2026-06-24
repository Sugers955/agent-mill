<template>
  <div class="page">
    <div class="page-head">
      <el-button text @click="goBack">← 返回</el-button>
      <span class="page-title" style="margin-left:8px">{{ kb?.name || '知识库详情' }}</span>
    </div>

    <div class="desc" v-if="kb?.description">{{ kb.description }}</div>

    <!-- 上传文档 -->
    <div class="actions">
      <el-upload :show-file-list="false" :auto-upload="false" :on-change="onUploadFile" accept=".txt,.md,.pdf,.docx,.csv,.json">
        <el-button type="primary">上传文档</el-button>
      </el-upload>
    </div>

    <!-- 文档列表 -->
    <div class="surface" style="margin-top:12px">
      <el-table :data="documents" stripe v-loading="loading">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="title" label="名称" min-width="240" />
        <el-table-column prop="char_count" label="字符数" width="80" />
        <el-table-column prop="chunk_count" label="分块数" width="80" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'ready' ? 'success' : 'warning'" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170" />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.file_id" size="small" text @click="viewSource(row)">查看源文件</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 搜索测试 -->
    <div class="surface" style="margin-top:16px">
      <div class="search-title">语义搜索测试</div>
      <div class="search-row">
        <el-input v-model="searchQuery" placeholder="输入搜索内容…" style="flex:1" @keydown.enter="onSearch" />
        <el-button type="primary" :loading="searching" @click="onSearch">搜索</el-button>
      </div>
      <div v-if="searchResults.length" class="search-results">
        <div v-for="r in searchResults" :key="r.kb_chunk_id" class="search-item">
          <div class="search-score">得分: {{ r.score }}</div>
          <div class="search-content">{{ r.content }}</div>
          <div class="search-meta">文档 ID: {{ r.document_id }} · 分块: {{ r.chunk_index }}</div>
        </div>
      </div>
      <div v-else-if="searched" class="no-results">无匹配结果</div>
    </div>
  </div>

  <!-- 源文件预览对话框 -->
  <el-dialog v-model="sourceDialog" :title="sourceTitle" width="90%" class="source-dialog">
    <div v-loading="sourceLoading" class="source-body">
      <pre class="source-pre">{{ sourceContent }}</pre>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '@/api'

const route = useRoute()
const router = useRouter()
const kbId = Number(route.params.id)
const kb = ref<any>(null)
const documents = ref<any[]>([])
const loading = ref(false)
const searchQuery = ref('')
const searchResults = ref<any[]>([])
const searching = ref(false)
const searched = ref(false)

async function load() {
  loading.value = true
  try {
    const [all, docs] = await Promise.all([
      api.request('/api/admin/knowledge/bases'),
      api.request(`/api/admin/knowledge/bases/${kbId}/documents`),
    ])
    kb.value = (all || []).find((b: any) => b.id === kbId)
    documents.value = docs || []
  } finally { loading.value = false }
}

async function onUploadFile(uploadFile: any) {
  const file: File | undefined = uploadFile?.raw
  if (!file) return
  try {
    const form = new FormData()
    form.append('file', file)
    const up = await api.request('/api/files/upload', { method: 'POST', data: form })
    await api.request(`/api/admin/knowledge/bases/${kbId}/documents?file_id=${up.id}`, { method: 'POST' })
    ElMessage.success('文档已添加')
    await load()
  } catch { ElMessage.error('上传失败') }
}

async function onSearch() {
  if (!searchQuery.value.trim()) return
  searching.value = true
  searched.value = true
  try {
    const r = await api.request('/api/admin/knowledge/search', { method: 'POST', data: { kb_id: kbId, query: searchQuery.value, top_k: 5 } })
    searchResults.value = r.results || []
  } catch { searchResults.value = [] }
  finally { searching.value = false }
}

function goBack() { router.push('/admin/knowledge').catch(() => {}) }

const sourceDialog = ref(false)
const sourceContent = ref('')
const sourceTitle = ref('')
const sourceLoading = ref(false)

async function viewSource(doc: any) {
  sourceTitle.value = doc.title || `文件 #${doc.file_id}`
  const ext = (doc.title || '').split('.').pop()?.toLowerCase() || ''
  const textExts = ['txt','md','csv','json','xml','yaml','yml','html','htm','py','js','ts','jsx','tsx','java','sh','bash','sql','log','cfg','ini','env','toml','rtf','css','scss','less']
  const inlineExts = ['pdf','png','jpg','jpeg','gif','webp','svg']

  if (textExts.includes(ext)) {
    sourceDialog.value = true
    sourceLoading.value = true
    try {
      const token = localStorage.getItem('access_token')
      const r = await fetch(`/api/files/${doc.file_id}/raw?t=${token}`)
      sourceContent.value = await r.text()
    } catch { sourceContent.value = '（无法加载文件内容）' }
    finally { sourceLoading.value = false }
  } else if (inlineExts.includes(ext)) {
    const token = localStorage.getItem('access_token')
    window.open(`/api/files/${doc.file_id}/raw?t=${token}`, '_blank')
  } else {
    const token = localStorage.getItem('access_token')
    window.open(`/api/files/${doc.file_id}/raw?t=${token}`, '_blank')
  }
}

onMounted(load)
</script>

<style scoped>
.desc { color: var(--m-text-secondary); font-size: 13px; margin-bottom: 8px; }
.actions { display: flex; gap: 8px; }
.search-title { font-size: 14px; font-weight: 600; margin-bottom: 8px; }
.search-row { display: flex; gap: 8px; }
.search-results { margin-top: 12px; display: flex; flex-direction: column; gap: 8px; }
.search-item {
  padding: 10px 12px; background: var(--m-bg-soft); border-radius: var(--m-radius-sm);
  border: 1px solid var(--m-border);
}
.search-score { font-size: 11px; color: var(--m-primary); font-weight: 500; margin-bottom: 4px; }
.search-content { font-size: 13px; color: var(--m-text); line-height: 1.5; }
.search-meta { font-size: 11px; color: var(--m-text-tertiary); margin-top: 4px; }
.no-results { text-align: center; color: var(--m-text-tertiary); padding: 24px; font-size: 13px; }

.source-body { max-height: 70vh; overflow: auto; }
.source-pre { margin: 0; font-size: 12px; line-height: 1.5; white-space: pre-wrap; word-break: break-all; }
:deep(.source-dialog .el-dialog__body) { padding: 12px 20px; }

@media (max-width: 768px) {
  .actions { flex-direction: column; }
  .actions .el-upload { width: 100%; }
  .search-row { flex-direction: column; }
  .search-row .el-input { flex: none; }
  .page-head { flex-wrap: wrap; }
}
</style>
