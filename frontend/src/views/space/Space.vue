<template>
  <div class="space-page">
    <div class="page-head">
      <h2 class="page-title">空间</h2>
      <div class="muted">仅你可见 · 共 {{ favs.total }} 条</div>
    </div>

    <div class="filters">
      <el-input
        v-model="q"
        placeholder="搜索问题 / 回答 / 备注"
        clearable
        class="filter-input"
        @keydown.enter="onFilter"
        @clear="onFilter"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-select
        v-model="filterAgentId"
        placeholder="按智能体筛选"
        clearable
        filterable
        class="filter-select"
        @change="onFilter"
      >
        <el-option v-for="a in agents" :key="a.id" :label="a.name" :value="a.id" />
      </el-select>
      <el-button type="primary" @click="onFilter">搜索</el-button>
      <el-button v-if="hasFilter" text type="primary" @click="clearFilters">清空</el-button>
    </div>

    <div v-loading="loading" class="fav-list">
      <div v-if="!favs.items.length && !loading" class="empty">
        <el-icon :size="40"><Star /></el-icon>
        <div class="empty-title">空间还是空的</div>
        <div class="empty-hint">在对话中点击 ⭐ 收藏 把有价值的问答存进来</div>
      </div>

      <div v-for="fav in favs.items" :key="fav.id" class="fav-card">
        <div class="card-head">
          <div class="head-meta">
            <el-tag v-if="fav.agent_name" size="small" effect="light" type="primary">
              <el-icon :size="11" style="vertical-align:-1px"><Promotion /></el-icon>
              {{ fav.agent_name }}
            </el-tag>
            <code v-if="fav.model_code" class="model-chip">{{ fav.model_code }}</code>
            <span class="muted time-text">{{ fmtTime(fav.created_at) }}</span>
          </div>
          <div class="head-actions">
            <el-tooltip v-if="fav.conversation_id" content="跳回原对话" placement="top">
              <el-button text circle size="small" @click="jumpBack(fav)">
                <el-icon :size="14"><ChatLineRound /></el-icon>
              </el-button>
            </el-tooltip>
            <el-tooltip content="取消收藏" placement="top">
              <el-button text circle size="small" @click="onRemove(fav)">
                <el-icon :size="14" class="del-ic"><Delete /></el-icon>
              </el-button>
            </el-tooltip>
          </div>
        </div>

        <div class="qa-text question" :title="fav.question_text">
          <span class="q-prefix">Q</span>
          <span class="q-text">{{ fav.question_text || '(空)' }}</span>
        </div>

        <div class="qa-block">
          <div class="qa-row">
            <div class="qa-label">回答</div>
            <button class="toggle-btn" @click="toggleExpand(fav.id)">
              <span>{{ expanded[fav.id] ? '收起' : '展开' }}</span>
              <el-icon :size="12">
                <ArrowUp v-if="expanded[fav.id]" />
                <ArrowDown v-else />
              </el-icon>
            </button>
          </div>
          <div v-if="expanded[fav.id]" class="qa-text answer-full">
            <template
              v-for="(seg, si) in parseSegments(fav.answer_text)"
              :key="seg.type === 'widget' ? seg.stableKey : `t-${fav.id}-${si}`"
            >
              <div v-if="seg.type === 'text'" class="md-body" v-html="md.render(seg.content)" />
              <WidgetRenderer
                v-else
                :widget-code="seg.widgetCode"
                :title="seg.title"
                :is-streaming="false"
              />
            </template>
            <div v-if="fav.files?.length" class="files-block">
              <FileCard
                v-for="(f, fi) in fav.files"
                :key="(f.output_path || f.name) + '-' + fi"
                :file="f"
                @preview="openPreview"
              />
            </div>
          </div>
          <div v-else class="qa-text answer-clip">
            <span>{{ clipText(plainAnswer(fav.answer_text), 140) }}</span>
            <span v-if="fav.files?.length" class="files-hint">
              <el-icon :size="11"><Paperclip /></el-icon>
              {{ fav.files.length }} 个文件
            </span>
          </div>
        </div>

        <div class="note-block">
          <div v-if="editingNote === fav.id" class="note-edit">
            <el-input
              v-model="noteDraft"
              type="textarea"
              :rows="2"
              maxlength="500"
              show-word-limit
              :ref="(el: any) => bindNoteRef(fav.id, el)"
              @blur="saveNote(fav)"
              @keydown.escape="cancelEditNote"
            />
          </div>
          <div v-else class="note-view" @click="startEditNote(fav)">
            <el-icon :size="13"><EditPen /></el-icon>
            <span v-if="fav.note" class="note-text">{{ fav.note }}</span>
            <span v-else class="note-placeholder">点击添加备注…</span>
          </div>
        </div>
      </div>
    </div>

    <div class="pager">
      <el-pagination
        background
        layout="total, sizes, prev, pager, next, jumper"
        :total="favs.total"
        :page-size="pageSize"
        :current-page="page"
        :page-sizes="[20, 50, 100]"
        @current-change="onPageChange"
        @size-change="onSizeChange"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import MarkdownIt from 'markdown-it'
import { api } from '@/api'
import { useChat } from '@/stores/chat'
import { useSpace } from '@/stores/space'
import { parseMessageContent } from '@/lib/widget-parser'
import WidgetRenderer from '@/components/WidgetRenderer.vue'
import FileCard from '@/components/FileCard.vue'

const md = new MarkdownIt({ breaks: true, linkify: true })
const router = useRouter()
const chat = useChat()
const space = useSpace()

const favs = ref<{ items: any[]; total: number }>({ items: [], total: 0 })
const agents = ref<any[]>([])
const loading = ref(false)

const q = ref('')
const filterAgentId = ref<number | null>(null)
const page = ref(1)
const pageSize = ref(20)

const expanded = reactive<Record<number, boolean>>({})
const editingNote = ref<number | null>(null)
const noteDraft = ref('')
const noteRefs = new Map<number, any>()

const hasFilter = computed(() => !!q.value || filterAgentId.value != null)

async function load() {
  loading.value = true
  try {
    const offset = (page.value - 1) * pageSize.value
    favs.value = await api.favorites({
      q: q.value.trim() || undefined,
      agent_id: filterAgentId.value ?? undefined,
      limit: pageSize.value,
      offset,
    })
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  // load agents for the filter dropdown (best-effort)
  try { agents.value = await api.myAgents() } catch {}
  await load()
})

function onFilter() { page.value = 1; load() }
function clearFilters() { q.value = ''; filterAgentId.value = null; page.value = 1; load() }
function onPageChange(p: number) { page.value = p; load() }
function onSizeChange(s: number) { pageSize.value = s; page.value = 1; load() }

function toggleExpand(id: number) { expanded[id] = !expanded[id] }
function clipText(s: string, n: number) { return (s || '').length > n ? s.slice(0, n) + '…' : (s || '') }

// Strip show-widget code fences (and raw <svg> blobs) for the collapsed preview —
// we don't want a wall of escaped SVG/HTML showing in the card summary.
function plainAnswer(s: string): string {
  if (!s) return ''
  return s
    .replace(/```show-widget[\s\S]*?```/g, '[图表]')
    .replace(/<svg[\s\S]*?<\/svg>/gi, '[图表]')
    .replace(/```[\s\S]*?```/g, '[代码]')
    .replace(/\s+/g, ' ')
    .trim()
}

function parseSegments(text: string) {
  return parseMessageContent(text || '', false)
}

// FileCard `@preview` callback. Space.vue doesn't host a split preview panel,
// so we just open the file in a new tab — FileCard has already refreshed the
// token (via output_path) before emitting, so this URL is fresh.
function openPreview(f: any) {
  if (!f) return
  const token = localStorage.getItem('access_token') || ''
  const url = f.download_url || ''
  if (!url) return
  const sep = url.includes('?') ? '&' : '?'
  const full = token ? `${url}${sep}t=${encodeURIComponent(token)}` : url
  window.open(full, '_blank')
}

function bindNoteRef(id: number, el: any) {
  if (el) noteRefs.set(id, el)
}
function startEditNote(fav: any) {
  editingNote.value = fav.id
  noteDraft.value = fav.note || ''
  nextTick(() => {
    const r = noteRefs.get(fav.id)
    r?.focus?.()
  })
}
function cancelEditNote() {
  editingNote.value = null
  noteDraft.value = ''
}
async function saveNote(fav: any) {
  if (editingNote.value !== fav.id) return
  const next = noteDraft.value.trim()
  if (next === (fav.note || '')) { editingNote.value = null; return }
  try {
    const updated = await api.updateFavorite(fav.id, next || null)
    Object.assign(fav, updated)
    ElMessage.success('备注已保存')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    editingNote.value = null
  }
}

async function onRemove(fav: any) {
  try {
    await ElMessageBox.confirm(`确定取消收藏吗?`, '确认', { type: 'warning' })
  } catch { return }
  try {
    await api.deleteFavorite(fav.id)
    // Drop locally + reload counters
    favs.value.items = favs.value.items.filter((x: any) => x.id !== fav.id)
    favs.value.total = Math.max(0, favs.value.total - 1)
    if (fav.message_id && space.favByMessage[fav.message_id]) {
      delete space.favByMessage[fav.message_id]
    }
    ElMessage.success('已取消收藏')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '取消失败')
  }
}

async function jumpBack(fav: any) {
  if (!fav.conversation_id) return
  // Find the conv in chat store; if not yet loaded, fetch the list first.
  let conv = chat.convs.find((x: any) => x.id === fav.conversation_id)
  if (!conv) {
    if (!chat.loaded) await chat.loadInit()
    conv = chat.convs.find((x: any) => x.id === fav.conversation_id)
  }
  if (!conv) {
    ElMessage.warning('原对话已被删除')
    return
  }
  await chat.selectConv(conv)
  const target = fav.message_id ? String(fav.message_id) : ''
  router.push(target ? `/chat?msg=${target}` : '/chat')
}

function fmtTime(s: string) {
  if (!s) return ''
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return s
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
</script>

<style scoped>
.space-page { padding: 24px; max-width: 920px; margin: 0 auto; }
.page-head { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 16px; }
.page-title { margin: 0; font-size: 22px; font-weight: 600; letter-spacing: -0.01em; }
.muted { color: var(--m-text-tertiary); font-size: 12px; }

.filters {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 16px; flex-wrap: wrap;
}
.filter-input { width: 280px; }
.filter-select { width: 200px; }

.fav-list { display: flex; flex-direction: column; gap: 12px; min-height: 200px; }

.empty {
  display: flex; flex-direction: column; align-items: center;
  gap: 8px; padding: 64px 16px;
  color: var(--m-text-tertiary);
}
.empty-title { font-size: 15px; color: var(--m-text-secondary); font-weight: 500; }
.empty-hint { font-size: 13px; }

.fav-card {
  background: var(--m-surface);
  border: 1px solid var(--m-border);
  border-radius: var(--m-radius);
  padding: 10px 14px;
  display: flex; flex-direction: column; gap: 6px;
  transition: border-color .15s, box-shadow .15s;
}
.fav-card:hover { border-color: var(--m-border-strong); box-shadow: var(--m-shadow-1); }

.card-head { display: flex; align-items: center; justify-content: space-between; min-height: 24px; }
.head-meta { display: inline-flex; align-items: center; gap: 6px; flex-wrap: wrap; min-width: 0; }
.model-chip {
  font-family: 'Roboto Mono', monospace; font-size: 11px;
  background: var(--m-surface-variant);
  padding: 1px 6px; border-radius: 4px;
  color: var(--m-text-secondary);
}
.time-text { font-size: 11px; }
.head-actions { display: inline-flex; align-items: center; gap: 2px; flex-shrink: 0; }
.head-actions :deep(.el-button + .el-button) { margin-left: 0; }
.del-ic { color: var(--m-danger, #d33); }

.qa-block { display: flex; flex-direction: column; gap: 4px; }
.qa-row { display: flex; align-items: center; justify-content: space-between; }
.toggle-btn {
  display: inline-flex; align-items: center; gap: 3px;
  border: none;
  background: transparent;
  color: var(--m-text-tertiary);
  font-size: 12px;
  padding: 2px 6px;
  border-radius: 4px;
  cursor: pointer;
  line-height: 1.4;
  transition: color .15s ease, background .15s ease;
}
.toggle-btn:hover { color: var(--m-text); background: var(--m-surface-variant); }
.qa-label {
  font-size: 11px; font-weight: 600;
  color: var(--m-text-tertiary);
  text-transform: uppercase; letter-spacing: .08em;
}
.qa-text { font-size: 13.5px; line-height: 1.55; color: var(--m-text); word-break: break-word; }
.qa-text.question {
  background: var(--m-primary-soft);
  padding: 6px 10px; border-radius: 6px;
  font-weight: 500;
  font-size: 13.5px; line-height: 1.5;
  display: flex; align-items: center; gap: 6px;
  min-width: 0;
}
.qa-text.question .q-prefix {
  font-weight: 700; color: var(--m-primary);
  font-family: 'Inter', sans-serif; font-size: 11px;
  background: rgba(255,255,255,.6); padding: 0 5px;
  border-radius: 3px; flex-shrink: 0;
  line-height: 18px;
}
.qa-text.question .q-text {
  flex: 1; min-width: 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.qa-text.answer-clip {
  color: var(--m-text-secondary);
  display: flex; align-items: center; gap: 8px;
  flex-wrap: wrap;
}
.qa-text.answer-clip > span:first-child {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  flex: 1; min-width: 0;
}
.files-hint {
  display: inline-flex; align-items: center; gap: 3px;
  font-size: 11px; color: var(--m-primary);
  background: var(--m-primary-soft);
  padding: 2px 8px; border-radius: 999px;
  flex-shrink: 0;
}
.files-block { display: flex; flex-direction: column; gap: 6px; margin-top: 4px; }
.qa-text.answer-full {
  background: var(--m-bg-soft);
  padding: 10px 12px; border-radius: var(--m-radius);
  display: flex; flex-direction: column; gap: 8px;
}
.qa-text.answer-full .md-body :deep(p) { margin: 4px 0; }
.qa-text.answer-full .md-body :deep(pre) {
  background: #202124; color: #e8eaed;
  padding: 12px; border-radius: var(--m-radius);
  overflow: auto; font-size: 12.5px;
}
.qa-text.answer-full .md-body :deep(code) { font-family: 'Roboto Mono', monospace; }
.qa-text.answer-full .md-body :deep(:not(pre) > code) {
  background: var(--m-surface-variant); padding: 1px 6px; border-radius: 4px; font-size: 13px;
}

.note-block {
  margin-top: 2px;
}
.note-view {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 12px; color: var(--m-text-secondary);
  cursor: pointer; padding: 2px 6px; border-radius: 4px;
  transition: background .15s;
  max-width: 100%; overflow: hidden;
}
.note-view:hover { background: var(--m-surface-variant); color: var(--m-text); }
.note-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.note-placeholder { color: var(--m-text-tertiary); font-style: italic; }
.note-edit { padding: 0; }

.pager { display: flex; justify-content: flex-end; margin-top: 16px; }
</style>
