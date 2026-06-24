<template>
  <div class="page agents-page">
    <div class="page-head">
      <span class="page-title">数字员工矩阵</span>
      <el-button type="primary" @click="openCreate">
        <el-icon><Plus /></el-icon>
        招募数字员工
      </el-button>
    </div>

    <!-- 卡片网格 -->
    <div class="agents-grid">
      <div
        v-for="agent in rows"
        :key="agent.id"
        class="agent-card"
        :class="{ 'is-default': agent.is_default, 'is-disabled': !agent.enabled }"
      >
        <!-- 卡片内容 -->
        <div class="card-content">
          <!-- 头像区域 -->
          <div class="avatar-area" @click="openEdit(agent)">
            <div class="agent-avatar" :style="getAvatarStyle(agent)">
              <img v-if="agent.icon_url" :src="agent.icon_url" alt="" class="avatar-img" />
              <span v-else class="avatar-text">{{ getInitials(agent.name) }}</span>
            </div>
            <!-- 在线状态 -->
            <span class="status-dot" :class="{ online: agent.enabled }"></span>
          </div>

          <!-- 信息区域 -->
          <div class="info-area" @click="openEdit(agent)">
            <h3 class="agent-name">{{ agent.name }}</h3>
            <p class="agent-code">{{ agent.code }}</p>
            <p class="agent-desc">{{ agent.description || '暂无描述' }}</p>
          </div>

          <!-- 标签区域 -->
          <div class="tags-area">
            <span v-if="agent.is_default" class="tag tag-primary">默认</span>
            <span class="tag tag-model">{{ modelLabel(agent.default_model_id) }}</span>
            <span class="tag tag-effort" :class="agent.effort">{{ getEffortLabel(agent.effort) }}</span>
          </div>

          <!-- 操作按钮 -->
          <div class="action-area">
            <el-button size="small" @click="startChat(agent)">
              <el-icon><ChatDotRound /></el-icon>
              与 TA 对话
            </el-button>
            <el-dropdown trigger="click" @command="handleCommand($event, agent)">
              <el-button size="small" text>
                <el-icon><MoreFilled /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="edit">编辑</el-dropdown-item>
                  <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
      </div>

      <!-- 新建卡片 -->
      <div class="agent-card add-card" @click="openCreate">
        <div class="add-content">
          <el-icon class="add-icon"><Plus /></el-icon>
          <span class="add-text">招募数字员工</span>
        </div>
      </div>
    </div>

    <!-- 编辑弹窗 -->
    <el-dialog v-model="visible" :title="editing ? '编辑数字员工' : '招募数字员工'" width="1000px" top="3vh" class="agent-dialog" destroy-on-close>
      <!-- 顶部操作栏 -->
      <div class="dlg-topbar">
        <div class="dlg-title">{{ editing ? '编辑' : '创建' }}数字员工 — <strong>{{ form.name || '未命名' }}</strong></div>
        <div class="dlg-actions">
          <el-button size="small" @click="visible = false">取消</el-button>
          <el-button size="small" @click="onDebug">在线调试</el-button>
          <el-button size="small" type="primary" @click="onSubmit">发布生效</el-button>
          <el-button v-if="editing" size="small" type="danger" plain @click="onDelete(editing)">删除</el-button>
        </div>
      </div>

      <el-tabs v-model="activeTab" class="dlg-tabs">
        <!-- Tab1 基础信息 -->
        <el-tab-pane label="基础信息" name="base">
          <div class="tb-section">
            <div class="tb-title">基础资料</div>
            <div class="tb-row">
              <span class="tb-label">智能体头像</span>
              <div class="tb-input">
                <div class="avatar-group">
                  <div class="av-preview" :style="getAvatarStyle(form)">
                    <img v-if="form.icon_url" :src="form.icon_url" class="av-img" />
                    <span v-else class="av-txt">{{ getInitials(form.name || '') }}</span>
                  </div>
                  <el-upload :show-file-list="false" :before-upload="beforeIconUpload" :on-success="onIconUploadSuccess" :action="`/api/admin/agents/${editing?.id || 'new'}/icon`" accept="image/*">
                    <el-button size="small" type="primary" :disabled="!editing">上传图标</el-button>
                  </el-upload>
                  <span class="tb-tip">支持 JPG/PNG，建议 128x128px</span>
                </div>
              </div>
            </div>
            <div class="tb-row">
              <span class="tb-label">唯一编码</span>
              <div class="tb-input">
                <el-input v-model="form.code" :disabled="!!editing" placeholder="创建后不可修改" />
              </div>
            </div>
            <div class="tb-row">
              <span class="tb-label">智能体名称</span>
              <div class="tb-input">
                <el-input v-model="form.name" placeholder="输入智能体名称" />
              </div>
            </div>
            <div class="tb-row">
              <span class="tb-label">业务描述</span>
              <div class="tb-input">
                <el-input v-model="form.description" type="textarea" :rows="3" placeholder="对外展示简介" />
              </div>
            </div>
            <div class="tb-row">
              <span class="tb-label">运行状态</span>
              <div class="tb-input">
                <el-switch v-model="form.enabled" :active-text="form.enabled ? '启用' : '停用'" />
              </div>
            </div>
            <div class="tb-row">
              <span class="tb-label">设为默认</span>
              <div class="tb-input">
                <el-switch v-model="form.is_default" />
              </div>
            </div>
          </div>
        </el-tab-pane>

        <!-- Tab2 角色 & Prompt -->
        <el-tab-pane label="角色 &amp; Prompt" name="prompt">
          <div class="tb-section prompt-section">
            <div class="tb-title">1. 角色人设（必填）</div>
            <el-input v-model="form.system_prompt" type="textarea" :rows="8" placeholder="定义智能体身份、岗位职责、服务对象" />
          </div>
          <div class="tb-section prompt-section">
            <div class="tb-title">2. 输出规范 &amp; 约束规则</div>
            <el-input v-model="form.constraints" type="textarea" :rows="8" placeholder="定义输出格式、合规限制、语气要求" />
            <div class="tb-tip" style="margin-top:6px">可选：一键加载行业模板</div>
          </div>
        </el-tab-pane>

        <!-- Tab3 模型算力 -->
        <el-tab-pane label="模型算力" name="model">
          <div class="tb-section">
            <div class="tb-title">默认大模型</div>
            <el-select v-model="form.default_model_id" clearable style="width:100%">
              <el-option v-for="m in models" :key="m.id" :label="`${m.code}（${m.name}）`" :value="m.id" />
            </el-select>
          </div>
          <div class="tb-section">
            <div class="tb-title">算力强度 <span class="tb-tip" style="margin-left:6px">原「努力程度」</span></div>
            <div class="effort-slider">
              <el-slider v-model="effortValue" :min="1" :max="5" :step="1" show-stops />
              <div class="effort-labels">
                <span :class="{ a: effortValue === 1 }">轻量</span>
                <span :class="{ a: effortValue === 2 }">均衡</span>
                <span :class="{ a: effortValue === 3 }">深度</span>
                <span :class="{ a: effortValue === 4 }">扩展</span>
                <span :class="{ a: effortValue === 5 }">极限</span>
              </div>
              <div class="effort-sub">
                <span>低开销</span>
                <span class="a" v-if="effortValue <= 2">推荐</span>
                <span class="a" v-else-if="effortValue === 3">推荐</span>
                <span>高精度</span>
              </div>
            </div>
          </div>
          <div class="tb-section">
            <div class="tb-title">高级参数</div>
            <el-collapse>
              <el-collapse-item title="展开高级设置" name="adv">
                <div class="tb-row">
                  <span class="tb-label">Temperature</span>
                  <div class="tb-input"><el-input-number v-model="form.temperature" :min="0" :max="2" :step="0.1" size="small" /></div>
                </div>
                <div class="tb-row">
                  <span class="tb-label">最大输出 Token</span>
                  <div class="tb-input"><el-input-number v-model="form.max_tokens" :min="256" :step="256" size="small" /></div>
                </div>
                <div class="tb-row">
                  <span class="tb-label">最大对话轮次</span>
                  <div class="tb-input"><el-input-number v-model="form.max_turns" :min="1" :max="50" size="small" /></div>
                </div>
              </el-collapse-item>
            </el-collapse>
          </div>
        </el-tab-pane>

        <!-- Tab4 知识库 & 技能 -->
        <el-tab-pane label="知识库 &amp; 技能" name="skill">
          <div class="tb-section">
            <div class="tb-title">关联知识库（多选绑定）</div>
            <el-select v-model="form.kb_ids" multiple style="width:100%">
              <el-option v-for="k in knowledgeBases" :key="k.id" :label="k.name" :value="k.id" />
            </el-select>
            <div class="tb-tip">绑定后智能体自动引用知识库做合规校验</div>
          </div>
          <div class="tb-section">
            <div class="tb-title">挂载工具技能</div>
            <div class="skill-tags">
              <el-tag v-for="sid in form.skill_ids" :key="sid" closable @close="removeSkill(sid)" style="margin:3px">
                {{ skillName(sid) }}
              </el-tag>
            </div>
            <el-select v-model="newSkillId" placeholder="从技能市场添加…" filterable style="width:100%;margin-top:8px" @change="addSkill">
              <el-option v-for="s in availableSkills" :key="s.id" :label="s.name" :value="s.id">
                <div style="display:flex;justify-content:space-between;align-items:center">
                  <span>{{ s.name }}</span>
                  <el-tag size="small" type="info">{{ s.type || '通用' }}</el-tag>
                </div>
              </el-option>
            </el-select>
            <div class="skill-quick" v-if="availableSkills.length">
              <span class="tb-tip">快速添加：</span>
              <button v-for="s in availableSkills.slice(0, 6)" :key="s.id" class="skill-chip" @click="addSkill(s.id)">{{ s.name }}</button>
            </div>
          </div>
          <div class="tb-section">
            <div class="tb-title">挂载连接器 (MCP)</div>
            <el-select v-model="form.mcp_ids" multiple style="width:100%">
              <el-option v-for="m in mcps" :key="m.id" :label="m.name" :value="m.id" />
            </el-select>
          </div>
        </el-tab-pane>
      </el-tabs>

      <!-- 调试弹窗 -->
      <el-dialog v-model="debugVisible" :title="`在线调试 — ${form.name || '智能体'} 实时效果预览`" width="800px" top="5vh" append-to-body class="debug-dialog">
        <div class="debug-body" ref="debugBodyRef">
          <div v-for="(msg, i) in debugMessages" :key="i" :class="['db-msg', msg.role]">
            <div v-if="msg.role === 'assistant'" class="db-name">{{ form.name || '智能体' }}</div>
            <div class="db-text" v-html="msg.text"></div>
          </div>
          <div v-if="debugTyping" class="db-msg assistant">
            <div class="db-name">{{ form.name || '智能体' }}</div>
            <div class="db-typing"><span /><span /><span /></div>
          </div>
        </div>
        <div class="debug-footer">
          <el-input v-model="debugInput" placeholder="输入测试内容…" @keydown.enter="sendDebug" />
          <el-button type="primary" :disabled="!debugInput.trim() || debugTyping" @click="sendDebug">发送</el-button>
        </div>
      </el-dialog>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'
import { agentGradient } from '@/utils/agent-colors'

const router = useRouter()
const rows = ref<any[]>([])
const models = ref<any[]>([])
const skills = ref<any[]>([])
const mcps = ref<any[]>([])
const knowledgeBases = ref<any[]>([])
const visible = ref(false)
const editing = ref<any | null>(null)
const form = reactive<any>(emptyForm())
const activeTab = ref('base')
const debugVisible = ref(false)
const debugInput = ref('')
const debugTyping = ref(false)
const debugMessages = ref<Array<{ role: string; text: string }>>([])
const debugBodyRef = ref<HTMLElement | null>(null)
const newSkillId = ref<number | null>(null)
const effortValue = ref(2)

const effortMap: Record<number, string> = { 1: 'low', 2: 'medium', 3: 'high', 4: 'xhigh', 5: 'max' }

const availableSkills = computed(() => skills.value.filter(s => !form.skill_ids.includes(s.id)))

function skillName(id: number) { const s = skills.value.find(x => x.id === id); return s?.name || `#${id}` }
function addSkill(id: number) { if (id && !form.skill_ids.includes(id)) form.skill_ids.push(id); newSkillId.value = null }
function removeSkill(id: number) { form.skill_ids = form.skill_ids.filter((x: number) => x !== id) }

watch(effortValue, (v) => {
  form.effort = effortMap[v] || 'medium'
})

function getAvatarStyle(agent: any) {
  if (agent.icon_url) return {}
  return { background: agentGradient(agent) }
}

function getInitials(name: string) {
  if (!name) return '?'
  return name.charAt(0).toUpperCase()
}

function getEffortLabel(effort: string) {
  const map: Record<string, string> = {
    low: '轻量',
    medium: '平衡',
    high: '深入',
    xhigh: '扩展',
    max: '极限',
  }
  return map[effort] || effort
}

function emptyForm() {
  return {
    code: '', name: '', description: '', icon: '', icon_url: '', system_prompt: '',
    constraints: '', temperature: 0.3, max_tokens: 4096,
    default_model_id: null, fallback_model_id: null,
    upload_policy_json: {}, max_turns: 15, effort: 'medium',
    parsed_content_limit: null, kb_ids: [],
    enabled: true, is_default: false,
    skill_ids: [], mcp_ids: [], pack_ids: [], role_ids: [],
  }
}

async function load() {
  const [agentsRes, modelsRes, skillsRes, mcpsRes, kbRes] = await Promise.all([
    api.agents(), api.models(), api.skills(), api.mcps(),
    api.request('/api/admin/knowledge/bases'),
  ])
  rows.value = agentsRes.items || agentsRes
  models.value = modelsRes.items || modelsRes
  skills.value = skillsRes.items || skillsRes
  mcps.value = mcpsRes.items || mcpsRes
  knowledgeBases.value = kbRes || []
}
onMounted(load)

function modelLabel(id: number) {
  const m = models.value.find((x: any) => x.id === id)
  return m ? m.code : '未配置'
}

function openCreate() {
  editing.value = null
  Object.assign(form, emptyForm())
  effortValue.value = 2
  visible.value = true
}

function openEdit(row: any) {
  editing.value = row
  Object.assign(form, emptyForm(), JSON.parse(JSON.stringify(row)))
  if (!form.kb_ids) form.kb_ids = form.kb_id ? [form.kb_id] : []
  const revEffort = { low: 1, medium: 2, high: 3, xhigh: 4, max: 5 }
  effortValue.value = revEffort[form.effort as keyof typeof revEffort] || 2
  visible.value = true
  activeTab.value = 'base'
}

function startChat(agent: any) {
  router.push({ path: '/chat', query: { agent: agent.code } }).catch(() => {})
}

function handleCommand(cmd: string, agent: any) {
  if (cmd === 'edit') openEdit(agent)
  else if (cmd === 'delete') onDelete(agent)
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
  const payload = { ...form, kb_id: form.kb_ids?.[0] ?? null }
  delete payload.kb_ids
  if (editing.value) {
    await api.updateAgent(editing.value.id, payload)
  } else {
    await api.createAgent(payload)
  }
  visible.value = false
  ElMessage.success('保存成功')
  await load()
}

async function onDelete(row: any) {
  try {
    await ElMessageBox.confirm(`删除数字员工 ${row.name}？`, '确认', { type: 'warning' })
    await api.deleteAgent(row.id)
    await load()
  } catch {}
}

function onDebug() {
  debugVisible.value = true
  debugConvId.value = null
  const agentName = form.name || '智能体'
  const agentDesc = form.description || '企业智能助手'
  debugMessages.value = [
    { role: 'user', text: `你好，请介绍一下你的能力` },
    { role: 'assistant', text: `你好！我是 <b>${agentName}</b>，${agentDesc}。<br><br>请问有什么可以帮你的？` },
  ]
  nextTick(() => scrollDebug())
}

const debugConvId = ref<number | null>(null)

function scrollDebug() {
  nextTick(() => { if (debugBodyRef.value) debugBodyRef.value.scrollTop = debugBodyRef.value.scrollHeight })
}

async function sendDebug() {
  if (!debugInput.value.trim() || debugTyping.value) return
  const userText = debugInput.value
  debugMessages.value.push({ role: 'user', text: userText })
  debugInput.value = ''
  debugTyping.value = true
  scrollDebug()

  const agentId = editing.value?.id
  if (!agentId) {
    // 未保存时模拟回复
    setTimeout(() => {
      debugMessages.value.push({ role: 'assistant', text: `请先保存智能体后再进行在线调试。` })
      debugTyping.value = false
      scrollDebug()
    }, 500)
    return
  }

  try {
    let convId = debugConvId.value
    if (!convId) {
      const conv = await api.createConversation(agentId, `[调试] ${userText.slice(0, 30)}`)
      convId = conv.id
      debugConvId.value = convId
    }
    const token = localStorage.getItem('access_token')
    const resp = await fetch(`/api/conversations/${convId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ content: userText, file_ids: [] }),
    })
    if (!resp.ok || !resp.body) throw new Error(`HTTP ${resp.status}`)

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    let reply = ''
    const msgIdx = debugMessages.value.length
    debugMessages.value.push({ role: 'assistant', text: '' })

    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const lines = buf.split('\n\n')
      buf = lines.pop() || ''
      for (const line of lines) {
        if (!line.startsWith('data:')) continue
        try {
          const ev = JSON.parse(line.slice(5).trim())
          if (ev.type === 'text') {
            reply += ev.data.text || ''
            debugMessages.value[msgIdx] = { role: 'assistant', text: reply.replace(/\n/g, '<br>') }
            scrollDebug()
          }
        } catch {}
      }
    }
    if (!reply) {
      debugMessages.value[msgIdx] = { role: 'assistant', text: '（模型未返回有效内容，请检查模型配置和 API Key）' }
    }
  } catch (e: any) {
    debugMessages.value.push({ role: 'assistant', text: `请求失败：${e.message}。请检查网络连接和模型配置。` })
  } finally {
    debugTyping.value = false
    scrollDebug()
  }
}
</script>

<style scoped>
.agents-page {
  background: var(--m-bg);
  min-height: 100vh;
}

/* 卡片网格 */
.agents-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
}

/* 数字员工卡片 */
.agent-card {
  background: var(--m-surface);
  border: 1px solid var(--m-border);
  border-radius: 12px;
  transition: all 0.2s ease;
}

.agent-card:hover {
  border-color: var(--m-border-strong);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

/* 卡片内容 */
.card-content {
  padding: 20px;
}

/* 头像区域 */
.avatar-area {
  position: relative;
  width: fit-content;
  margin-bottom: 16px;
  cursor: pointer;
}

.agent-avatar {
  width: 64px;
  height: 64px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--m-primary);
  overflow: hidden;
}

.avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-text {
  font-size: 24px;
  font-weight: 600;
  color: var(--m-surface);
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}

/* 在线状态 */
.status-dot {
  position: absolute;
  bottom: 0;
  right: 0;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--m-border);
  border: 2px solid var(--m-surface);
}

.status-dot.online {
  background: var(--m-success);
}

/* 信息区域 */
.info-area {
  cursor: pointer;
  margin-bottom: 12px;
}

.agent-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--m-text);
  margin: 0 0 4px 0;
}

.agent-code {
  font-size: 12px;
  color: var(--m-text-tertiary);
  font-family: 'Roboto Mono', monospace;
  margin: 0 0 8px 0;
}

.agent-desc {
  font-size: 14px;
  color: var(--m-text-secondary);
  margin: 0;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 标签区域 */
.tags-area {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 16px;
}

.tag {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.tag-primary {
  background: var(--m-primary-soft);
  color: var(--m-primary);
}

.tag-model {
  background: var(--m-bg-soft);
  color: var(--m-text-secondary);
}

.tag-effort.low {
  background: rgba(34, 197, 94, 0.1);
  color: var(--m-success);
}

.tag-effort.medium {
  background: var(--m-primary-soft);
  color: var(--m-primary);
}

.tag-effort.high {
  background: rgba(217, 119, 6, 0.1);
  color: var(--m-warning);
}

/* 操作区域 */
.action-area {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-top: 16px;
  border-top: 1px solid var(--m-border);
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

.icon-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.icon-text {
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

/* 禁用状态 */
.is-disabled {
  opacity: 0.6;
}

.is-disabled .status-dot {
  background: var(--m-border);
}

@media (max-width: 768px) {
  .agents-grid {
    grid-template-columns: 1fr;
  }
  .page-head {
    flex-direction: column;
    gap: 12px;
    align-items: flex-start;
  }
}

/* ===== 编辑弹窗 ===== */
.agent-dialog :deep(.el-dialog__body) { padding: 0; }
.dlg-topbar { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; border-bottom: 1px solid var(--m-border); }
.dlg-title { font-size: 16px; font-weight: 500; color: var(--m-text); }
.dlg-actions { display: flex; gap: 6px; }
.dlg-tabs :deep(.el-tabs__header) { margin: 0; padding: 0 20px; border-bottom: 1px solid var(--m-border); }
.dlg-tabs :deep(.el-tabs__item) { font-size: 14px; font-weight: 500; padding: 12px 18px; height: auto; }
.dlg-tabs :deep(.el-tabs__content) { padding: 16px 20px; max-height: 68vh; overflow-y: auto; }
.dlg-tabs :deep(.el-textarea__inner) { min-height: 120px !important; font-size: 14px; line-height: 1.7; }
.prompt-section .el-textarea { min-height: 160px; }
.tb-section { background: var(--m-bg-soft); border-radius: 8px; padding: 16px; margin-bottom: 14px; }
.tb-title { font-size: 14px; font-weight: 600; color: var(--m-text); margin-bottom: 12px; display: flex; align-items: center; }
.tb-row { display: flex; margin-bottom: 14px; align-items: flex-start; }
.tb-row:last-child { margin-bottom: 0; }
.tb-label { width: 120px; padding-top: 8px; font-size: 13px; color: var(--m-text-secondary); flex-shrink: 0; }
.tb-input { flex: 1; min-width: 0; }
.tb-tip { font-size: 12px; color: var(--m-text-tertiary); margin-top: 4px; }
.avatar-group { display: flex; align-items: center; gap: 12px; }
.av-preview { width: 56px; height: 56px; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.av-img { width: 100%; height: 100%; border-radius: 50%; object-fit: cover; }
.av-txt { font-size: 22px; font-weight: 600; color: #fff; }
.effort-slider { padding: 4px 8px 0; }
.effort-labels { display: flex; justify-content: space-between; margin-top: -2px; font-size: 12px; color: var(--m-text-tertiary); }
.effort-labels span { flex: 1; text-align: center; }
.effort-labels span.a { color: var(--m-primary); font-weight: 600; }
.effort-sub { display: flex; justify-content: space-between; font-size: 11px; color: var(--m-text-tertiary); margin-top: 2px; }
.effort-sub span.a { color: var(--m-success); }
.skill-tags { display: flex; flex-wrap: wrap; gap: 4px; min-height: 32px; padding: 4px 0; }
.skill-quick { display: flex; align-items: center; gap: 6px; margin-top: 10px; flex-wrap: wrap; }
.skill-chip { padding: 3px 10px; font-size: 12px; border: 1px solid var(--m-border); border-radius: 4px; background: var(--m-surface); color: var(--m-text-secondary); cursor: pointer; }
.skill-chip:hover { border-color: var(--m-primary); color: var(--m-primary); }

/* 调试弹窗 */
.debug-dialog :deep(.el-dialog__body) { padding: 0; }
.debug-body { background: var(--m-bg); padding: 16px; height: 380px; overflow-y: auto; }
.db-msg { max-width: 80%; padding: 10px 14px; border-radius: 8px; margin-bottom: 12px; font-size: 14px; line-height: 1.6; }
.db-msg.user { margin-left: auto; background: var(--m-primary); color: #fff; }
.db-msg.assistant { background: var(--m-surface); border: 1px solid var(--m-border); }
.db-name { font-size: 11px; font-weight: 600; color: var(--m-text-secondary); margin-bottom: 4px; }
.db-text { word-break: break-word; }
.db-typing { display: flex; gap: 4px; padding: 4px 0; }
.db-typing span { width: 6px; height: 6px; border-radius: 50%; background: var(--m-text-tertiary); animation: db-dot 1.2s ease-in-out infinite; }
.db-typing span:nth-child(2) { animation-delay: .15s; }
.db-typing span:nth-child(3) { animation-delay: .3s; }
@keyframes db-dot { 0%,100% { opacity: .2; } 50% { opacity: .8; } }
.debug-footer { display: flex; gap: 8px; padding: 12px 16px; border-top: 1px solid var(--m-border); }
.debug-footer .el-input { flex: 1; }
</style>
