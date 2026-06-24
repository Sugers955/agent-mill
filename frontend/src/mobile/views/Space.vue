<template>
  <div class="mb-page space-mb">
    <header class="mb-header soft">
      <button class="mb-icon-btn" @click="$router.back()" aria-label="返回">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
      </button>
      <div class="mb-header-title"><span class="name">空间</span></div>
      <div style="width:36px"></div>
    </header>

    <div class="search-bar">
      <input
        v-model="q"
        class="mb-input"
        type="search"
        placeholder="搜索问题 / 回答 / 备注"
        @keydown.enter="onSearch"
      />
      <button v-if="q" class="clear-btn" @click="q = ''; onSearch()">清空</button>
    </div>

    <div class="body" @scroll.passive="onScroll" ref="scrollEl">
      <div v-if="loading && !rows.length" class="empty">加载中…</div>
      <div v-else-if="!rows.length" class="empty">
        <svg viewBox="0 0 24 24" width="40" height="40" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="opacity:.4;margin-bottom:8px"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
        <div>{{ q ? '没有匹配的收藏' : '空间还是空的' }}</div>
        <div v-if="!q" class="hint">在 PC 端对话里点 ⭐ 把问答存进来</div>
      </div>

      <div v-for="fav in rows" :key="fav.id" class="fav-card">
        <div class="card-head">
          <span class="agent-tag">{{ fav.agent_name || '-' }}</span>
          <span class="time-text">{{ relTime(fav.created_at) }}</span>
          <button class="del-btn" @click.stop="onRemove(fav)" aria-label="取消收藏">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-2 14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L5 6"/></svg>
          </button>
        </div>

        <div class="qa-question" :title="fav.question_text">
          <span class="q-prefix">Q</span>
          <span class="q-text">{{ fav.question_text || '(空)' }}</span>
        </div>

        <div class="qa-answer">
          <div v-if="!expanded[fav.id]" class="answer-clip">
            <span>{{ clipText(plainAnswer(fav.answer_text), 130) }}</span>
            <span v-if="fav.files?.length" class="files-hint">📎 {{ fav.files.length }}</span>
          </div>
          <div v-else class="answer-full">
            <div class="answer-text">{{ plainAnswer(fav.answer_text) }}</div>
            <div v-if="fav.files?.length" class="files-list">
              <a
                v-for="(f, fi) in fav.files"
                :key="fi"
                class="file-item"
                :href="fileUrl(f)"
                @click="onFileClick(f, $event)"
                target="_blank"
                rel="noopener"
              >
                <span class="file-icon">📄</span>
                <span class="file-name">{{ f.name }}</span>
                <span class="file-size">{{ fmtSize(f.size) }}</span>
              </a>
            </div>
          </div>
          <button class="toggle-btn" @click="toggleExpand(fav.id)">
            <span>{{ expanded[fav.id] ? '收起' : '展开' }}</span>
            <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
              <polyline v-if="expanded[fav.id]" points="18 15 12 9 6 15" />
              <polyline v-else points="6 9 12 15 18 9" />
            </svg>
          </button>
        </div>

        <div v-if="fav.note" class="note-line">
          <span class="note-icon">📝</span>{{ fav.note }}
        </div>
      </div>

      <div v-if="loading && rows.length" class="loading-more">加载中…</div>
      <div v-else-if="!hasMore && rows.length" class="end-hint">没有更多了</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { api } from '../api'
import { showToast } from '../toast'

const rows = ref<any[]>([])
const total = ref(0)
const loading = ref(false)
const expanded = reactive<Record<number, boolean>>({})
const q = ref('')
const PAGE_SIZE = 20
const offset = ref(0)
const hasMore = ref(false)
const scrollEl = ref<HTMLElement | null>(null)

async function load(reset = false) {
  if (loading.value) return
  if (reset) { offset.value = 0; rows.value = []; hasMore.value = false }
  loading.value = true
  try {
    const res = await api.favorites({
      q: q.value.trim() || undefined,
      limit: PAGE_SIZE,
      offset: offset.value,
    })
    if (reset) rows.value = res.items
    else rows.value = rows.value.concat(res.items)
    total.value = res.total
    offset.value += res.items.length
    hasMore.value = rows.value.length < res.total
  } catch {
    // toast already fired by api.handle()
  } finally {
    loading.value = false
  }
}
onMounted(() => load(true))

function onSearch() { load(true) }
function onScroll() {
  const el = scrollEl.value
  if (!el || loading.value || !hasMore.value) return
  if (el.scrollHeight - el.scrollTop - el.clientHeight < 80) load(false)
}

function toggleExpand(id: number) { expanded[id] = !expanded[id] }
function clipText(s: string, n: number) { return (s || '').length > n ? s.slice(0, n) + '…' : (s || '') }

function plainAnswer(s: string): string {
  if (!s) return ''
  return s
    .replace(/```show-widget[\s\S]*?```/g, '[图表]')
    .replace(/<svg[\s\S]*?<\/svg>/gi, '[图表]')
    .replace(/```[\s\S]*?```/g, '[代码]')
    .trim()
}

async function onRemove(fav: any) {
  if (!window.confirm('确定取消收藏?')) return
  try {
    await api.deleteFavorite(fav.id)
    rows.value = rows.value.filter((x) => x.id !== fav.id)
    total.value = Math.max(0, total.value - 1)
    showToast('已取消收藏', 'success')
  } catch {}
}

function relTime(iso: string) {
  if (!iso) return ''
  const t = new Date(iso).getTime()
  const diff = Date.now() - t
  if (diff < 60_000) return '刚刚'
  if (diff < 3600_000) return `${Math.floor(diff / 60_000)} 分钟前`
  if (diff < 86400_000) return `${Math.floor(diff / 3600_000)} 小时前`
  return new Date(iso).toLocaleDateString()
}

function fmtSize(b?: number) {
  if (!b && b !== 0) return ''
  if (b < 1024) return `${b} B`
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`
  return `${(b / 1024 / 1024).toFixed(2)} MB`
}

// download_url with token in query (so direct browser nav works on mobile).
function fileUrl(f: any) {
  const url = f?.download_url || ''
  if (!url) return ''
  const t = localStorage.getItem('access_token') || ''
  if (!t) return url
  const sep = url.includes('?') ? '&' : '?'
  return `${url}${sep}t=${encodeURIComponent(t)}`
}

// Token may have expired (72h). Try a HEAD-ish probe first; on 410/404/403
// refresh via output_path then open the new URL.
async function onFileClick(f: any, ev: MouseEvent) {
  if (!f?.output_path) return  // no fallback path → let the anchor proceed
  try {
    const r = await fetch(fileUrl(f), { method: 'GET', headers: authHeader() })
    if (r.ok) return  // anchor's default navigation already happened
  } catch {
    return
  }
  // got an error — block default and try refresh
  ev.preventDefault()
  try {
    const fresh = await api.refreshDownload(f.output_path)
    if (fresh?.download_url) {
      f.download_url = fresh.download_url
      window.open(fileUrl(f), '_blank')
    }
  } catch {}
}

function authHeader(): Record<string, string> {
  const t = localStorage.getItem('access_token') || ''
  return t ? { Authorization: `Bearer ${t}` } : {}
}
</script>

<style scoped>
.space-mb { background: var(--m-bg); }
.mb-header.soft { background: var(--m-bg); border-bottom: none; }

.search-bar {
  display: flex; gap: 8px;
  padding: 6px 12px 10px;
  background: var(--m-bg);
}
.mb-input {
  flex: 1;
  height: 36px;
  padding: 0 12px;
  border-radius: 999px;
  border: 1px solid var(--m-border);
  background: var(--m-surface);
  font-size: 14px;
  color: var(--m-text);
  outline: none;
}
.mb-input:focus { border-color: var(--m-primary); }
.clear-btn {
  background: transparent; border: none;
  color: var(--m-primary);
  font-size: 13px; padding: 0 6px;
}

.body { flex: 1; overflow: auto; padding: 4px 12px 24px; }

.empty {
  display: flex; flex-direction: column; align-items: center;
  text-align: center; color: var(--m-text-tertiary);
  padding: 60px 20px; font-size: 14px;
}
.empty .hint { font-size: 12px; margin-top: 6px; }

.fav-card {
  background: var(--m-surface);
  border-radius: 14px;
  padding: 12px 14px;
  margin-bottom: 10px;
  box-shadow: var(--m-shadow-1);
  display: flex; flex-direction: column; gap: 8px;
}

.card-head {
  display: flex; align-items: center; gap: 8px;
  font-size: 11.5px; color: var(--m-text-secondary);
}
.agent-tag {
  background: var(--m-primary-soft);
  color: var(--m-primary);
  padding: 2px 8px; border-radius: 999px;
  font-weight: 500;
  max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.time-text { flex: 1; }
.del-btn {
  background: transparent; border: none;
  color: var(--m-text-tertiary);
  padding: 4px;
}
.del-btn:active { color: var(--m-danger); }

.qa-question {
  background: var(--m-primary-soft);
  padding: 6px 10px; border-radius: 8px;
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; line-height: 1.5; font-weight: 500;
  min-width: 0;
}
.q-prefix {
  font-weight: 700; color: var(--m-primary);
  font-size: 10px;
  background: rgba(255,255,255,.6); padding: 0 5px;
  border-radius: 3px; flex-shrink: 0;
  line-height: 16px;
}
.q-text {
  flex: 1; min-width: 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

.qa-answer { display: flex; flex-direction: column; gap: 6px; }
.answer-clip {
  font-size: 13px; line-height: 1.6;
  color: var(--m-text-secondary);
  display: flex; align-items: flex-start; gap: 6px;
  flex-wrap: wrap;
}
.answer-clip > span:first-child {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  flex: 1; min-width: 0;
}
.files-hint {
  background: var(--m-primary-soft); color: var(--m-primary);
  font-size: 11px; padding: 1px 8px; border-radius: 999px;
  flex-shrink: 0;
}
.answer-full {
  background: var(--m-bg-soft);
  border-radius: 8px;
  padding: 10px 12px;
  display: flex; flex-direction: column; gap: 8px;
}
.answer-text {
  font-size: 13.5px; line-height: 1.65;
  color: var(--m-text);
  white-space: pre-wrap; word-break: break-word;
}
.files-list { display: flex; flex-direction: column; gap: 4px; }
.file-item {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 10px;
  background: var(--m-surface);
  border-radius: 8px;
  text-decoration: none;
  color: var(--m-text);
  font-size: 13px;
}
.file-item:active { background: var(--m-surface-variant); }
.file-icon { font-size: 16px; }
.file-name {
  flex: 1; min-width: 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.file-size { color: var(--m-text-tertiary); font-size: 11px; flex-shrink: 0; }

.toggle-btn {
  align-self: flex-end;
  display: inline-flex; align-items: center; gap: 3px;
  background: transparent; border: none;
  color: var(--m-text-tertiary);
  font-size: 12px;
  padding: 2px 6px;
}

.note-line {
  font-size: 12px;
  color: var(--m-text-secondary);
  display: flex; align-items: center; gap: 4px;
  padding-top: 4px;
  border-top: 1px dashed var(--m-border);
}
.note-icon { font-size: 12px; }

.loading-more, .end-hint {
  text-align: center; padding: 16px 0;
  font-size: 12px; color: var(--m-text-tertiary);
}
</style>
