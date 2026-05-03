<template>
  <div class="layout">
    <!-- Side rail -->
    <aside class="rail">
      <div class="rail-brand">
        <div class="brand-mark">
          <span class="dot dot-1" /><span class="dot dot-2" /><span class="dot dot-3" /><span class="dot dot-4" />
        </div>
        <div class="brand-name">H3C Agent</div>
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
          <router-link v-if="auth.isAdmin" to="/admin/users" class="rail-item" active-class="active">
            <el-icon :size="20"><User /></el-icon><span>用户</span>
          </router-link>
          <router-link to="/admin/agents" class="rail-item" active-class="active">
            <el-icon :size="20"><Promotion /></el-icon><span>智能体</span>
          </router-link>
          <router-link to="/admin/skills" class="rail-item" active-class="active">
            <el-icon :size="20"><MagicStick /></el-icon><span>Skills</span>
          </router-link>
          <router-link to="/admin/mcp" class="rail-item" active-class="active">
            <el-icon :size="20"><Connection /></el-icon><span>MCP</span>
          </router-link>
          <router-link to="/admin/models" class="rail-item" active-class="active">
            <el-icon :size="20"><Cpu /></el-icon><span>模型</span>
          </router-link>
          <router-link to="/admin/logs" class="rail-item" active-class="active">
            <el-icon :size="20"><Document /></el-icon><span>日志</span>
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
          <div class="agent-icon">{{ (a.name || '?').slice(0, 1) }}</div>
          <div class="agent-meta">
            <div class="agent-row">
              <span class="agent-name">{{ a.name }}</span>
              <el-tag v-if="a.id === chat.defaultAgent?.id" size="small" effect="light" type="primary">默认</el-tag>
              <el-icon v-if="a.id === chat.currentAgent?.id" class="agent-check"><Check /></el-icon>
            </div>
            <div class="agent-desc">{{ a.description || a.code || '暂无介绍' }}</div>
          </div>
        </div>
      </div>
    </aside>

    <!-- Main -->
    <div class="main">
      <header class="topbar">
        <div></div>
        <el-dropdown trigger="click">
          <div class="user-chip">
            <div class="avatar">{{ initial }}</div>
            <div class="user-meta">
              <div class="name">{{ auth.user?.display_name || auth.user?.username }}</div>
              <div class="role">{{ auth.user?.role?.name }}</div>
            </div>
            <el-icon><ArrowDown /></el-icon>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="onLogout"><el-icon><SwitchButton /></el-icon>退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </header>
      <main class="content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useAuth } from '@/stores/auth'
import { useChat } from '@/stores/chat'

const router = useRouter()
const auth = useAuth()
const chat = useChat()

const subPanel = ref<'history' | 'agent' | null>(null)

const initial = computed(() => {
  const n = auth.user?.display_name || auth.user?.username || '?'
  return n.slice(0, 1).toUpperCase()
})

onMounted(() => {
  if (!chat.loaded) chat.loadInit()
})

function togglePanel(name: 'history' | 'agent') {
  if (!auth.canManage && name === 'history') return
  subPanel.value = subPanel.value === name ? null : name
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

function onPickAgent(a: any) {
  chat.selectAgent(a)
}

function onLogout() {
  auth.logout()
  router.push('/login')
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
  width: 36px; height: 36px; border-radius: 50%;
  background: linear-gradient(135deg, #4285f4, #34a853);
  color: #fff; font-weight: 600; font-size: 14px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
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

/* ---------- Main ---------- */
.main { flex: 1; display: flex; flex-direction: column; min-width: 0; background: var(--m-surface); }
.topbar {
  height: 56px;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 24px;
  background: var(--m-surface);
}

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
  background: linear-gradient(135deg, #4285f4 0%, #34a853 100%);
  color: #fff; font-weight: 600; font-size: 13px;
  display:flex; align-items:center; justify-content:center;
}
.user-meta { line-height: 1.1; }
.user-meta .name { font-size: 13px; font-weight: 500; }
.user-meta .role { font-size: 11px; color: var(--m-text-secondary); margin-top: 2px; }

.content { flex: 1; overflow: auto; }
</style>
