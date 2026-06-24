<template>
  <div class="layout">
    <!-- Side rail -->
    <aside :class="['rail', { collapsed: railCollapsed }]">
      <div class="rail-top">
        <div v-if="!railCollapsed" class="rail-brand">
          <img class="brand-logo" src="/logo-icon.png" alt="Agent Mill" />
          <div class="brand-text">
            <div class="brand-name">Agent Mill</div>
            <div class="brand-slogan">你的数字员工工厂</div>
          </div>
        </div>
        <img v-else class="brand-logo-only" src="/logo-icon.png" alt="Agent Mill" />
        <button class="rail-toggle" @click="toggleRail" :title="railCollapsed ? '展开侧边栏' : '收起侧边栏'">
          <el-icon :size="18"><Fold v-if="!railCollapsed" /><Expand v-else /></el-icon>
        </button>
      </div>

      <nav class="rail-nav">
        <button class="rail-item rail-new" :disabled="!chat.currentAgent" @click="onNewConv">
          <el-icon :size="20"><Plus /></el-icon>
          <span>新对话</span>
        </button>

        <!-- 指挥中心入口 - 所有角色可见 -->
        <router-link to="/command" class="rail-item" active-class="active" data-tip="指挥中心">
          <el-icon :size="20"><Monitor /></el-icon><span>指挥中心</span>
        </router-link>

        <!-- Manager: collapsible side panel for both history & agent (saves rail space for admin nav) -->
        <template v-if="auth.canManage">
          <div class="rail-sub-row">
            <button
              :class="['rail-sub', { active: subPanel === 'history' }]"
              @click="togglePanel('history')"
            >
              <el-icon :size="16"><ChatLineRound /></el-icon>
              <span>对话历史</span>
            </button>
            <button
              :class="['rail-sub', { active: subPanel === 'agent' }]"
              @click="togglePanel('agent')"
            >
              <el-icon :size="16"><Promotion /></el-icon>
              <span>数字员工</span>
            </button>
          </div>

          <div class="rail-divider">工作台</div>
          <router-link to="/admin/agents" class="rail-item" active-class="active" data-tip="数字员工">
            <el-icon :size="20"><Promotion /></el-icon><span>数字员工</span>
          </router-link>
          <router-link to="/admin/skills" class="rail-item" active-class="active" data-tip="技能">
            <el-icon :size="20"><MagicStick /></el-icon><span>技能</span>
          </router-link>
          <router-link to="/admin/mcp" class="rail-item" active-class="active" data-tip="连接器">
            <el-icon :size="20"><Connection /></el-icon><span>连接器</span>
          </router-link>
          <router-link to="/admin/models" class="rail-item" active-class="active" data-tip="模型">
            <el-icon :size="20"><Cpu /></el-icon><span>模型</span>
          </router-link>
          <router-link to="/admin/packs" class="rail-item" active-class="active" data-tip="方案包">
            <el-icon :size="20"><CollectionTag /></el-icon><span>方案包</span>
          </router-link>
          <router-link to="/admin/workflows" class="rail-item" active-class="active" data-tip="工作流">
            <el-icon :size="20"><Connection /></el-icon><span>工作流</span>
          </router-link>
          <router-link to="/admin/templates" class="rail-item" active-class="active" data-tip="模板市场">
            <el-icon :size="20"><Grid /></el-icon><span>模板市场</span>
          </router-link>
          <router-link to="/admin/knowledge" class="rail-item" active-class="active" data-tip="知识库">
            <el-icon :size="20"><Collection /></el-icon><span>知识库</span>
          </router-link>
          <router-link to="/tasks" class="rail-item" active-class="active" data-tip="自动化">
            <el-icon :size="20"><AlarmClock /></el-icon><span>自动化</span>
          </router-link>
          <router-link to="/space" class="rail-item" active-class="active" data-tip="空间">
            <el-icon :size="20"><Star /></el-icon><span>空间</span>
          </router-link>
        </template>

        <!-- Regular user: automation + space + inline history list -->
        <template v-else>
          <router-link to="/tasks" class="rail-item" active-class="active" data-tip="自动化">
            <el-icon :size="20"><AlarmClock /></el-icon><span>自动化</span>
          </router-link>
          <router-link to="/space" class="rail-item" active-class="active" data-tip="空间">
            <el-icon :size="20"><Star /></el-icon><span>空间</span>
          </router-link>

          <div class="rail-divider">对话历史</div>
          <div class="rail-history">
            <div v-if="!chat.convs.length" class="empty-hint">暂无对话</div>
            <div
              v-for="c in chat.convs"
              :key="c.id"
              :class="['conv-item', { active: c.id === chat.currentConvId }]"
              @click="onPickConv(c)"
            >
              <el-icon class="conv-icon"><ChatLineRound /></el-icon>
              <div class="conv-title">{{ c.title }}</div>
              <div class="conv-actions" @click.stop>
                <el-icon @click="onRename(c)" title="重命名"><EditPen /></el-icon>
                <el-icon @click="onDelete(c)" title="删除"><Delete /></el-icon>
              </div>
            </div>
          </div>
        </template>

        <!-- 系统管理折叠组 - 仅 admin 可见 -->
        <div
          :class="['rail-group', { open: sysGroupOpen }]"
          v-if="auth.isAdmin"
        >
          <button class="rail-group-header" @click="sysGroupOpen = !sysGroupOpen" data-tip="系统管理">
            <el-icon :size="20"><Setting /></el-icon>
            <span>系统管理</span>
            <el-icon class="rail-group-arrow" :size="14"><ArrowDown /></el-icon>
          </button>
          <transition name="group-slide">
            <div v-show="sysGroupOpen" class="rail-group-body">
              <router-link to="/admin/logs" class="rail-item rail-item-sub" active-class="active" data-tip="日志">
                <el-icon :size="18"><Document /></el-icon><span>日志</span>
              </router-link>
              <router-link to="/admin/users" class="rail-item rail-item-sub" active-class="active" data-tip="用户">
                <el-icon :size="18"><User /></el-icon><span>用户</span>
              </router-link>
              <router-link to="/admin/departments" class="rail-item rail-item-sub" active-class="active" data-tip="部门">
                <el-icon :size="18"><OfficeBuilding /></el-icon><span>部门</span>
              </router-link>
              <router-link to="/admin/roles" class="rail-item rail-item-sub" active-class="active" data-tip="角色">
                <el-icon :size="18"><UserFilled /></el-icon><span>角色</span>
              </router-link>
              <router-link to="/admin/quotas" class="rail-item rail-item-sub" active-class="active" data-tip="额度管理">
                <el-icon :size="18"><Tickets /></el-icon><span>额度管理</span>
              </router-link>
              <router-link to="/admin/memories" class="rail-item rail-item-sub" active-class="active" data-tip="记忆管理">
                <el-icon :size="18"><ChatDotRound /></el-icon><span>记忆管理</span>
              </router-link>
            </div>
          </transition>
        </div>
      </nav>
    </aside>

    <!-- Sub panel: slides next to the rail (managers see both, regular users only agent) -->
    <aside v-if="subPanel" class="sub-panel">
      <div class="sub-head">
        <span class="sub-title">{{ subPanel === 'history' ? '对话历史' : '数字员工' }}</span>
        <button class="sub-close" @click="subPanel = null" title="收起">
          <el-icon :size="16"><Close /></el-icon>
        </button>
      </div>

      <div v-if="subPanel === 'history'" class="sub-body">
        <div v-if="!chat.convs.length" class="empty-hint">暂无对话</div>
        <div
          v-for="c in chat.convs"
          :key="c.id"
          :class="['conv-item', { active: c.id === chat.currentConvId }]"
          @click="onPickConv(c)"
        >
          <el-icon class="conv-icon"><ChatLineRound /></el-icon>
          <div class="conv-title">{{ c.title }}</div>
          <div class="conv-actions" @click.stop>
            <el-icon @click="onRename(c)" title="重命名"><EditPen /></el-icon>
            <el-icon @click="onDelete(c)" title="删除"><Delete /></el-icon>
          </div>
        </div>
      </div>

      <div v-else-if="subPanel === 'agent'" class="sub-body">
        <div v-if="!chat.agents.length" class="empty-hint">暂无可用数字员工</div>
        <div
          v-for="a in chat.agents"
          :key="a.id"
          :class="['agent-item', { active: a.id === chat.currentAgent?.id }]"
          @click="onPickAgent(a)"
        >
          <div class="agent-icon"><el-icon :size="18"><Promotion /></el-icon></div>
          <div class="agent-meta">
            <div class="agent-row">
              <span class="agent-name">{{ a.name }}</span>
              <el-tag v-if="a.id === chat.defaultAgent?.id" size="small" effect="light" type="primary">默认</el-tag>
              <el-icon v-if="a.id === chat.currentAgent?.id" class="agent-check"><Check /></el-icon>
            </div>
            <div class="agent-desc" :title="a.description || a.code || ''">{{ a.description || a.code || '暂无介绍' }}</div>

            <div class="agent-caps" @click.stop>
              <!-- Row 1: model (single line, name truncates with …) -->
              <div class="cap-row cap-row-model">
                <span class="cap-item">
                  <el-icon :size="13"><Cpu /></el-icon>
                  <span class="cap-label">模型:</span>
                  <span class="cap-value" :title="capModel(a.id)">{{ capModel(a.id) }}</span>
                </span>
              </div>

              <!-- Row 2: skills + MCP popovers -->
              <div class="cap-row cap-row-tools">
                <!-- Skills popover -->
                <el-popover
                  placement="right-start"
                  :width="320"
                  trigger="click"
                  @before-enter="ensureCaps(a.id, true)"
                >
                  <template #reference>
                    <a class="cap-link" @click.stop>
                      <el-icon :size="13"><MagicStick /></el-icon>
                      技能 ({{ a.skill_ids?.length || 0 }})
                    </a>
                  </template>
                  <div class="pop-body">
                    <div class="pop-title">技能 ({{ a.skill_ids?.length || 0 }})</div>
                    <div v-if="capsLoading[a.id]" class="pop-empty">加载中…</div>
                    <div v-else-if="!caps[a.id]?.skills?.length" class="pop-empty">未挂载技能</div>
                    <div v-else class="pop-list">
                      <div v-for="s in caps[a.id].skills" :key="s.id" class="pop-row">
                        <div class="pop-row-head">
                          <span class="pop-name">{{ s.name }}</span>
                          <el-tag size="small" effect="light">{{ s.type }}</el-tag>
                        </div>
                        <div class="pop-desc">{{ s.description || s.code || '暂无描述' }}</div>
                      </div>
                  </div>
                </div>
              </el-popover>

              <!-- MCP popover -->
              <el-popover
                placement="right-start"
                :width="380"
                trigger="click"
                @before-enter="ensureCaps(a.id, true)"
              >
                <template #reference>
                  <a class="cap-link" @click.stop>
                    <el-icon :size="13"><Connection /></el-icon>
                    连接器 ({{ a.mcp_ids?.length || 0 }})
                  </a>
                </template>
                <div class="pop-body">
                  <div class="pop-title">连接器工具 ({{ a.mcp_ids?.length || 0 }})</div>
                  <div v-if="capsLoading[a.id]" class="pop-empty">加载中…</div>
                  <div v-else-if="!caps[a.id]?.mcps?.length" class="pop-empty">未挂载连接器</div>
                  <div v-else class="pop-list">
                    <div v-for="m in caps[a.id].mcps" :key="m.id" class="pop-row">
                      <div class="pop-row-head">
                        <span class="pop-name">{{ m.name }}</span>
                        <el-tag size="small" effect="light">{{ m.transport }}</el-tag>
                        <span class="pop-row-actions">
                          <a v-if="!mcpTools[mcpKey(a.id, m.id)] && !mcpToolsLoading[mcpKey(a.id, m.id)]"
                             class="cap-link cap-link-sm" @click.stop="openMcpTools(a.id, m.id)">查看工具</a>
                          <a v-else-if="mcpTools[mcpKey(a.id, m.id)]"
                             class="cap-link cap-link-sm" @click.stop="toggleMcpTools(a.id, m.id)">
                             {{ mcpToolsExpanded[mcpKey(a.id, m.id)] ? '收起' : '展开' }}
                          </a>
                          <a v-if="mcpTools[mcpKey(a.id, m.id)]"
                             class="cap-link cap-link-sm" @click.stop="loadMcpTools(a.id, m.id)">刷新</a>
                        </span>
                      </div>
                      <div v-if="mcpToolsLoading[mcpKey(a.id, m.id)]" class="pop-desc">连接中…</div>
                      <div v-else-if="mcpToolsError[mcpKey(a.id, m.id)]" class="pop-desc err">{{ mcpToolsError[mcpKey(a.id, m.id)] }}</div>
                      <div v-else-if="mcpTools[mcpKey(a.id, m.id)] && mcpToolsExpanded[mcpKey(a.id, m.id)]" class="mcp-tools">
                        <div v-if="!mcpTools[mcpKey(a.id, m.id)].length" class="pop-desc">该连接器没有可用工具</div>
                        <div v-for="t in mcpTools[mcpKey(a.id, m.id)]" :key="t.name" class="mcp-tool">
                          <code class="mcp-tool-name">{{ t.name }}</code>
                          <span v-if="t.description" class="mcp-tool-desc">— {{ t.description }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </el-popover>
              </div><!-- /cap-row-tools -->
            </div>
          </div>
        </div>
      </div>
    </aside>

    <!-- Main -->
    <div class="main">
      <header class="topbar">
        <div class="topbar-left">
          <div v-if="route.path === '/chat' && chat.currentAgent" class="agent-chip" @click="togglePanel('agent')">
            <div class="agent-chip-icon"><el-icon :size="14"><Promotion /></el-icon></div>
            <div class="agent-chip-meta">
              <span class="agent-chip-label">当前员工</span>
              <span class="agent-chip-name">{{ chat.currentAgent.name }}</span>
            </div>
            <el-icon class="agent-chip-arrow"><ArrowDown /></el-icon>
          </div>
        </div>
        <div class="topbar-right">
          <NotificationBell />
          <button class="theme-btn" @click="toggleTheme" :title="isDark ? '亮色模式' : '暗色模式'" :aria-label="isDark ? '切换亮色模式' : '切换暗色模式'">
            <div class="theme-btn-track">
              <svg class="theme-icon sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="5" />
                <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
              </svg>
              <svg class="theme-icon moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
              </svg>
              <span class="theme-knob" :class="{ dark: isDark }" />
            </div>
          </button>
          <router-link v-if="auth.canManage" to="/admin/dashboard" class="topbar-icon-btn" title="统计面板">
            <el-icon :size="18"><DataAnalysis /></el-icon>
          </router-link>
          <el-dropdown trigger="click">
            <div class="user-chip">
              <div class="avatar"><el-icon :size="16"><UserFilled /></el-icon></div>
              <div class="user-meta">
                <div class="name">{{ auth.user?.display_name || auth.user?.username }}</div>
                <div class="role">{{ auth.user?.role?.name }}</div>
              </div>
              <el-icon><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="onChangePassword"><el-icon><Key /></el-icon>修改密码</el-dropdown-item>
                <el-dropdown-item @click="onUpdateEmail"><el-icon><Message /></el-icon>设置邮箱</el-dropdown-item>
                <el-dropdown-item divided @click="onLogout"><el-icon><SwitchButton /></el-icon>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>
      <main class="content">
        <router-view />
      </main>
    </div>
  </div>

  <!-- 删除确认弹窗 -->
  <transition name="del-fade">
    <div v-if="deleteTarget" class="del-overlay" @click.self="deleteTarget = null">
      <div class="del-dialog">
        <div class="del-header">
          <div class="del-icon">
            <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 8v4M12 16" />
            </svg>
          </div>
          <div class="del-title">确认删除对话</div>
        </div>
        <div class="del-body">
          <p>确定要永久删除该对话吗？</p>
          <div class="del-target">{{ deleteTarget?.title || '未命名对话' }}</div>
        </div>
        <div class="del-footer">
          <el-button @click="deleteTarget = null">取消</el-button>
          <el-button type="danger" :loading="deleting" @click="confirmDelete">确认删除</el-button>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox, ElMessage } from 'element-plus'
import { api } from '@/api'
import { useAuth } from '@/stores/auth'
import { useChat } from '@/stores/chat'
import NotificationBell from '@/components/NotificationBell.vue'

const router = useRouter()
const route = useRoute()
const auth = useAuth()
const chat = useChat()

const subPanel = ref<'history' | 'agent' | null>(null)
const sysGroupOpen = ref(true)
const railCollapsed = ref(localStorage.getItem('rail_collapsed') === 'true')
const isDark = ref(document.documentElement.getAttribute('data-theme') === 'dark')
const deleteTarget = ref<any>(null)
const deleting = ref(false)

function toggleTheme() {
  isDark.value = !isDark.value
  document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light')
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
}

// on mount: 读取主题偏好
const savedTheme = localStorage.getItem('theme')
if (savedTheme) {
  isDark.value = savedTheme === 'dark'
  document.documentElement.setAttribute('data-theme', savedTheme)
}

function toggleRail() {
  railCollapsed.value = !railCollapsed.value
  localStorage.setItem('rail_collapsed', String(railCollapsed.value))
  // 收起时关闭子面板
  if (railCollapsed.value) subPanel.value = null
}

// per-agent capability cache (model + skills + mcps), populated lazily on popover open
const caps = reactive<Record<number, any>>({})
const capsLoading = reactive<Record<number, boolean>>({})
// per-(agent,mcp) tool cache, populated only when user clicks "查看工具"
const mcpTools = reactive<Record<string, any[]>>({})
const mcpToolsLoading = reactive<Record<string, boolean>>({})
const mcpToolsError = reactive<Record<string, string>>({})
const mcpToolsExpanded = reactive<Record<string, boolean>>({})
const mcpKey = (aid: number, mid: number) => `${aid}:${mid}`

async function ensureCaps(agentId: number, force = false) {
  // popover/drawer reopen flow: when `force` is true, always refetch so we
  // pick up admin edits to user_summary / tool_summaries that happened after
  // the first cache hit.
  if (!force && (caps[agentId] || capsLoading[agentId])) return
  capsLoading[agentId] = true
  try {
    caps[agentId] = await api.agentCapabilities(agentId)
  } catch {
    if (!caps[agentId]) caps[agentId] = { model: null, skills: [], mcps: [] }
  } finally {
    capsLoading[agentId] = false
  }
}

function capModel(agentId: number) {
  const c = caps[agentId]
  if (!c) return capsLoading[agentId] ? '…' : '点击加载'
  const m = c.model
  if (!m) return '未配置'
  return m.code || m.model_id || `#${m.id}`
}

async function loadMcpTools(agentId: number, mcpId: number) {
  const k = mcpKey(agentId, mcpId)
  if (mcpToolsLoading[k]) return
  mcpToolsLoading[k] = true
  delete mcpToolsError[k]
  try {
    const info = await api.agentMcpTools(agentId, mcpId)
    mcpTools[k] = info.tools || []
    mcpToolsExpanded[k] = true
  } catch (e: any) {
    mcpToolsError[k] = e?.response?.data?.detail || e?.message || '加载失败'
  } finally {
    mcpToolsLoading[k] = false
  }
}

function openMcpTools(agentId: number, mcpId: number) {
  loadMcpTools(agentId, mcpId)
}

function toggleMcpTools(agentId: number, mcpId: number) {
  const k = mcpKey(agentId, mcpId)
  mcpToolsExpanded[k] = !mcpToolsExpanded[k]
}

onMounted(() => {
  if (!chat.loaded) chat.loadInit()
})

function togglePanel(name: 'history' | 'agent') {
  if (!auth.canManage && name === 'history') return
  subPanel.value = subPanel.value === name ? null : name
  if (subPanel.value === 'agent') {
    chat.agents.forEach((a) => ensureCaps(a.id))
  }
}

async function onNewConv() {
  if (!chat.currentAgent) { ElMessage.warning('请先选择数字员工'); return }
  subPanel.value = null
  await chat.newConv()
  if (router.currentRoute.value.path !== '/chat') {
    router.push('/chat').catch(() => {})
  }
}

async function onPickConv(c: any) {
  subPanel.value = null
  try {
    await chat.selectConv(c)
    if (router.currentRoute.value.path !== '/chat') {
      router.push('/chat').catch(() => {})
    }
  } catch { ElMessage.error('加载对话失败') }
}

function onDelete(c: any) {
  deleteTarget.value = c
}

async function confirmDelete() {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    await chat.deleteConv(deleteTarget.value)
    ElMessage.success('已删除')
    deleteTarget.value = null
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  } finally {
    deleting.value = false
  }
}

async function onRename(c: any) {
  try {
    const { value } = await ElMessageBox.prompt('新标题', '重命名', { inputValue: c.title })
    await chat.renameConv(c, value)
  } catch {}
}

async function onPickAgent(a: any) {
  // Collapse the agent picker panel regardless — the user has made a choice.
  subPanel.value = null
  // Same agent: nothing else to do.
  if (a?.id === chat.currentAgent?.id) return
  chat.selectAgent(a)
  // If there's an active conversation, force a brand-new one with the new agent
  // so prior chat history (tied to the previous agent) doesn't bleed in.
  // No active conv yet → defer creation until the user actually sends a message.
  if (chat.currentConvId) {
    try { await chat.newConv() } catch {}
  }
  if (router.currentRoute.value.path !== '/chat') {
    await nextTick()
    router.push('/chat').catch(() => {})
  }
}

function onLogout() {
  auth.logout()
  router.push('/login').catch(() => {})
}

async function onUpdateEmail() {
  try {
    const r = await ElMessageBox.prompt('用于任务通知接收', '设置邮箱', {
      inputType: 'email',
      inputValue: auth.user?.email || '',
      confirmButtonText: '保存',
      cancelButtonText: '取消',
      inputValidator: (v) => !v || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v) || '邮箱格式不正确',
    })
    await api.updateEmail((r.value || '').trim() || null)
    await auth.fetchMe()
    ElMessage.success('已保存')
  } catch {}
}

async function onChangePassword() {
  let oldPwd = ''
  try {
    const r1 = await ElMessageBox.prompt('请输入原密码', '修改密码', {
      inputType: 'password',
      confirmButtonText: '下一步',
      cancelButtonText: '取消',
      inputValidator: (v) => (!!v && v.length >= 6) || '密码至少 6 位',
    })
    oldPwd = r1.value
  } catch { return }
  let newPwd = ''
  try {
    const r2 = await ElMessageBox.prompt('请输入新密码（不少于 6 位）', '修改密码', {
      inputType: 'password',
      confirmButtonText: '下一步',
      cancelButtonText: '取消',
      inputValidator: (v) => (!!v && v.length >= 6) || '密码至少 6 位',
    })
    newPwd = r2.value
  } catch { return }
  try {
    const r3 = await ElMessageBox.prompt('请再次输入新密码', '修改密码', {
      inputType: 'password',
      confirmButtonText: '提交',
      cancelButtonText: '取消',
      inputValidator: (v) => v === newPwd || '两次密码不一致',
    })
    if (r3.value !== newPwd) return
  } catch { return }
  try {
    await api.changePassword(oldPwd, newPwd)
    ElMessage.success('密码已更新，请重新登录')
    auth.logout()
    router.push('/login')
  } catch {
    // interceptor shows error
  }
}
</script>

<style scoped>
.layout { display: flex; height: 100vh; background: var(--m-bg); overflow: hidden; }

/* ---------- Side rail ---------- */
.rail {
  width: 240px; flex-shrink: 0;
  background: var(--m-bg-soft);
  padding: 20px 12px;
  display: flex; flex-direction: column;
  overflow: hidden;
  transition: width .22s ease;
}
.rail.collapsed { width: 64px; padding: 20px 10px; }

/* ---------- Rail top (brand + toggle) ---------- */
.rail-top {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 4px 24px;
  min-height: 48px;
}
.rail-brand { display:flex; align-items:center; gap: 12px; flex: 1; min-width: 0; }
.brand-logo {
  width: 44px; height: 44px; border-radius: 12px;
  object-fit: cover; object-position: center 35%;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(0,0,0,.1);
  background: var(--m-surface);
}
.brand-logo-only {
  width: 44px; height: 44px; border-radius: 12px;
  object-fit: cover; object-position: center 35%;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(0,0,0,.1);
  background: var(--m-surface);
}
.brand-text { display: flex; flex-direction: column; gap: 1px; overflow: hidden; }
.brand-name { font-size: 18px; font-weight: 700; letter-spacing: -0.02em; line-height: 1.2; white-space: nowrap; }
.brand-slogan { font-size: 11px; color: var(--m-text-tertiary); letter-spacing: 0.02em; white-space: nowrap; }
.rail-toggle {
  flex-shrink: 0;
  width: 32px; height: 32px;
  display: flex; align-items: center; justify-content: center;
  background: transparent; border: none;
  border-radius: var(--m-radius);
  color: var(--m-text-secondary);
  cursor: pointer;
  transition: background .15s, color .15s;
}
.rail-toggle:hover { background: var(--m-surface-variant); color: var(--m-text); }
.rail.collapsed .rail-brand { display: none; }

.rail-nav { display:flex; flex-direction: column; gap: 2px; min-height: 0; flex: 1; overflow-y: auto; overflow-x: hidden; }
.rail-nav::-webkit-scrollbar { width: 4px; }
.rail-nav::-webkit-scrollbar-thumb { background: var(--m-border); border-radius: 4px; }
.rail-nav::-webkit-scrollbar-track { background: transparent; }
.rail-divider {
  font-size: 11px; font-weight: 600; color: var(--m-text-tertiary);
  letter-spacing: .08em; text-transform: uppercase;
  padding: 18px 16px 6px;
}
.rail.collapsed .rail-divider { display: none; }
.rail-item {
  display: flex; align-items: center; gap: 14px;
  padding: 10px 16px;
  color: var(--m-text);
  background: transparent; border: none;
  border-radius: var(--m-radius-pill);
  text-decoration: none; text-align: left;
  font-size: 14px; font-weight: 500;
  cursor: pointer;
  transition: background .15s ease, border-color .15s ease;
  position: relative;
  white-space: nowrap;
}
.rail-item:hover:not(:disabled) { background: var(--m-surface-variant); }
.rail-item:disabled { color: var(--m-text-tertiary); cursor: not-allowed; }
.rail-item.active { background: var(--m-primary-soft); color: var(--m-primary-hover); }
.rail-item.active :deep(.el-icon) { color: var(--m-primary); }

/* Collapsed: center icons, hide text, show tooltip */
.rail.collapsed .rail-item {
  justify-content: center;
  padding: 10px;
}
.rail.collapsed .rail-item span { display: none; }
.rail.collapsed .rail-item::after {
  content: attr(data-tip);
  position: absolute;
  left: calc(100% + 10px);
  top: 50%; transform: translateY(-50%);
  background: var(--m-text);
  color: var(--m-bg);
  padding: 5px 10px;
  border-radius: 6px;
  font-size: 12px;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition: opacity .15s;
  z-index: 100;
}
.rail.collapsed .rail-item:hover::after { opacity: 1; }

.rail-new {
  background: var(--m-primary-soft);
  color: var(--m-primary-hover);
  border: 1px solid var(--m-primary);
  margin-bottom: 6px;
}
.rail-new :deep(.el-icon) { color: var(--m-primary); }
.rail-new:hover:not(:disabled) {
  background: var(--m-primary);
  color: var(--m-on-primary, #fff);
}
.rail-new:hover:not(:disabled) :deep(.el-icon) { color: var(--m-on-primary, #fff); }
.rail-new:disabled {
  background: var(--m-bg-soft);
  border-color: var(--m-border);
  color: var(--m-text-tertiary);
}
.rail-new:disabled :deep(.el-icon) { color: var(--m-text-tertiary); }
.rail.collapsed .rail-new { padding: 10px; justify-content: center; }
.rail.collapsed .rail-new span { display: none; }
.rail.collapsed .rail-new::after {
  content: '新对话';
  position: absolute; left: calc(100% + 10px); top: 50%; transform: translateY(-50%);
  background: var(--m-text); color: var(--m-bg);
  padding: 5px 10px; border-radius: 6px; font-size: 12px;
  white-space: nowrap; opacity: 0; pointer-events: none; transition: opacity .15s; z-index: 100;
}
.rail.collapsed .rail-new:hover::after { opacity: 1; }

.rail-suffix {
  margin-left: auto;
  font-size: 12px; font-weight: 400;
  color: var(--m-text-tertiary);
  max-width: 100px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

.rail-history {
  flex: 1; min-height: 0; overflow-y: auto; overflow-x: hidden;
  padding: 0 4px;
  display: flex; flex-direction: column; gap: 2px;
}
.rail-history::-webkit-scrollbar { width: 4px; }
.rail-history::-webkit-scrollbar-thumb { background: var(--m-border); border-radius: 4px; }
.rail-history::-webkit-scrollbar-track { background: transparent; }
.rail-history .conv-item { padding: 8px 10px; }

.rail-sub-row { display: flex; gap: 6px; padding: 4px 4px 4px; margin-top: 2px; }
.rail.collapsed .rail-sub-row { display: none; }
.rail-sub {
  flex: 1;
  display: flex; align-items: center; justify-content: center; gap: 6px;
  padding: 8px 8px;
  background: transparent; border: none;
  border-radius: var(--m-radius);
  font-size: 12px; font-weight: 500; color: var(--m-text-secondary);
  cursor: pointer;
  transition: background .15s ease, color .15s ease;
}
.rail-sub:hover { background: var(--m-surface-variant); color: var(--m-text); }
.rail-sub.active { background: var(--m-primary-soft); color: var(--m-primary-hover); }
.rail-sub.active :deep(.el-icon) { color: var(--m-primary); }

/* ---------- Rail group (collapsible) ---------- */
.rail-group { margin-top: 4px; }
.rail-group-header {
  display: flex; align-items: center; gap: 14px;
  width: 100%; padding: 10px 16px;
  color: var(--m-text);
  background: transparent; border: none;
  border-radius: var(--m-radius-pill);
  font-size: 14px; font-weight: 500;
  cursor: pointer;
  transition: background .15s ease;
  position: relative;
  white-space: nowrap;
}
.rail-group-header:hover { background: var(--m-surface-variant); }
.rail.collapsed .rail-group-header {
  justify-content: center;
  padding: 10px;
}
.rail.collapsed .rail-group-header span,
.rail.collapsed .rail-group-header .rail-group-arrow { display: none; }
.rail.collapsed .rail-group-header::after {
  content: '系统管理';
  position: absolute; left: calc(100% + 10px); top: 50%; transform: translateY(-50%);
  background: var(--m-text); color: var(--m-bg);
  padding: 5px 10px; border-radius: 6px; font-size: 12px;
  white-space: nowrap; opacity: 0; pointer-events: none; transition: opacity .15s; z-index: 100;
}
.rail.collapsed .rail-group-header:hover::after { opacity: 1; }
.rail.collapsed .rail-group-body { display: none; }
.rail-group-arrow {
  margin-left: auto;
  transition: transform .2s ease;
}
.rail-group.open .rail-group-arrow { transform: rotate(180deg); }
.rail-group-body {
  display: flex; flex-direction: column; gap: 2px;
  padding-left: 8px;
}
.rail-item-sub {
  padding: 8px 16px;
  font-size: 13px;
}
.group-slide-enter-active,
.group-slide-leave-active {
  transition: all .2s ease;
  overflow: hidden;
}
.group-slide-enter-from,
.group-slide-leave-to {
  opacity: 0;
  max-height: 0;
}
.group-slide-enter-to,
.group-slide-leave-from {
  opacity: 1;
  max-height: 200px;
}

/* ---------- Sub panel ---------- */
.sub-panel {
  width: 300px; flex-shrink: 0;
  background: var(--m-surface);
  border-left: 1px solid var(--m-border);
  border-right: 1px solid var(--m-border);
  display: flex; flex-direction: column;
  animation: slideIn .18s ease;
  overflow: hidden;
}
.rail.collapsed ~ .sub-panel { display: none; }
@keyframes slideIn {
  from { transform: translateX(-8px); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}
.sub-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 16px 12px;
}
.sub-title { font-size: 14px; font-weight: 600; color: var(--m-text); }
.sub-close {
  background: transparent; border: none; cursor: pointer;
  color: var(--m-text-secondary);
  width: 28px; height: 28px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  transition: background .15s ease, color .15s ease;
}
.sub-close:hover { background: var(--m-surface-variant); color: var(--m-text); }

.sub-body { flex: 1; overflow-y: auto; overflow-x: hidden; padding: 0 8px 12px; }
.sub-body::-webkit-scrollbar { width: 4px; }
.sub-body::-webkit-scrollbar-thumb { background: var(--m-border); border-radius: 4px; }
.sub-body::-webkit-scrollbar-track { background: transparent; }
.empty-hint { padding: 24px; text-align: center; color: var(--m-text-tertiary); font-size: 13px; }

.conv-item {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 12px;
  border-radius: var(--m-radius);
  cursor: pointer;
  transition: background .15s ease;
}
.conv-item:hover { background: var(--m-surface-variant); }
.conv-item.active { background: var(--m-primary-soft); color: var(--m-primary-hover); }
.conv-item.active .conv-icon { color: var(--m-primary); }
.conv-icon { color: var(--m-text-secondary); flex-shrink: 0; }
.conv-title {
  flex: 1; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; font-size: 13px; font-weight: 500;
}
.conv-actions { display: none; gap: 8px; color: var(--m-text-secondary); }
.conv-actions :deep(.el-icon):hover { color: var(--m-primary); }
.conv-item:hover .conv-actions { display: flex; }

.agent-item {
  display: flex; align-items: flex-start; gap: 12px;
  padding: 12px;
  border-radius: var(--m-radius);
  cursor: pointer;
  transition: background .15s ease;
  margin-bottom: 4px;
}
.agent-item:hover { background: var(--m-surface-variant); }
.agent-item.active { background: var(--m-primary-soft); }
.agent-icon {
  width: 36px; height: 36px; border-radius: 10px;
  background: var(--m-bg-soft);
  border: 1px solid var(--m-border);
  color: var(--m-text-secondary);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  transition: color .15s ease, border-color .15s ease, background .15s ease;
}
.agent-item:hover .agent-icon { color: var(--m-text); }
.agent-item.active .agent-icon {
  color: var(--m-primary);
  background: var(--m-primary-soft);
  border-color: var(--m-primary);
}
.agent-meta { flex: 1; min-width: 0; }
.agent-row { display: flex; align-items: center; gap: 6px; }
.agent-name { font-size: 14px; font-weight: 500; color: var(--m-text); }
.agent-check { color: var(--m-primary); margin-left: auto; }
.agent-desc {
  margin-top: 4px;
  font-size: 12px; line-height: 1.5;
  color: var(--m-text-secondary);
  word-break: break-word;
  /* Clamp to 3 lines — longer descriptions truncate with … */
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.agent-caps {
  margin-top: 8px;
  display: flex; flex-direction: column; gap: 6px;
  font-size: 12px;
  min-width: 0;
}
.cap-row {
  display: flex; align-items: center; gap: 14px;
  min-width: 0;
}
.cap-row-model {
  /* keep model on a single line; .cap-value truncates with ellipsis */
  flex-wrap: nowrap;
}
.cap-row-tools {
  flex-wrap: wrap;
}
.cap-item {
  display: inline-flex; align-items: center; gap: 4px;
  color: var(--m-text-secondary);
  min-width: 0;
  max-width: 100%;
}
.cap-label { color: var(--m-text-tertiary); flex-shrink: 0; }
.cap-value {
  color: var(--m-text); font-weight: 500;
  /* truncate long model ids with … */
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}
.cap-link {
  display: inline-flex; align-items: center; gap: 4px;
  color: var(--m-primary);
  cursor: pointer;
  text-decoration: none;
}
.cap-link:hover { text-decoration: underline; }
.cap-link-sm { font-size: 11px; }

/* ---------- Capability popover content ---------- */
.pop-body {
  font-size: 13px;
  max-height: 60vh;
  overflow: auto;
  padding-right: 4px;
}
.pop-title {
  font-size: 12px; font-weight: 600;
  color: var(--m-text-secondary);
  text-transform: uppercase; letter-spacing: .06em;
  margin-bottom: 8px;
}
.pop-empty { color: var(--m-text-tertiary); font-size: 12px; padding: 4px 0; }
.pop-list { display: flex; flex-direction: column; gap: 10px; }
.pop-row {
  padding: 8px 10px;
  background: var(--m-bg-soft);
  border-radius: var(--m-radius);
}
.pop-row-head {
  display: flex; align-items: center; gap: 8px;
  font-size: 13px;
}
.pop-row-actions {
  margin-left: auto;
  display: inline-flex; align-items: center; gap: 8px;
}
.pop-name { font-weight: 500; color: var(--m-text); }
.pop-desc {
  margin-top: 4px;
  font-size: 12px; line-height: 1.5;
  color: var(--m-text-secondary);
  word-break: break-word;
}
.pop-desc.err { color: var(--m-danger, #d33); }
.mcp-tools {
  margin-top: 6px;
  display: flex; flex-direction: column; gap: 4px;
  max-height: 240px;
  overflow: auto;
  padding-right: 4px;
}
.mcp-tool { font-size: 12px; line-height: 1.5; }
.mcp-tool-name {
  background: var(--m-surface-variant);
  padding: 1px 6px; border-radius: 4px;
  font-family: 'Roboto Mono', monospace;
  font-size: 11.5px; color: var(--m-text);
}
.mcp-tool-desc { color: var(--m-text-secondary); margin-left: 4px; }

/* ---------- Main ---------- */
.main { flex: 1; display: flex; flex-direction: column; min-width: 0; background: var(--m-surface); overflow: hidden; }
.topbar {
  height: 56px;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 24px;
  background: var(--m-surface);
}
.topbar-left { display: flex; align-items: center; min-width: 0; }
.topbar-right { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.topbar-icon-btn {
  width: 32px; height: 32px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 50%;
  color: var(--m-text-secondary);
  text-decoration: none;
  transition: background .15s ease, color .15s ease;
}
.topbar-icon-btn:hover { background: var(--m-surface-variant); color: var(--m-text); }

/* Theme toggle — glass toggle switch */
.theme-btn {
  position: relative;
  width: 52px; height: 28px;
  display: flex; align-items: center;
  background: var(--m-bg-soft);
  border: 1px solid var(--m-border);
  border-radius: 14px;
  cursor: pointer;
  transition: background 0.3s, border-color 0.3s, box-shadow 0.3s;
  padding: 0;
  outline: none;
}
.theme-btn:hover {
  border-color: var(--m-primary);
  box-shadow: 0 0 0 3px var(--m-primary-soft);
}
.theme-btn-track {
  position: relative;
  width: 100%; height: 100%;
  display: flex; align-items: center;
  justify-content: space-between;
  padding: 0 6px;
}
.theme-icon {
  width: 14px; height: 14px;
  z-index: 1;
  transition: opacity 0.3s, color 0.3s;
}
.theme-icon.sun { color: #f59e0b; }
.theme-icon.moon { color: #818cf8; }
.theme-knob {
  position: absolute;
  top: 3px; left: 3px;
  width: 20px; height: 20px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 1px 3px rgba(0,0,0,0.15);
  transition: transform 0.35s cubic-bezier(.22,.61,.36,1), background 0.3s;
  z-index: 2;
}
.theme-knob.dark {
  transform: translateX(24px);
  background: #1e1e2e;
}

.agent-chip {
  display: inline-flex; align-items: center; gap: 10px;
  padding: 6px 12px 6px 6px;
  background: var(--m-bg-soft);
  border-radius: var(--m-radius-pill);
  cursor: pointer;
  transition: background .15s ease;
  max-width: 100%;
}
.agent-chip:hover { background: var(--m-surface-variant); }
.agent-chip-icon {
  width: 28px; height: 28px; border-radius: 8px;
  background: var(--m-surface);
  border: 1px solid var(--m-border);
  color: var(--m-primary);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.agent-chip-meta {
  display: flex; flex-direction: column; line-height: 1.15; min-width: 0;
}
.agent-chip-label {
  font-size: 10px; font-weight: 500;
  color: var(--m-text-tertiary);
  text-transform: uppercase; letter-spacing: .06em;
}
.agent-chip-name {
  font-size: 13px; font-weight: 600; color: var(--m-text);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  max-width: 240px;
}
.agent-chip-arrow { color: var(--m-text-tertiary); }

.user-chip {
  display:flex; align-items:center; gap: 10px;
  padding: 6px 10px 6px 6px;
  border-radius: var(--m-radius-pill);
  cursor: pointer;
  transition: background .15s ease;
}
.user-chip:hover { background: var(--m-surface-variant); }
.avatar {
  width: 32px; height: 32px; border-radius: 50%;
  background: var(--m-bg-soft);
  border: 1px solid var(--m-border);
  color: var(--m-text-secondary);
  display:flex; align-items:center; justify-content:center;
}
.user-meta { line-height: 1.1; }
.user-meta .name { font-size: 13px; font-weight: 500; }
.user-meta .role { font-size: 11px; color: var(--m-text-secondary); margin-top: 2px; }

.content { flex: 1; position: relative; overflow-y: auto; }

/* 响应式布局 */
@media (max-width: 768px) {
  .rail:not(.collapsed) { width: 56px; padding: 12px 8px; }
  .rail:not(.collapsed) .rail-item span,
  .rail:not(.collapsed) .rail-group-header span,
  .rail:not(.collapsed) .rail-group-header .rail-group-arrow,
  .rail:not(.collapsed) .rail-divider,
  .rail:not(.collapsed) .rail-sub-row { display: none; }
  .rail:not(.collapsed) .rail-item { justify-content: center; padding: 10px; }
  .rail:not(.collapsed) .rail-new span { display: none; }
  .rail:not(.collapsed) .rail-new { padding: 10px; justify-content: center; }
  .rail.collapsed .rail-item::after,
  .rail.collapsed .rail-new::after,
  .rail.collapsed .rail-group-header::after { display: none; }
  .rail-group-body { display: none !important; }
  .sub-panel { position: fixed; left: 56px; top: 0; bottom: 0; width: 280px; z-index: 100; border-radius: 0; }
  .main { margin-left: 56px; }
  .topbar { padding: 0 12px; }
  .agent-chip-name { max-width: 120px; }
}

/* ========== 删除确认弹窗 ========== */
.del-overlay {
  position: fixed; inset: 0; z-index: 9999;
  display: flex; align-items: center; justify-content: center;
  background: rgba(0,0,0,.35);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}
.del-dialog {
  width: 380px;
  background: var(--m-surface);
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0,0,0,.2);
  overflow: hidden;
  animation: del-in .25s cubic-bezier(.22,.61,.36,1);
}
@keyframes del-in {
  from { opacity: 0; transform: scale(.92) translateY(12px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}
.del-header {
  display: flex; align-items: center; gap: 12px;
  padding: 20px 24px 0;
}
.del-icon {
  width: 44px; height: 44px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  background: var(--m-danger-soft);
  color: var(--m-danger);
  flex-shrink: 0;
}
.del-title { font-size: 17px; font-weight: 600; color: var(--m-text); }
.del-body { padding: 16px 24px; font-size: 14px; color: var(--m-text-secondary); }
.del-body p { margin: 0 0 8px; }
.del-target {
  display: inline-block;
  padding: 6px 12px;
  background: var(--m-bg-soft);
  border: 1px solid var(--m-border);
  border-radius: 8px;
  font-size: 13px; font-weight: 500; color: var(--m-text);
}
.del-footer { display: flex; justify-content: flex-end; gap: 8px; padding: 0 24px 20px; }

.del-fade-enter-active { transition: opacity .2s; }
.del-fade-leave-active { transition: opacity .15s; }
.del-fade-enter-from, .del-fade-leave-to { opacity: 0; }
</style>
