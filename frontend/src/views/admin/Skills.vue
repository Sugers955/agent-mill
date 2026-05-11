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
      <el-table-column prop="code" label="编码" min-width="140" show-overflow-tooltip />
      <el-table-column prop="name" label="名称" min-width="160" show-overflow-tooltip />
      <el-table-column prop="type" label="类型" width="90">
        <template #default="{ row }">
          <el-tag :type="row.type === 'composite' ? 'warning' : 'primary'" size="small">{{ row.type }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
      <el-table-column label="来源" width="90">
        <template #default="{ row }">
          <el-tag v-if="row.source_json?.path" type="info" size="small">已上传</el-tag>
          <el-tag v-else-if="row.source_json?.callable" type="info" size="small">callable</el-tag>
          <el-tag v-else-if="row.source_json?.yaml" type="info" size="small">YAML</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="version" label="版本" width="60" align="center" />
      <el-table-column prop="enabled" label="启用" width="60" align="center">
        <template #default="{ row }"><el-tag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? '是' : '否' }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="240" fixed="right">
        <template #default="{ row }">
          <div class="row-actions">
            <el-button v-if="row.source_json?.path" size="small" text @click="openDetail(row)"><el-icon><View /></el-icon>详情</el-button>
            <el-button size="small" text @click="openEdit(row)">编辑</el-button>
            <el-button size="small" text @click="openSummary(row)">使用说明</el-button>
            <el-button size="small" text type="danger" @click="onDelete(row)">删除</el-button>
          </div>
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
              <div class="head-actions">
                <template v-if="!editingFile">
                  <el-button v-if="currentFile.editable" size="small" type="primary" plain @click="startEdit">
                    <el-icon><EditPen /></el-icon>编辑
                  </el-button>
                  <el-tooltip v-else content="该文件类型不允许在线编辑" placement="top">
                    <el-button size="small" disabled>
                      <el-icon><Lock /></el-icon>只读
                    </el-button>
                  </el-tooltip>
                </template>
                <template v-else>
                  <el-button size="small" @click="cancelEdit">取消</el-button>
                  <el-button size="small" type="primary" :loading="saving" @click="saveEdit"
                             :disabled="editBuffer === currentFile.content">
                    <el-icon><Check /></el-icon>保存
                  </el-button>
                </template>
              </div>
            </div>
            <div v-if="editingFile" class="editor-wrap">
              <textarea
                ref="editorRef"
                v-model="editBuffer"
                class="editor-area"
                spellcheck="false"
                @keydown.tab.prevent="onTab"
                @keydown.ctrl.s.prevent="saveEdit"
                @keydown.meta.s.prevent="saveEdit"
              />
              <div class="editor-footer">
                <span class="muted">{{ editBuffer.length }} 字符 · {{ editBuffer.split('\n').length }} 行</span>
                <span class="muted">Ctrl/Cmd + S 保存</span>
              </div>
            </div>
            <div v-else class="code-viewer">
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

        <!-- Security findings: shown after a blocked attempt -->
        <el-form-item v-if="uploadFindings.length" label="安全扫描">
          <el-alert type="warning" :closable="false" show-icon
                   title="检测到潜在风险,请确认后继续">
            <template #default>
              <div class="findings-list">
                <div v-for="(f, i) in uploadFindings.slice(0, 8)" :key="i" class="finding">
                  <code class="finding-file">{{ f.file }}</code>
                  <span class="finding-rule">{{ f.rule }}</span>
                  <span class="finding-snippet">{{ f.snippet }}</span>
                </div>
                <div v-if="uploadFindings.length > 8" class="finding muted">
                  …还有 {{ uploadFindings.length - 8 }} 项
                </div>
              </div>
            </template>
          </el-alert>
          <el-checkbox v-model="uploadForm.force" style="margin-top:8px">
            我已确认上述内容,强制上传
          </el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="onUploadSubmit">上传</el-button>
      </template>
    </el-dialog>

    <!-- Usage summary editor: view + edit the AI-generated user_summary. -->
    <el-dialog v-model="summaryVisible" :title="`使用说明 · ${summaryRow?.name || ''}`" width="640px">
      <div v-if="summaryRow" class="summary-meta muted">
        <span>{{ summaryRow.code }}</span>
        <span v-if="summaryRow.user_summary_updated_at">· 更新于 {{ formatTime(summaryRow.user_summary_updated_at) }}</span>
      </div>
      <el-input
        v-model="summaryText"
        type="textarea"
        :rows="10"
        placeholder="说明这个 Skill 是做什么的、什么时候使用、给出 1-2 个调用示例。留空则恢复 AI 自动生成的说明。"
      />
      <template #footer>
        <el-button @click="summaryVisible = false">取消</el-button>
        <el-button @click="onResetSummary" :disabled="summarySaving">重置为自动生成</el-button>
        <el-button type="primary" :loading="summarySaving" @click="onSaveSummary">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
<script setup lang="ts">
import { ref, onMounted, reactive, computed, nextTick } from 'vue'
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
const uploadForm = reactive<any>({ code: '', name: '', description: '', file: null as File | null, force: false })
const uploading = ref(false)
const uploadFindings = ref<any[]>([])
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

// ---------- usage summary editor ----------
const summaryVisible = ref(false)
const summaryRow = ref<any>(null)
const summaryText = ref('')
const summarySaving = ref(false)

function openSummary(row: any) {
  summaryRow.value = row
  summaryText.value = row.user_summary || ''
  summaryVisible.value = true
}
function formatTime(iso: string) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('zh-CN', { hour12: false })
}
async function onSaveSummary() {
  if (!summaryRow.value) return
  summarySaving.value = true
  try {
    const r = summaryRow.value
    await api.updateSkill(r.id, {
      code: r.code,
      name: r.name,
      description: r.description || '',
      type: r.type,
      source_json: r.source_json || {},
      enabled: r.enabled,
      user_summary: (summaryText.value || '').trim(),
    })
    ElMessage.success('已保存')
    summaryVisible.value = false
    await load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    summarySaving.value = false
  }
}
async function onResetSummary() {
  if (!summaryRow.value) return
  try {
    await ElMessageBox.confirm('重置后将清空当前说明，并触发 AI 重新生成。继续？', '确认', { type: 'warning' })
  } catch { return }
  summarySaving.value = true
  try {
    const r = summaryRow.value
    // empty user_summary signals "let backend re-summarize"
    await api.updateSkill(r.id, {
      code: r.code, name: r.name, description: r.description || '',
      type: r.type, source_json: r.source_json || {}, enabled: r.enabled,
      user_summary: null,
    })
    await api.resummarizeSkill(r.id)
    ElMessage.success('已重置，稍后刷新列表查看')
    summaryVisible.value = false
    setTimeout(() => { load() }, 4000)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '重置失败')
  } finally {
    summarySaving.value = false
  }
}

// ---------- detail drawer ----------
const detailVisible = ref(false)
const detailRow = ref<any>(null)
const tree = ref<any>(null)
const currentFile = ref<any>(null)
const editingFile = ref(false)
const editBuffer = ref('')
const saving = ref(false)
const editorRef = ref<HTMLTextAreaElement | null>(null)
const detailTitle = computed(() => detailRow.value ? `${detailRow.value.name} · 详情` : '详情')
const lineCount = computed(() => {
  if (!currentFile.value?.content) return 0
  return Math.max(1, currentFile.value.content.split('\n').length)
})

async function openDetail(row: any) {
  detailRow.value = row
  detailVisible.value = true
  currentFile.value = null
  editingFile.value = false
  try {
    tree.value = await api.skillFiles(row.id)
    const skillMd = (tree.value.tree || []).find((n: any) => n.type === 'file' && n.name.toLowerCase() === 'skill.md')
    if (skillMd) await loadFile(skillMd.path)
  } catch {}
}

async function onNodeClick(data: any) {
  if (data.type === 'file') await loadFile(data.path)
}
async function loadFile(path: string) {
  if (!detailRow.value) return
  if (editingFile.value && editBuffer.value !== currentFile.value?.content) {
    try {
      await ElMessageBox.confirm('当前文件未保存,切换会丢失修改,继续?', '确认', { type: 'warning' })
    } catch { return }
  }
  editingFile.value = false
  try { currentFile.value = await api.skillFile(detailRow.value.id, path) } catch {}
}

function startEdit() {
  if (!currentFile.value?.editable) return
  editBuffer.value = currentFile.value.content || ''
  editingFile.value = true
  nextTick().then(() => editorRef.value?.focus())
}

function cancelEdit() {
  if (editBuffer.value !== currentFile.value?.content) {
    if (!confirm('放弃本次修改?')) return
  }
  editingFile.value = false
}

function onTab(e: KeyboardEvent) {
  const ta = editorRef.value
  if (!ta) return
  const start = ta.selectionStart
  const end = ta.selectionEnd
  editBuffer.value = editBuffer.value.slice(0, start) + '  ' + editBuffer.value.slice(end)
  nextTick().then(() => {
    if (editorRef.value) editorRef.value.selectionStart = editorRef.value.selectionEnd = start + 2
  })
}

async function saveEdit() {
  if (!currentFile.value || !detailRow.value) return
  if (editBuffer.value === currentFile.value.content) return
  saving.value = true
  try {
    await api.saveSkillFile(detailRow.value.id, currentFile.value.path, editBuffer.value)
    ElMessage.success('保存成功')
    currentFile.value = await api.skillFile(detailRow.value.id, currentFile.value.path)
    editingFile.value = false
    await load()
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    if (detail && typeof detail === 'object' && detail.findings) {
      ElMessage.error(`内容触发安全规则: ${detail.findings.map((f: any) => f.rule).join(', ')}`)
    }
  } finally {
    saving.value = false
  }
}
function formatSize(b: number) {
  if (b < 1024) return `${b} B`
  if (b < 1024 * 1024) return `${(b/1024).toFixed(1)} KB`
  return `${(b/1024/1024).toFixed(2)} MB`
}

function openUpload() {
  Object.assign(uploadForm, { code: '', name: '', description: '', file: null, force: false })
  uploadFindings.value = []
  uploadVisible.value = true
}
function onFileChange(uf: any) {
  uploadForm.file = uf.raw as File
  // a fresh file should reset prior findings/force decisions
  uploadFindings.value = []
  uploadForm.force = false
}
function onFileRemove() {
  uploadForm.file = null
  uploadFindings.value = []
  uploadForm.force = false
}
async function onUploadSubmit() {
  const ok = await uploadFormRef.value?.validate().catch(() => false)
  if (!ok) return
  if (!uploadForm.file) { ElMessage.error('请选择 zip 包'); return }
  uploading.value = true
  try {
    await api.uploadSkill(
      uploadForm.file, uploadForm.code, uploadForm.name, uploadForm.description, uploadForm.force,
    )
    ElMessage.success('上传成功')
    uploadVisible.value = false
    await load()
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    if (detail && typeof detail === 'object' && Array.isArray(detail.findings)) {
      // security scan blocked — surface findings inline so admin can review and tick force
      uploadFindings.value = detail.findings
      ElMessage.warning(detail.message || '检测到潜在风险,请确认后强制上传')
    } else if (typeof detail === 'string') {
      ElMessage.error(detail)
    } else if (detail && typeof detail === 'object') {
      const head = detail.message || '上传失败'
      const hint = detail.hint ? ` (${detail.hint})` : ''
      ElMessage.error(`${head}${hint}`)
      console.error('upload skill blocked:', detail)
    } else {
      ElMessage.error('上传失败')
    }
  } finally {
    uploading.value = false
  }
}
</script>

<style scoped>
.summary-meta {
  font-size: 12px; margin-bottom: 8px;
  display: flex; align-items: center; gap: 8px;
}
.summary-cell {
  font-size: 12px;
  line-height: 1.5;
  color: var(--m-text-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.muted { color: var(--m-text-tertiary); font-size: 12px; }
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
.content-head .head-actions { margin-left: auto; display: flex; gap: 6px; }
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

/* in-place editor */
.editor-wrap {
  flex: 1; display: flex; flex-direction: column; min-height: 0;
  background: var(--m-surface);
}
.editor-area {
  flex: 1; min-height: 0; resize: none;
  border: none; outline: none; padding: 16px;
  font-family: 'Roboto Mono', ui-monospace, Menlo, monospace;
  font-size: 13px; line-height: 1.65;
  color: var(--m-text); background: #fafbfc;
  white-space: pre; overflow: auto;
  tab-size: 2;
}
.editor-area:focus { background: #fff; box-shadow: inset 2px 0 0 var(--m-primary); }
.editor-footer {
  display: flex; justify-content: space-between;
  padding: 8px 16px;
  font-size: 11px; color: var(--m-text-secondary);
  background: var(--m-bg-soft);
  border-top: 1px solid var(--m-border);
}

.findings-list { max-height: 200px; overflow: auto; font-size: 12px; }
.finding {
  display: flex; align-items: center; gap: 8px;
  padding: 4px 0;
  border-bottom: 1px dashed var(--m-border);
}
.finding:last-child { border-bottom: none; }
.finding.muted { color: var(--m-text-tertiary); justify-content: center; }
.finding-file {
  font-family: 'Roboto Mono', monospace;
  background: var(--m-surface-variant);
  padding: 1px 6px; border-radius: 4px;
  max-width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  flex-shrink: 0;
}
.finding-rule {
  font-weight: 600; color: var(--m-danger, #d33);
  flex-shrink: 0;
}
.finding-snippet {
  color: var(--m-text-secondary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  flex: 1; min-width: 0;
}

/* Action column buttons: Element Plus injects margin-left:12px between sibling
   buttons globally. Compress it to a tight gap here only. */
.row-actions { display: inline-flex; align-items: center; gap: 4px; }
.row-actions :deep(.el-button + .el-button) { margin-left: 0; }
.row-actions :deep(.el-button) { padding: 4px 6px; }
</style>
