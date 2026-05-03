<template>
  <div class="page">
    <div class="page-head">
      <span class="page-title">Skills 仓库</span>
      <div style="display:flex;gap:8px">
        <el-button @click="openUpload"><el-icon><Upload /></el-icon>上传 Skill 包</el-button>
        <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon>新建 Skill</el-button>
      </div>
    </div>
    <el-table :data="rows" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="code" label="编码" />
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="type" label="类型" width="100">
        <template #default="{ row }">
          <el-tag :type="row.type === 'composite' ? 'warning' : 'primary'">{{ row.type }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="描述" show-overflow-tooltip />
      <el-table-column label="来源" width="160">
        <template #default="{ row }">
          <el-tag v-if="row.source_json?.path" type="info" size="small">已上传</el-tag>
          <el-tag v-else-if="row.source_json?.callable" type="info" size="small">callable</el-tag>
          <el-tag v-else-if="row.source_json?.yaml" type="info" size="small">YAML</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="version" label="版本" width="80" />
      <el-table-column prop="enabled" label="启用" width="80">
        <template #default="{ row }"><el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '是' : '否' }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="240">
        <template #default="{ row }">
          <el-button v-if="row.source_json?.path" size="small" text @click="openDetail(row)"><el-icon><View /></el-icon>详情</el-button>
          <el-button size="small" text @click="openEdit(row)">编辑</el-button>
          <el-button size="small" text type="danger" @click="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Detail drawer with file tree + content viewer -->
    <el-drawer v-model="detailVisible" :size="900" direction="rtl" :title="detailTitle">
      <div class="detail-wrap">
        <div class="tree-pane">
          <div class="tree-head">{{ tree?.root }}</div>
          <el-tree
            v-if="tree"
            :data="tree.tree"
            :props="{ label: 'name', children: 'children' }"
            node-key="path"
            :default-expand-all="true"
            :expand-on-click-node="false"
            @node-click="onNodeClick"
          >
            <template #default="{ node, data }">
              <span class="tree-node">
                <el-icon v-if="data.type === 'dir'"><Folder /></el-icon>
                <el-icon v-else><Document /></el-icon>
                <span>{{ data.name }}</span>
                <span v-if="data.type === 'file'" class="muted file-size">{{ formatSize(data.size) }}</span>
              </span>
            </template>
          </el-tree>
        </div>
        <div class="content-pane">
          <div v-if="!currentFile" class="content-empty">点击左侧文件查看内容</div>
          <template v-else>
            <div class="content-head">
              <code>{{ currentFile.path }}</code>
              <span class="muted">{{ formatSize(currentFile.size) }}</span>
            </div>
            <div class="code-viewer">
              <div class="line-numbers">
                <div v-for="n in lineCount" :key="n">{{ n }}</div>
              </div>
              <pre class="code">{{ currentFile.content }}</pre>
            </div>
          </template>
        </div>
      </div>
    </el-drawer>

    <!-- Manual create / edit dialog -->
    <el-dialog v-model="visible" :title="editing ? '编辑 Skill' : '新建 Skill'" width="720px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="编码"><el-input v-model="form.code" /></el-form-item>
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="form.type">
            <el-radio value="atomic">原子</el-radio>
            <el-radio value="composite">组合 (YAML DAG)</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.type === 'atomic'" label="路径/调用">
          <el-input v-model="atomicPath" placeholder="path:/storage/skills/xxx 或 callable:pkg.mod:func" />
          <div style="font-size:12px;color:var(--m-text-secondary);margin-top:4px">
            前缀 <code>path:</code> 或 <code>callable:</code>。如要上传 zip 包,请用右上"上传 Skill 包"
          </div>
        </el-form-item>
        <el-form-item v-else label="YAML">
          <el-input v-model="yamlText" type="textarea" :rows="14" :placeholder="yamlSample" />
        </el-form-item>
        <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" @click="onSubmit">保存</el-button>
      </template>
    </el-dialog>

    <!-- Upload Skill package dialog -->
    <el-dialog v-model="uploadVisible" title="上传 Skill 包" width="560px">
      <el-form :model="uploadForm" :rules="uploadRules" ref="uploadFormRef" label-width="100px">
        <el-form-item label="编码" prop="code">
          <el-input v-model="uploadForm.code" placeholder="英文小写,作为目录名,如 pdf_extract" />
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="uploadForm.name" placeholder="显示名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="uploadForm.description" type="textarea" :rows="2" placeholder="留空则从 SKILL.md 提取" />
        </el-form-item>
        <el-form-item label="Skill 包" prop="file">
          <el-upload
            drag
            :auto-upload="false"
            :show-file-list="true"
            :limit="1"
            :on-change="onFileChange"
            :on-remove="onFileRemove"
            accept=".zip"
          >
            <el-icon class="el-icon--upload" :size="40"><UploadFilled /></el-icon>
            <div class="el-upload__text">拖拽 zip 包到这里,或<em>点击选择</em></div>
            <template #tip>
              <div style="font-size:12px;color:var(--m-text-secondary);margin-top:8px">
                zip 包根目录(或唯一子目录)需包含 <code>SKILL.md</code>
              </div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="onUploadSubmit">上传</el-button>
      </template>
    </el-dialog>
  </div>
</template>
<script setup lang="ts">
import { ref, onMounted, reactive, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'

const yamlSample = `name: contract_review_flow
description: 合同审查流程
steps:
  - id: extract
    skill: pdf_extract
    input:
      file: "{{trigger.file}}"
  - id: analyze
    skill: llm_call
    depends_on: [extract]
    input:
      text: "{{extract.value}}"
`

const rows = ref<any[]>([])
const visible = ref(false)
const editing = ref<any | null>(null)
const form = reactive<any>({ code: '', name: '', description: '', type: 'atomic', source_json: {}, enabled: true })
const atomicPath = ref('')
const yamlText = ref('')

// upload state
const uploadVisible = ref(false)
const uploadFormRef = ref<any>(null)
const uploadForm = reactive<any>({ code: '', name: '', description: '', file: null as File | null })
const uploading = ref(false)
const uploadRules = {
  code: [
    { required: true, message: '请输入编码', trigger: 'blur' },
    { pattern: /^[a-z][a-z0-9_-]{1,63}$/, message: '小写字母开头,允许 a-z 0-9 _ -', trigger: 'blur' },
  ],
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  file: [{ required: true, message: '请选择 zip 包', trigger: 'change' }],
}

async function load() { rows.value = await api.skills() }
onMounted(load)

function openCreate() {
  editing.value = null
  Object.assign(form, { code: '', name: '', description: '', type: 'atomic', source_json: {}, enabled: true })
  atomicPath.value = ''; yamlText.value = ''
  visible.value = true
}
function openEdit(row: any) {
  editing.value = row
  Object.assign(form, JSON.parse(JSON.stringify(row)))
  if (row.type === 'atomic') {
    atomicPath.value = row.source_json.path ? `path:${row.source_json.path}` :
                       row.source_json.callable ? `callable:${row.source_json.callable}` : ''
  } else {
    yamlText.value = row.source_json.yaml || ''
  }
  visible.value = true
}
async function onSubmit() {
  if (form.type === 'atomic') {
    const v = atomicPath.value.trim()
    if (v.startsWith('path:')) form.source_json = { path: v.slice(5).trim() }
    else if (v.startsWith('callable:')) form.source_json = { callable: v.slice(9).trim() }
    else { ElMessage.error('请填写 path: 或 callable:'); return }
  } else {
    form.source_json = { yaml: yamlText.value }
  }
  if (editing.value) await api.updateSkill(editing.value.id, form)
  else await api.createSkill(form)
  visible.value = false
  ElMessage.success('保存成功')
  await load()
}
async function onDelete(row: any) {
  try { await ElMessageBox.confirm(`删除 ${row.code}?`, '确认', { type: 'warning' }); await api.deleteSkill(row.id); await load() } catch {}
}

// ---------- detail drawer ----------
const detailVisible = ref(false)
const detailRow = ref<any>(null)
const tree = ref<any>(null)
const currentFile = ref<any>(null)
const detailTitle = computed(() => detailRow.value ? `${detailRow.value.name} · 详情` : '详情')
const lineCount = computed(() => {
  if (!currentFile.value?.content) return 0
  return Math.max(1, currentFile.value.content.split('\n').length)
})

async function openDetail(row: any) {
  detailRow.value = row
  detailVisible.value = true
  currentFile.value = null
  try {
    tree.value = await api.skillFiles(row.id)
    // auto-open SKILL.md if exists
    const skillMd = (tree.value.tree || []).find((n: any) => n.type === 'file' && n.name.toLowerCase() === 'skill.md')
    if (skillMd) await loadFile(skillMd.path)
  } catch {}
}

async function onNodeClick(data: any) {
  if (data.type === 'file') await loadFile(data.path)
}
async function loadFile(path: string) {
  if (!detailRow.value) return
  try { currentFile.value = await api.skillFile(detailRow.value.id, path) } catch {}
}
function formatSize(b: number) {
  if (b < 1024) return `${b} B`
  if (b < 1024 * 1024) return `${(b/1024).toFixed(1)} KB`
  return `${(b/1024/1024).toFixed(2)} MB`
}

function openUpload() {
  Object.assign(uploadForm, { code: '', name: '', description: '', file: null })
  uploadVisible.value = true
}
function onFileChange(uf: any) {
  uploadForm.file = uf.raw as File
}
function onFileRemove() {
  uploadForm.file = null
}
async function onUploadSubmit() {
  const ok = await uploadFormRef.value?.validate().catch(() => false)
  if (!ok) return
  if (!uploadForm.file) { ElMessage.error('请选择 zip 包'); return }
  uploading.value = true
  try {
    await api.uploadSkill(uploadForm.file, uploadForm.code, uploadForm.name, uploadForm.description)
    ElMessage.success('上传成功')
    uploadVisible.value = false
    await load()
  } catch {} finally {
    uploading.value = false
  }
}
</script>

<style scoped>
.detail-wrap { display: flex; height: calc(100vh - 80px); }
.tree-pane {
  width: 280px; flex-shrink: 0;
  border-right: 1px solid var(--m-border);
  overflow: auto; padding: 8px 0;
  background: var(--m-bg-soft);
}
.tree-head {
  padding: 8px 16px; font-size: 12px; font-weight: 600;
  color: var(--m-text-secondary); text-transform: uppercase; letter-spacing: .06em;
}
.tree-node { display: flex; align-items: center; gap: 6px; }
.file-size { font-size: 11px; margin-left: auto; padding-left: 8px; }

.content-pane { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.content-empty {
  flex: 1; display: flex; align-items: center; justify-content: center;
  color: var(--m-text-tertiary);
}
.content-head {
  padding: 12px 16px;
  display: flex; align-items: center; gap: 12px;
  background: var(--m-bg-soft);
  border-bottom: 1px solid var(--m-border);
  font-size: 13px;
}
.code-viewer {
  flex: 1; overflow: auto; display: flex;
  background: #fafbfc;
  font-family: 'Roboto Mono', ui-monospace, Menlo, monospace;
  font-size: 13px; line-height: 1.65;
}
.line-numbers {
  text-align: right; padding: 16px 12px 16px 16px;
  color: var(--m-text-tertiary); user-select: none;
  border-right: 1px solid var(--m-border);
  background: var(--m-surface);
}
.code {
  flex: 1; margin: 0; padding: 16px;
  white-space: pre; overflow: auto;
  color: var(--m-text);
}
</style>
