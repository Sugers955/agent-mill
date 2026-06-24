<template>
  <div class="page skills-page">
    <div class="page-head">
      <span class="page-title">技能工坊</span>
      <div style="display:flex;gap:8px">
        <el-button @click="openUpload"><el-icon><Upload /></el-icon>上传 Skill 包</el-button>
        <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon>新建 Skill</el-button>
      </div>
    </div>

    <!-- 技能卡片网格 -->
    <div class="skills-grid">
      <div
        v-for="skill in rows"
        :key="skill.id"
        class="skill-card"
        :class="{ 'is-composite': skill.type === 'composite', 'is-disabled': !skill.enabled }"
      >
        <!-- 卡片头部 -->
        <div class="skill-header">
          <div class="skill-icon" :style="getIconStyle(skill)" @click="openIconUpload(skill)">
            <img v-if="skill.icon_url" :src="skill.icon_url" alt="" class="icon-img" />
            <span v-else class="icon-text">{{ getInitials(skill.name) }}</span>
          </div>
          <div class="skill-status">
            <span class="status-dot" :class="{ online: skill.enabled }"></span>
          </div>
        </div>

        <!-- 卡片内容 -->
        <div class="skill-body">
          <h3 class="skill-name">{{ skill.name }}</h3>
          <p class="skill-code">{{ skill.code }}</p>
          <p class="skill-desc">{{ skill.description || '暂无描述' }}</p>
        </div>

        <!-- 能力标签 -->
        <div class="skill-tags">
          <span class="type-tag" :class="skill.type">
            {{ skill.type === 'atomic' ? '原子技能' : '组合技能' }}
          </span>
          <span class="version-tag">v{{ skill.version }}</span>
          <span v-if="skill.source_json?.path" class="source-tag">已上传</span>
          <span v-else-if="skill.source_json?.callable" class="source-tag">Callable</span>
          <span v-else-if="skill.source_json?.yaml" class="source-tag">YAML</span>
        </div>

        <!-- 操作按钮 -->
        <div class="skill-actions">
          <button v-if="skill.source_json?.path" class="action-btn" @click="openDetail(skill)">
            <el-icon><View /></el-icon>
            详情
          </button>
          <button class="action-btn" @click="openEdit(skill)">
            <el-icon><Edit /></el-icon>
            编辑
          </button>
          <button class="action-btn" @click="openSummary(skill)">
            <el-icon><InfoFilled /></el-icon>
            说明
          </button>
          <button class="action-btn danger" @click="onDelete(skill)">
            <el-icon><Delete /></el-icon>
          </button>
        </div>
      </div>

      <!-- 新建卡片 -->
      <div class="skill-card add-card" @click="openCreate">
        <div class="add-content">
          <el-icon class="add-icon"><Plus /></el-icon>
          <span class="add-text">新建技能</span>
        </div>
      </div>
    </div>

    <!-- Detail drawer -->
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
            <template #default="{ data }">
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
                  <el-button v-if="currentFile.editable" size="small" type="primary" @click="startEdit">
                    <el-icon><EditPen /></el-icon>编辑
                  </el-button>
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
              <textarea ref="editorRef" v-model="editBuffer" class="editor-area" spellcheck="false"
                        @keydown.tab.prevent="onTab" @keydown.ctrl.s.prevent="saveEdit"></textarea>
            </div>
            <div v-else class="content-body">
              <pre class="file-content"><code>{{ currentFile.content }}</code></pre>
            </div>
          </template>
        </div>
      </div>
    </el-drawer>

    <!-- 编辑弹窗 -->
    <el-dialog v-model="visible" :title="editing ? '编辑 Skill' : '新建 Skill'" width="700px">
      <el-form :model="form" label-width="100px">
        <!-- 图标上传 -->
        <el-form-item label="图标">
          <div class="icon-upload-area">
            <div class="icon-preview" :style="getIconStyle(form)">
              <img v-if="form.icon_url" :src="form.icon_url" alt="" class="icon-img" />
              <span v-else class="icon-text">{{ getInitials(form.name || '') }}</span>
            </div>
            <div class="icon-actions">
              <el-upload
                :show-file-list="false"
                :before-upload="beforeIconUpload"
                :on-success="onIconUploadSuccess"
                :action="`/api/admin/skills/${editing?.id || 'new'}/icon`"
                accept="image/*"
              >
                <el-button size="small" type="primary" :disabled="!editing">
                  <el-icon><Upload /></el-icon>
                  上传图标
                </el-button>
              </el-upload>
              <div class="icon-tip">支持 JPG/PNG，建议 128x128px</div>
            </div>
          </div>
        </el-form-item>

        <el-form-item label="编码" required><el-input v-model="form.code" :disabled="!!editing" /></el-form-item>
        <el-form-item label="名称" required><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="描述" required><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="类型" required>
          <el-radio-group v-model="form.type">
            <el-radio value="atomic">atomic — 原子技能（单步执行）</el-radio>
            <el-radio value="composite">composite — 组合技能（YAML DAG）</el-radio>
          </el-radio-group>
        </el-form-item>
        <template v-if="form.type === 'atomic'">
          <el-form-item label="来源">
            <el-radio-group v-model="sourceType">
              <el-radio value="callable">Callable（Python 函数）</el-radio>
              <el-radio value="path">Path（Skill 包目录）</el-radio>
            </el-radio-group>
          </el-form-item>
          <template v-if="sourceType === 'callable'">
            <el-form-item label="module"><el-input v-model="form.source_json.module" placeholder="app.skills.xxx" /></el-form-item>
            <el-form-item label="function"><el-input v-model="form.source_json.function" placeholder="main" /></el-form-item>
          </template>
          <template v-else>
            <el-form-item label="path"><el-input v-model="form.source_json.path" disabled /></el-form-item>
          </template>
        </template>
        <template v-else>
          <el-form-item label="YAML" required>
            <el-input v-model="yamlText" type="textarea" :rows="12" placeholder="# YAML DAG 定义..." />
            <div style="margin-top:6px;font-size:12px;color:var(--m-text-secondary)">
              composite 技能由 YAML 定义 DAG 步骤，运行时自动解析
            </div>
          </el-form-item>
        </template>
        <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSubmit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 上传弹窗 -->
    <el-dialog v-model="uploadVisible" title="上传 Skill 包" width="560px">
      <el-upload
        ref="uploadRef"
        drag
        :action="uploadUrl"
        :headers="uploadHeaders"
        :limit="1"
        :on-success="onUploadDone"
        :on-error="onUploadErr"
        accept=".zip"
      >
        <el-icon class="el-icon--upload"><Upload /></el-icon>
        <div class="el-upload__text">拖拽 <b>.zip</b> 文件到此处，或 <em>点击上传</em></div>
        <template #tip>
          <div class="el-upload__tip">仅支持 .zip 格式，根目录需包含 SKILL.md</div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="uploadVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 使用说明弹窗 -->
    <el-dialog v-model="summaryVisible" title="Skill 使用说明" width="680px">
      <div v-if="summaryLoading" style="text-align:center;padding:40px;color:var(--m-text-secondary)">生成中...</div>
      <div v-else-if="summaryText" style="white-space:pre-wrap;line-height:1.7;font-size:14px">{{ summaryText }}</div>
      <div v-else style="text-align:center;padding:40px;color:var(--m-text-secondary)">暂无使用说明</div>
      <template #footer>
        <el-button @click="summaryVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'
import { agentGradient } from '@/utils/agent-colors'

const rows = ref<any[]>([])
const visible = ref(false)
const editing = ref<any | null>(null)
const form = reactive<any>({ code: '', name: '', description: '', type: 'atomic', source_json: {}, enabled: true, icon_url: '' })
const sourceType = ref<'callable' | 'path'>('callable')
const yamlText = ref('')
const saving = ref(false)

const detailVisible = ref(false)
const detailTitle = ref('')
const detailSkill = ref<any>(null)
const tree = ref<any>(null)
const currentFile = ref<any>(null)
const editingFile = ref(false)
const editBuffer = ref('')
const editorRef = ref<HTMLTextAreaElement>()

const uploadVisible = ref(false)
const uploadRef = ref()
const uploadUrl = `/api/admin/skills/upload`
const uploadHeaders = reactive<Record<string, string>>({})

const summaryVisible = ref(false)
const summaryText = ref('')
const summaryLoading = ref(false)

function getIconStyle(skill: any) {
  if (skill.icon_url) return {}
  return { background: agentGradient(skill) }
}

function getInitials(name: string) {
  if (!name) return '?'
  return name.charAt(0).toUpperCase()
}

async function load() {
  const res = await api.skills()
  rows.value = res.items || res
}

onMounted(() => {
  const t = localStorage.getItem('token')
  if (t) uploadHeaders['Authorization'] = `Bearer ${t}`
  load()
})

function openCreate() {
  editing.value = null
  Object.assign(form, { code: '', name: '', description: '', type: 'atomic', source_json: {}, enabled: true, icon_url: '' })
  sourceType.value = 'callable'
  yamlText.value = ''
  visible.value = true
}

function openEdit(row: any) {
  editing.value = row
  Object.assign(form, JSON.parse(JSON.stringify(row)))
  if (form.type === 'composite' && form.source_json?.yaml) yamlText.value = form.source_json.yaml
  sourceType.value = form.source_json?.callable ? 'callable' : 'path'
  visible.value = true
}

function openIconUpload(skill: any) {
  // 如果是编辑模式，可以上传图标
  if (editing.value?.id === skill.id) {
    // 触发上传
  }
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
  if (form.type === 'composite') {
    if (!yamlText.value.trim()) { ElMessage.warning('请输入 YAML'); return }
    form.source_json = { yaml: yamlText.value }
  }
  saving.value = true
  try {
    if (editing.value) await api.updateSkill(editing.value.id, form)
    else await api.createSkill(form)
    visible.value = false
    ElMessage.success('保存成功')
    await load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally { saving.value = false }
}

async function onDelete(row: any) {
  try {
    await ElMessageBox.confirm(`确认删除 ${row.code}？`, '确认', { type: 'warning' })
    await api.deleteSkill(row.id)
    ElMessage.success('已删除')
    await load()
  } catch {}
}

function openUpload() { uploadVisible.value = true }
function onUploadDone() { ElMessage.success('上传成功'); uploadVisible.value = false; uploadRef.value?.clearFiles(); load() }
function onUploadErr(e: any) { ElMessage.error(e?.message || '上传失败') }

async function openDetail(row: any) {
  detailSkill.value = row
  detailTitle.value = `${row.name} (${row.code})`
  currentFile.value = null
  editingFile.value = false
  detailVisible.value = true
  try {
    tree.value = await api.skillTree(row.id)
    // 自动加载 SKILL.md
    if (tree.value?.tree) {
      const skillMd = findSkillMd(tree.value.tree)
      if (skillMd) loadFile(skillMd.path)
    }
  } catch { tree.value = null }
}

function findSkillMd(nodes: any[]): any {
  for (const node of nodes) {
    if (node.name?.toUpperCase() === 'SKILL.MD' && node.type === 'file') return node
    if (node.children) {
      const found = findSkillMd(node.children)
      if (found) return found
    }
  }
  return null
}

function onNodeClick(data: any) {
  if (data.type === 'file') loadFile(data.path)
}

async function loadFile(path: string) {
  if (!detailSkill.value) return
  editingFile.value = false
  try {
    const r = await api.skillFile(detailSkill.value.id, path)
    currentFile.value = { ...r, path }
  } catch { currentFile.value = null }
}

function startEdit() {
  editBuffer.value = currentFile.value?.content || ''
  editingFile.value = true
  setTimeout(() => editorRef.value?.focus(), 50)
}

function cancelEdit() { editingFile.value = false }

async function saveEdit() {
  if (!detailSkill.value || !currentFile.value) return
  saving.value = true
  try {
    await api.updateSkillFile(detailSkill.value.id, currentFile.value.path, editBuffer.value)
    currentFile.value.content = editBuffer.value
    editingFile.value = false
    ElMessage.success('保存成功')
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '保存失败') }
  finally { saving.value = false }
}

function onTab(e: KeyboardEvent) {
  const ta = e.target as HTMLTextAreaElement
  const s = ta.selectionStart, end = ta.selectionEnd
  editBuffer.value = editBuffer.value.substring(0, s) + '  ' + editBuffer.value.substring(end)
  setTimeout(() => { ta.selectionStart = ta.selectionEnd = s + 2 }, 0)
}

function formatSize(bytes: number) {
  if (!bytes) return ''
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1048576).toFixed(1) + ' MB'
}

async function openSummary(row: any) {
  summaryText.value = ''
  summaryLoading.value = true
  summaryVisible.value = true
  try {
    const r = await api.skillSummary(row.id)
    summaryText.value = r?.summary || ''
  } catch { summaryText.value = '' }
  finally { summaryLoading.value = false }
}
</script>

<style scoped>
.skills-page {
  background: var(--m-bg);
  min-height: 100vh;
}

/* 卡片网格 */
.skills-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 24px;
}

/* 技能卡片 */
.skill-card {
  position: relative;
  border-radius: 16px;
  background: var(--m-surface);
  border: 1px solid var(--m-border);
  padding: 20px;
  transition: all 0.2s ease;
}

.skill-card:hover {
  border-color: var(--m-border-strong);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

/* 卡片头部 */
.skill-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.skill-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  background: var(--m-primary);
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.2s ease;
}

.skill-icon:hover {
  transform: scale(1.05);
}

.icon-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.icon-text {
  font-size: 20px;
  font-weight: 600;
  color: var(--m-surface);
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--m-text-tertiary);
}

.status-dot.online {
  background: var(--m-success);
}

/* 卡片内容 */
.skill-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--m-text);
  margin: 0 0 4px 0;
}

.skill-code {
  font-size: 12px;
  color: var(--m-text-tertiary);
  font-family: 'Roboto Mono', monospace;
  margin: 0 0 12px 0;
}

.skill-desc {
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
.skill-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.type-tag {
  padding: 4px 10px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 500;
}

.type-tag.atomic {
  background: var(--m-primary-soft);
  color: var(--m-primary);
}

.type-tag.composite {
  background: rgba(219, 39, 119, 0.1);
  color: #DB2777;
}

.version-tag,
.source-tag {
  padding: 4px 10px;
  border-radius: 8px;
  font-size: 12px;
  background: var(--m-bg-soft);
  color: var(--m-text-secondary);
}

/* 操作按钮 */
.skill-actions {
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
  min-height: 240px;
  cursor: pointer;
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
}

.icon-preview .icon-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.icon-preview .icon-text {
  font-size: 24px;
  font-weight: 600;
  color: var(--m-surface);
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

/* 详情抽屉 */
.detail-wrap {
  display: flex;
  height: 100%;
}

.tree-pane {
  width: 260px;
  border-right: 1px solid var(--m-border);
  padding: 16px;
  overflow-y: auto;
}

.tree-head {
  font-size: 13px;
  font-weight: 600;
  color: var(--m-text);
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--m-border);
}

.tree-node {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}

.file-size {
  margin-left: auto;
  font-size: 11px;
}

.content-pane {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.content-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--m-text-tertiary);
}

.content-head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--m-border);
  background: var(--m-bg-soft);
}

.content-head code {
  font-size: 13px;
  color: var(--m-text);
}

.head-actions {
  margin-left: auto;
}

.content-body {
  flex: 1;
  overflow: auto;
  padding: 16px;
}

.file-content {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
}

.editor-wrap {
  flex: 1;
  padding: 16px;
}

.editor-area {
  width: 100%;
  height: 100%;
  min-height: 400px;
  border: 1px solid var(--m-border);
  border-radius: 8px;
  padding: 12px;
  font-family: 'Roboto Mono', monospace;
  font-size: 13px;
  line-height: 1.6;
  resize: none;
  outline: none;
}

.editor-area:focus {
  border-color: var(--m-primary);
}
</style>
