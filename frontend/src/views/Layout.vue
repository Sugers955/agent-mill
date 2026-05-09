<template>
  <div class="layout">
    <!-- Side rail -->
    <aside class="rail">
      <div class="rail-brand">
        <div class="brand-mark">
          <span class="dot dot-1" /><span class="dot dot-2" /><span class="dot dot-3" /><span class="dot dot-4" />
        </div>
        <div class="brand-name">Agent Forge</div>
      </div>

      <nav class="rail-nav">
        <button class="rail-item rail-new" :disabled="!chat.currentAgent" @click="onNewConv">
          <el-icon :size="20"><Plus /></el-icon>
          <span>新对话</span>
        </button>

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
              <span>智能体</span>
            </button>
          </div>

          <div class="rail-divider">管理</div>
          <router-link to="/admin/agents" class="rail-item" active-class="active">
            <el-icon :size="20"><Promotion /></el-icon><span>智能体</span>
          </router-link>
          <router-link to="/admin/packs" class="rail-item" active-class="active">
            <el-icon :size="20"><CollectionTag /></el-icon><span>Solution Pack</span>
          </router-link>
          <router-link to="/admin/skills" class="rail-item" active-class="active">
            <el-icon :size="20"><MagicStick /></el-icon><span>Skills</span>
          </router-link>
          <router-link to="/admin/mcp" class="rail-item" active-class="active">
            <el-icon :size="20"><Connection /></el-icon><span>MCP</span>
          </router-link>
          <router-link to="/tasks" class="rail-item" active-class="active">
            <el-icon :size="20"><AlarmClock /></el-icon><span>任务</span>
          </router-link>
          <router-link to="/admin/models" class="rail-item" active-class="active">
            <el-icon :size="20"><Cpu /></el-icon><span>模型</span>
          </router-link>
          <router-link to="/admin/logs" class="rail-item" active-class="active">
            <el-icon :size="20"><Document /></el-icon><span>日志</span>
          </router-link>
          <router-link v-if="auth.isAdmin" to="/admin/users" class="rail-item" active-class="active">
            <el-icon :size="20"><User /></el-icon><span>用户</span>
          </router-link>
          <router-link v-if="auth.isAdmin" to="/admin/departments" class="rail-item" active-class="active">
            <el-icon :size="20"><OfficeBuilding /></el-icon><span>部门</span>
          </router-link>
          <router-link v-if="auth.isAdmin" to="/admin/roles" class="rail-item" active-class="active">
            <el-icon :size="20"><UserFilled /></el-icon><span>角色</span>
          </router-link>
        </template>

        <!-- Regular user: agent toggle + inline history list -->
        <template v-else>
          <button
            :class="['rail-item', { active: subPanel === 'agent' }]"
            @click="togglePanel('agent')"
          >
            <el-icon :size="20"><Promotion /></el-icon>
            <span>智能体</span>
            <span v-if="chat.currentAgent" class="rail-suffix">{{ chat.currentAgent.name }}</span>
          </button>

          <router-link to="/tasks" class="rail-item" active-class="active">
            <el-icon :size="20"><AlarmClock /></el-icon><span>任务</span>
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
      </nav>
    </aside>

    <!-- Sub panel: slides next to the rail (managers see both, regular users only agent) -->
    <aside v-if="subPanel" class="sub-panel">
      <div class="sub-head">
        <span class="sub-title">{{ subPanel === 'history' ? '对话历史' : '智能体' }}</span>
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
        <div v-if="!chat.agents.length" class="empty-hint">暂无可用智能体</div>
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
            <div class="agent-desc">{{ a.description || a.code || '暂无介绍' }}</div>

            <div class="agent-caps" @click.stop>
              <!-- Model -->
              <span class="cap-item">
                <el-icon :size="13"><Cpu /></el-icon>
                <span class="cap-label">模型:</span>
                <span class="cap-value">{{ capModel(a.id) }}</span>
              </span>

              <!-- Skills popover -->
              <el-popover
                placement="right-start"
                :width="320"
                trigger="click"
                @before-enter="ensureCaps(a.id)"
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
                @before-enter="ensureCaps(a.id)"
              >
                <template #reference>
                  <a class="cap-link" @click.stop>
                    <el-icon :size="13"><Connection /></el-icon>
                    MCP ({{ a.mcp_ids?.length || 0 }})
                  </a>
                </template>
                <div class="pop-body">
                  <div class="pop-title">MCP 工具 ({{ a.mcp_ids?.length || 0 }})</div>
                  <div v-if="capsLoading[a.id]" class="pop-empty">加载中…</div>
                  <div v-else-if="!caps[a.id]?.mcps?.length" class="pop-empty">未挂载 MCP</div>
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
                        <div v-if="!mcpTools[mcpKey(a.id, m.id)].length" class="pop-desc">该 MCP 没有可用工具</div>
                        <div v-for="t in mcpTools[mcpKey(a.id, m.id)]" :key="t.name" class="mcp-tool">
                          <code class="mcp-tool-name">{{ t.name }}</code>
                          <span v-if="t.description" class="mcp-tool-desc">— {{ t.description }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </el-popover>
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
              <span class="agent-chip-label">当前智能体</span>
              <span class="agent-chip-name">{{ chat.currentAgent.name }}</span>
            </div>
            <el-icon class="agent-chip-arrow"><ArrowDown /></el-icon>
          </div>
        </div>
        <div class="topbar-right">
          <NotificationBell />
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
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
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

// per-agent capability cache (model + skills + mcps), populated lazily on popover open
const caps = reactive<Record<number, any>>({})
const capsLoading = reactive<Record<number, boolean>>({})
// per-(agent,mcp) tool cache, populated only when user clicks "查看工具"
const mcpTools = reactive<Record<string, any[]>>({})
const mcpToolsLoading = reactive<Record<string, boolean>>({})
const mcpToolsError = reactive<Record<string, string>>({})
const mcpToolsExpanded = reactive<Record<string, boolean>>({})
const mcpKey = (aid: number, mid: number) => `${aid}:${mid}`

async function ensureCaps(agentId: number) {
  if (caps[agentId] || capsLoading[agentId]) return
  capsLoading[agentId] = true
  try {
    caps[agentId] = await api.agentCapabilities(agentId)
  } catch {
    caps[agentId] = { model: null, skills: [], mcps: [] }
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
  if (!chat.currentAgent) return
  await chat.newConv()
  if (router.currentRoute.value.path !== '/chat') router.push('/chat')
}

async function onPickConv(c: any) {
  await chat.selectConv(c)
  if (router.currentRoute.value.path !== '/chat') router.push('/chat')
}

async function onRename(c: any) {
  try {
    const { value } = await ElMessageBox.prompt('新标题', '重命名', { inputValue: c.title })
    await chat.renameConv(c, value)
  } catch {}
}

async function onDelete(c: any) {
  try {
    await ElMessageBox.confirm('确定删除该对话?', '确认', { type: 'warning' })
    await chat.deleteConv(c)
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
  if (router.currentRoute.value.path !== '/chat') router.push('/chat')
}

function onLogout() {
  auth.logout()
  router.push('/login')
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
.layout { display: flex; height: 100vh; background: var(--m-bg); }

/* ---------- Side rail ---------- */
.rail {
  width: 240px; flex-shrink: 0;
  background: var(--m-bg-soft);
  padding: 20px 12px;
  display: flex; flex-direction: column;
}
.rail-brand { display:flex; align-items:center; gap: 10px; padding: 0 12px 24px; }
.brand-mark { display:grid; grid-template-columns: 1fr 1fr; gap: 3px; width: 22px; height: 22px; }
.dot { border-radius: 50%; }
.dot-1 { background:#4285f4 } .dot-2 { background:#ea4335 }
.dot-3 { background:#fbbc04 } .dot-4 { background:#34a853 }
.brand-name { font-size: 17px; font-weight: 600; letter-spacing: -0.01em; }

.rail-nav { display:flex; flex-direction: column; gap: 2px; min-height: 0; flex: 1; }
.rail-divider {
  font-size: 11px; font-weight: 600; color: var(--m-text-tertiary);
  letter-spacing: .08em; text-transform: uppercase;
  padding: 18px 16px 6px;
}
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
}
.rail-item:hover:not(:disabled) { background: var(--m-surface-variant); }
.rail-item:disabled { color: var(--m-text-tertiary); cursor: not-allowed; }
.rail-item.active { background: var(--m-primary-soft); color: var(--m-primary-hover); }
.rail-item.active :deep(.el-icon) { color: var(--m-primary); }

.rail-new {
  background: var(--m-primary-soft);
  color: var(--m-primary-hover);
  border: 1px solid var(--m-primary);
  margin-bottom: 6px;
}
.rail-new :deep(.el-icon) { color: var(--m-primary); }
.rail-new:hover:not(:disabled) {
  background: var(--m-primary);
  color: #fff;
}
.rail-new:hover:not(:disabled) :deep(.el-icon) { color: #fff; }
.rail-new:disabled {
  background: var(--m-bg-soft);
  border-color: var(--m-border);
  color: var(--m-text-tertiary);
}
.rail-new:disabled :deep(.el-icon) { color: var(--m-text-tertiary); }

.rail-suffix {
  margin-left: auto;
  font-size: 12px; font-weight: 400;
  color: var(--m-text-tertiary);
  max-width: 100px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

.rail-history {
  flex: 1; min-height: 0; overflow: auto;
  padding: 0 4px;
  display: flex; flex-direction: column; gap: 2px;
}
.rail-history .conv-item { padding: 8px 10px; }

.rail-sub-row { display: flex; gap: 6px; padding: 4px 4px 4px; margin-top: 2px; }
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

/* ---------- Sub panel ---------- */
.sub-panel {
  width: 300px; flex-shrink: 0;
  background: var(--m-surface);
  border-left: 1px solid var(--m-border);
  border-right: 1px solid var(--m-border);
  display: flex; flex-direction: column;
  animation: slideIn .18s ease;
}
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

.sub-body { flex: 1; overflow: auto; padding: 0 8px 12px; }
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
}

.agent-caps {
  margin-top: 8px;
  display: flex; flex-wrap: wrap; align-items: center; gap: 4px 12px;
  font-size: 12px;
}
.cap-item {
  display: inline-flex; align-items: center; gap: 4px;
  color: var(--m-text-secondary);
}
.cap-label { color: var(--m-text-tertiary); }
.cap-value { color: var(--m-text); font-weight: 500; }
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
.main { flex: 1; display: flex; flex-direction: column; min-width: 0; background: var(--m-surface); }
.topbar {
  height: 56px;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 24px;
  background: var(--m-surface);
}
.topbar-left { display: flex; align-items: center; min-width: 0; }
.topbar-right { display: flex; align-items: center; gap: 4px; flex-shrink: 0; }

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

.content { flex: 1; overflow: auto; }
</style>
