<template>
  <div class="page">
    <div class="page-head">
      <span class="page-title">部门管理</span>
      <el-button type="primary" @click="openCreate(null)"><el-icon><Plus /></el-icon>新建部门</el-button>
    </div>

    <div class="dep-layout">
      <!-- Left: tree -->
      <div class="dep-pane tree-pane">
        <div class="pane-head">
          <el-icon class="pane-icon"><OfficeBuilding /></el-icon>
          <span class="pane-title">组织架构</span>
          <span class="pane-sub">{{ totalDeps }} 个部门</span>
        </div>

        <div class="pane-search">
          <el-input
            v-model="q"
            placeholder="搜索部门名称或编码"
            clearable
            size="default"
            @input="onSearch"
            @clear="load"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </div>

        <div class="tree-scroll">
          <el-tree
            v-if="tree.length"
            ref="treeRef"
            :data="treeWithAll"
            :props="treeProps"
            node-key="id"
            :default-expand-all="true"
            :expand-on-click-node="false"
            :highlight-current="true"
            :current-node-key="selectedId ?? '__all__'"
            class="dep-tree"
            v-loading="loading"
            @node-click="onSelect"
          >
            <template #default="{ data }">
              <div class="tree-row" :class="{ 'is-all': data.id === '__all__' }">
                <div class="tree-main">
                  <el-icon class="tree-leaf-icon">
                    <Folder v-if="data.id === '__all__' || (data.children && data.children.length)" />
                    <Document v-else />
                  </el-icon>
                  <span class="tree-name">{{ data.name }}</span>
                  <span v-if="data.code && data.id !== '__all__'" class="tree-code">{{ data.code }}</span>
                  <span class="tree-count">{{ data.user_count || 0 }}</span>
                </div>
                <div v-if="data.id !== '__all__'" class="tree-actions" @click.stop>
                  <el-tooltip content="新增子部门" placement="top">
                    <el-button text circle size="small" @click="openCreate(data.id)">
                      <el-icon><Plus /></el-icon>
                    </el-button>
                  </el-tooltip>
                  <el-tooltip content="编辑" placement="top">
                    <el-button text circle size="small" @click="openEdit(data)">
                      <el-icon><EditPen /></el-icon>
                    </el-button>
                  </el-tooltip>
                  <el-tooltip content="删除" placement="top">
                    <el-button text circle size="small" @click="onDelete(data)">
                      <el-icon class="del-ic"><Delete /></el-icon>
                    </el-button>
                  </el-tooltip>
                </div>
              </div>
            </template>
          </el-tree>
          <div v-else-if="!loading" class="empty-hint">
            <el-icon :size="32"><FolderOpened /></el-icon>
            <div>暂无部门</div>
            <el-button text type="primary" @click="openCreate(null)">立即新建</el-button>
          </div>
        </div>
      </div>

      <!-- Right: users in selected department -->
      <div class="dep-pane users-pane">
        <div class="pane-head">
          <el-icon class="pane-icon"><User /></el-icon>
          <span class="pane-title">{{ selectedTitle }}</span>
          <span class="pane-sub">{{ users.total }} 个用户</span>
        </div>

        <div class="pane-search">
          <el-input
            v-model="userQ"
            placeholder="搜索用户名/姓名"
            clearable
            @keydown.enter="onUserFilter"
            @clear="onUserFilter"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </div>

        <el-table
          :data="users.items"
          stripe
          v-loading="usersLoading"
          class="users-table"
          height="100%"
        >
          <el-table-column prop="username" label="用户名" min-width="140" />
          <el-table-column prop="display_name" label="姓名" min-width="120">
            <template #default="{ row }">
              <span v-if="row.display_name">{{ row.display_name }}</span>
              <span v-else class="muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="角色" width="120">
            <template #default="{ row }">{{ row.role?.name }}</template>
          </el-table-column>
          <el-table-column label="部门" min-width="140" v-if="selectedId == null">
            <template #default="{ row }">
              <span v-if="row.department">{{ row.department.name }}</span>
              <span v-else class="muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small" effect="light">
                {{ row.status === 'active' ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <template #empty>
            <div class="users-empty">
              <el-icon :size="28"><User /></el-icon>
              <div>{{ selectedId == null ? '当前没有用户' : '该部门下还没有用户' }}</div>
            </div>
          </template>
        </el-table>

        <div class="pager">
          <el-pagination
            background
            small
            layout="total, prev, pager, next, sizes"
            :total="users.total"
            :page-size="userPageSize"
            :current-page="userPage"
            :page-sizes="[10, 20, 50, 100]"
            @current-change="onUserPageChange"
            @size-change="onUserSizeChange"
          />
        </div>
      </div>
    </div>

    <el-dialog v-model="visible" :title="editing ? '编辑部门' : '新建部门'" width="520px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="编码"><el-input v-model="form.code" /></el-form-item>
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="上级部门">
          <el-tree-select
            v-model="form.parent_id"
            :data="tree"
            :props="{ label: 'name', value: 'id', children: 'children' }"
            node-key="id"
            check-strictly
            clearable
            placeholder="不选则为顶级"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="排序"><el-input-number v-model="form.sort" :min="0" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" @click="onSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'

const tree = ref<any[]>([])
const loading = ref(false)
const visible = ref(false)
const editing = ref<any | null>(null)
const q = ref('')
const form = reactive<any>(emptyForm())
const treeRef = ref<any>(null)

// selection: null = "全部" virtual node
const selectedId = ref<number | null>(null)
const selectedName = ref<string>('全部用户')

// users panel state
const users = ref<{ items: any[]; total: number }>({ items: [], total: 0 })
const usersLoading = ref(false)
const userQ = ref('')
const userPage = ref(1)
const userPageSize = ref(20)

const treeProps = { label: 'name', children: 'children' }

function emptyForm() {
  return { code: '', name: '', parent_id: null as number | null, sort: 0, description: '' }
}

const treeWithAll = computed(() => {
  const totalUsers = sumUsers(tree.value)
  return [
    { id: '__all__', name: '全部用户', user_count: totalUsers, children: tree.value },
  ]
})

function sumUsers(nodes: any[]): number {
  let n = 0
  for (const x of nodes) {
    n += x.user_count || 0
    n += sumUsers(x.children || [])
  }
  return n
}

const totalDeps = computed(() => countNodes(tree.value))
function countNodes(nodes: any[]): number {
  let n = 0
  for (const x of nodes) { n += 1 + countNodes(x.children || []) }
  return n
}

const selectedTitle = computed(() =>
  selectedId.value == null ? '全部用户' : `${selectedName.value} 的用户`
)

let searchTimer: any = null
function onSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(load, 200)
}

async function load() {
  loading.value = true
  try {
    let data = await api.departmentTree()
    if (q.value.trim()) {
      const kw = q.value.trim().toLowerCase()
      data = filterTree(data, (n: any) =>
        (n.name || '').toLowerCase().includes(kw) || (n.code || '').toLowerCase().includes(kw))
    }
    tree.value = data
  } finally {
    loading.value = false
  }
  await nextTick()
  // restore tree highlight
  treeRef.value?.setCurrentKey(selectedId.value ?? '__all__')
}

function filterTree(nodes: any[], pred: (n: any) => boolean): any[] {
  const out: any[] = []
  for (const n of nodes) {
    const kids = filterTree(n.children || [], pred)
    if (pred(n) || kids.length) out.push({ ...n, children: kids })
  }
  return out
}

async function loadUsers() {
  usersLoading.value = true
  try {
    const offset = (userPage.value - 1) * userPageSize.value
    users.value = await api.users({
      q: userQ.value.trim() || undefined,
      department_id: selectedId.value ?? undefined,
      limit: userPageSize.value,
      offset,
    })
  } finally {
    usersLoading.value = false
  }
}

function onSelect(data: any) {
  if (data.id === '__all__') {
    selectedId.value = null
    selectedName.value = '全部用户'
  } else {
    selectedId.value = data.id
    selectedName.value = data.name
  }
  userPage.value = 1
  loadUsers()
}

function onUserFilter() { userPage.value = 1; loadUsers() }
function onUserPageChange(p: number) { userPage.value = p; loadUsers() }
function onUserSizeChange(s: number) { userPageSize.value = s; userPage.value = 1; loadUsers() }

onMounted(async () => {
  await load()
  await loadUsers()
})

function openCreate(parentId: number | null) {
  editing.value = null
  Object.assign(form, emptyForm())
  form.parent_id = parentId
  visible.value = true
}

function openEdit(row: any) {
  editing.value = row
  Object.assign(form, {
    code: row.code, name: row.name, parent_id: row.parent_id,
    sort: row.sort || 0, description: row.description || '',
  })
  visible.value = true
}

async function onSubmit() {
  try {
    if (editing.value) await api.updateDepartment(editing.value.id, form)
    else await api.createDepartment(form)
    visible.value = false
    ElMessage.success('保存成功')
    await load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  }
}

async function onDelete(row: any) {
  try {
    await ElMessageBox.confirm(`删除部门 "${row.name}"?`, '确认', { type: 'warning' })
  } catch { return }
  try {
    await api.deleteDepartment(row.id)
    ElMessage.success('已删除')
    if (selectedId.value === row.id) {
      selectedId.value = null
      selectedName.value = '全部用户'
    }
    await load()
    await loadUsers()
  } catch (e: any) {
    const msg = e?.response?.data?.detail || '删除失败'
    if (e?.response?.status === 400 && msg.includes('用户')) {
      try {
        await ElMessageBox.confirm(msg + ' 是否强制解除关联并删除?', '确认', { type: 'warning' })
        await api.deleteDepartment(row.id, true)
        ElMessage.success('已删除')
        if (selectedId.value === row.id) {
          selectedId.value = null
          selectedName.value = '全部用户'
        }
        await load()
        await loadUsers()
      } catch {}
    } else {
      ElMessage.error(msg)
    }
  }
}
</script>

<style scoped>
.page-head {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 16px;
}
.page-title { font-size: 18px; font-weight: 600; }

/* ---------- Two-pane layout ---------- */
.dep-layout {
  display: grid;
  grid-template-columns: 360px 1fr;
  gap: 16px;
  height: calc(100vh - 160px);
  min-height: 480px;
}
.dep-pane {
  background: var(--m-surface);
  border: 1px solid var(--m-border);
  border-radius: var(--m-radius-lg);
  display: flex; flex-direction: column;
  overflow: hidden;
}

.pane-head {
  display: flex; align-items: center; gap: 8px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--m-border);
  background: var(--m-bg-soft);
}
.pane-icon { color: var(--m-primary); }
.pane-title { font-size: 14px; font-weight: 600; color: var(--m-text); }
.pane-sub { margin-left: auto; font-size: 12px; color: var(--m-text-tertiary); }

.pane-search { padding: 12px 12px 4px; }

/* ---------- Tree pane ---------- */
.tree-scroll { flex: 1; overflow: auto; padding: 4px 8px 12px; }
.dep-tree {
  background: transparent;
  --el-tree-node-hover-bg-color: var(--m-surface-variant);
  --el-tree-node-content-height: 36px;
}
.dep-tree :deep(.el-tree-node__content) {
  border-radius: var(--m-radius);
  padding-right: 4px;
  margin: 2px 0;
}
.dep-tree :deep(.el-tree-node.is-current > .el-tree-node__content) {
  background: var(--m-primary-soft);
}
.dep-tree :deep(.el-tree-node.is-current > .el-tree-node__content) .tree-name { color: var(--m-primary-hover); font-weight: 600; }
.dep-tree :deep(.el-tree-node.is-current > .el-tree-node__content) .tree-leaf-icon { color: var(--m-primary); }

.tree-row {
  flex: 1; display: flex; align-items: center; justify-content: space-between; gap: 8px;
  min-width: 0;
  padding-right: 4px;
}
.tree-row.is-all .tree-name { font-weight: 600; }
.tree-main { display: flex; align-items: center; gap: 8px; min-width: 0; flex: 1; }
.tree-leaf-icon { color: var(--m-text-secondary); flex-shrink: 0; }
.tree-name {
  color: var(--m-text); font-size: 13px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.tree-code {
  font-size: 11px; color: var(--m-text-tertiary);
  font-family: 'Roboto Mono', monospace;
}
.tree-count {
  margin-left: auto;
  min-width: 22px; padding: 0 6px;
  font-size: 11px; color: var(--m-text-secondary);
  background: var(--m-surface-variant);
  border-radius: 999px;
  text-align: center; line-height: 18px;
  flex-shrink: 0;
}
.tree-actions { display: none; gap: 0; flex-shrink: 0; }
.tree-actions :deep(.el-button) { padding: 4px; height: 24px; width: 24px; min-height: 0; }
.tree-actions .del-ic { color: var(--m-danger, #d33); }
.dep-tree :deep(.el-tree-node__content):hover .tree-actions { display: flex; }
.dep-tree :deep(.el-tree-node__content):hover .tree-count { display: none; }

.empty-hint {
  padding: 48px 24px; text-align: center;
  color: var(--m-text-tertiary); font-size: 13px;
  display: flex; flex-direction: column; align-items: center; gap: 8px;
}

/* ---------- Users pane ---------- */
.users-pane { display: flex; flex-direction: column; min-height: 0; }
.users-table { flex: 1; min-height: 0; }
.users-table :deep(.el-table__inner-wrapper) { height: 100%; }
.users-empty {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  padding: 32px;
  color: var(--m-text-tertiary);
}
.muted { color: var(--m-text-tertiary); }
.pager {
  display: flex; justify-content: flex-end;
  padding: 10px 16px;
  border-top: 1px solid var(--m-border);
  background: var(--m-bg-soft);
}

@media (max-width: 1024px) {
  .dep-layout { grid-template-columns: 1fr; height: auto; }
}
</style>
