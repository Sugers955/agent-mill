<template>
  <div class="card-list">
    <div v-if="schema.title" class="title-row">
      <h3 class="title">{{ schema.title }}</h3>
      <span v-if="schema.data_model.total" class="muted">共 {{ schema.data_model.total }} 项</span>
    </div>

    <div v-if="schema.filters?.length" class="filter-bar">
      <el-button
        v-for="f in schema.filters"
        :key="f.field"
        size="small"
        :type="activeSort === f.field ? 'primary' : 'default'"
        @click="onFilter(f)"
      >
        {{ f.label }}
      </el-button>
    </div>

    <div class="grid" :class="{ 'no-image': allImagesMissing }">
      <div
        v-for="(item, i) in displayItems"
        :key="item.id || i"
        class="card"
        @click="cardAction && fire(cardAction, i, item)"
      >
        <div v-if="!allImagesMissing" class="img-wrap">
          <img
            v-if="pickImage(item) && !brokenImages[i]"
            :src="pickImage(item)"
            :alt="pickTitle(item)"
            @error="brokenImages[i] = true"
          />
          <div v-else class="img-placeholder" :style="{ background: placeholderColor(i) }">
            <span class="ph-letter">{{ pickTitle(item).slice(0, 1) }}</span>
          </div>
        </div>
        <div class="card-body">
          <div class="card-name">{{ pickTitle(item) }}</div>
          <div v-if="pickSubtitle(item)" class="card-addr muted">{{ pickSubtitle(item) }}</div>
          <div class="card-row">
            <span v-if="pickPrice(item) != null" class="price">¥ {{ pickPrice(item) }}</span>
            <el-rate v-if="item.rating != null" :model-value="Number(item.rating)" disabled allow-half size="small" />
          </div>
          <div v-if="pickTags(item).length" class="tags">
            <el-tag v-for="t in pickTags(item)" :key="t" size="small" type="info" effect="plain">{{ t }}</el-tag>
          </div>
          <div v-if="buttonActions.length" class="card-actions" @click.stop>
            <el-button
              v-for="a in buttonActions"
              :key="a.name"
              :type="a.style === 'primary' ? 'primary' : (a.style === 'danger' ? 'danger' : 'default')"
              size="small"
              @click="fire(a, i, item)"
            >{{ a.label }}</el-button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="schema.pagination" class="pagination-row">
      <el-pagination
        :current-page="schema.pagination.page"
        :page-size="schema.pagination.page_size"
        :total="schema.pagination.total"
        layout="prev, pager, next, total"
        @current-change="onPage"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ActionDef, UIMessage } from '../types/schema'

const props = defineProps<{ schema: UIMessage; onAction: (a: ActionDef, params: any, ctx: any) => void }>()

const activeSort = ref<string>('')
// Track which cards' images failed to load (so we can swap to a placeholder)
const brokenImages = ref<Record<number, boolean>>({})

// Deterministic pastel based on index — gives each card a different placeholder color
function placeholderColor(i: number): string {
  const palette = [
    'linear-gradient(135deg,#fef3c7 0%,#fde68a 100%)',
    'linear-gradient(135deg,#dbeafe 0%,#bfdbfe 100%)',
    'linear-gradient(135deg,#dcfce7 0%,#bbf7d0 100%)',
    'linear-gradient(135deg,#fce7f3 0%,#fbcfe8 100%)',
    'linear-gradient(135deg,#ede9fe 0%,#ddd6fe 100%)',
    'linear-gradient(135deg,#fed7aa 0%,#fdba74 100%)',
  ]
  return palette[i % palette.length]
}

const cardAction = computed<ActionDef | undefined>(() =>
  (props.schema.actions || []).find(a => a.trigger === 'card_click'))
const buttonActions = computed<ActionDef[]>(() =>
  (props.schema.actions || []).filter(a => a.trigger === 'button_click'))

const displayItems = computed(() => {
  const items = (props.schema.data_model.items || []).slice()
  if (activeSort.value === 'price') items.sort((a: any, b: any) => (pickPrice(a) ?? 0) - (pickPrice(b) ?? 0))
  else if (activeSort.value === 'rating') items.sort((a: any, b: any) => (b.rating ?? 0) - (a.rating ?? 0))
  return items
})

// True when not a single item carries an image. In that case we render a
// compact image-less card layout — much cleaner than showing a row of giant
// gradient-letter placeholders, which is what ask_user_pick / ask_user_form
// produces most of the time (the model rarely has real cover images for
// follow-up questions).
const allImagesMissing = computed(() =>
  displayItems.value.length > 0 && displayItems.value.every((it: any) => !pickImage(it)))

// ---------- Field-name fallbacks ----------
// CardList tries common aliases so MCPs / Skills with different naming
// (orders use scenic_spot_name + total_price, hotels use name + price, etc.)
// all render without forcing each adapter to remap fields.
// Schema can override via data_model.card_field_map = { title: '/foo', ... }.
function pick(item: any, candidates: string[], explicit?: string): any {
  if (explicit && typeof explicit === 'string') {
    const path = explicit.startsWith('/') ? explicit.slice(1) : explicit
    return path.split('/').reduce((cur: any, k: string) => (cur ? cur[k] : undefined), item)
  }
  for (const k of candidates) {
    const v = item?.[k]
    if (v != null && v !== '') return v
  }
  return undefined
}

const fieldMap = computed<Record<string, string>>(() => props.schema.data_model?.card_field_map || {})

function pickTitle(item: any): string {
  return pick(item, ['title', 'name', 'scenic_spot_name', 'spot_name', 'product_name', 'subject', 'order_no'], fieldMap.value.title)
    ?? `#${item?.id ?? ''}`
}
function pickSubtitle(item: any): string {
  const explicit = fieldMap.value.subtitle
  if (explicit) return pick(item, [], explicit) ?? ''
  // Built-in: prefer address / location, otherwise stitch order-style fields
  const addr = item?.address ?? item?.location
  if (addr) return addr
  const customer = item?.customer_name
  const visit = item?.visit_date
  const count = item?.ticket_count
  const status = item?.status
  if (customer || visit) {
    const parts = [customer, visit, count != null ? `${count}张` : '', status].filter(Boolean)
    return parts.join(' · ')
  }
  return item?.description ?? ''
}
function pickPrice(item: any): number | null | undefined {
  return pick(item, ['price', 'total_price', 'amount', 'unit_price'], fieldMap.value.price)
}
function pickImage(item: any): string {
  return pick(item, ['image', 'cover', 'image_url', 'thumbnail'], fieldMap.value.image) ?? ''
}
function pickTags(item: any): string[] {
  if (Array.isArray(item?.tags)) return item.tags
  // Auto-derive a tag from common status fields
  const tags: string[] = []
  if (item?.status) tags.push(String(item.status))
  return tags
}

function fire(a: ActionDef, index: number, row: any) {
  props.onAction(a, null, { index, row })
}

function onFilter(f: any) {
  if (!f.agent_call) {
    activeSort.value = activeSort.value === f.field ? '' : f.field
    return
  }
  props.onAction(
    { name: 'filter', label: f.label, trigger: 'select_change', agent_call: true,
      tool: 'filter', params_from: '/' } as ActionDef,
    { field: f.field },
    {},
  )
}

function onPage(page: number) {
  if (!props.schema.pagination?.agent_call) return
  props.onAction(
    { name: 'paginate', label: '翻页', trigger: 'select_change', agent_call: true,
      tool: 'paginate', params_from: '/' } as ActionDef,
    { page },
    {},
  )
}
</script>

<style scoped>
.card-list { display: flex; flex-direction: column; gap: 12px; }
.title-row { display:flex; align-items:baseline; gap: 8px; }
.title { margin: 0; font-size: 16px; font-weight: 600; }
.muted { color: var(--m-text-secondary); font-size: 12px; }
.filter-bar { display:flex; gap: 6px; flex-wrap: wrap; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }

/* When the whole batch has no images (typical for ask_user_pick follow-ups),
   collapse to a compact text-card grid — no awkward letter placeholders. */
.grid.no-image { grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 8px; }
.grid.no-image .card { min-height: 0; }
.grid.no-image .card-body { padding: 12px 14px; gap: 4px; }
.grid.no-image .card-name { font-size: 14.5px; }

.card {
  border: 1px solid var(--m-border); border-radius: var(--m-radius);
  background: var(--m-surface); cursor: pointer; overflow: hidden;
  transition: transform .15s ease, box-shadow .15s ease, border-color .15s ease;
}
.card:hover { transform: translateY(-2px); box-shadow: var(--m-shadow-2); border-color: var(--m-border-strong); }
.img-wrap { aspect-ratio: 16/9; background: var(--m-bg-soft); }
.img-wrap img { width: 100%; height: 100%; object-fit: cover; display: block; }
.img-placeholder {
  width: 100%; height: 100%;
  display: flex; align-items: center; justify-content: center;
  color: rgba(15,23,42,.55);
  font-family: 'Inter', sans-serif;
}
.img-placeholder .ph-letter {
  font-size: 38px; font-weight: 700; line-height: 1;
  letter-spacing: -0.02em;
}
.card-body { padding: 10px 12px; display: flex; flex-direction: column; gap: 6px; }
.card-name { font-weight: 600; font-size: 14px; color: var(--m-text); }
.card-addr { font-size: 12px; }
.card-row { display:flex; align-items:center; justify-content: space-between; gap: 8px; }
.price { color: var(--m-danger); font-weight: 700; font-size: 15px; }
.tags { display:flex; flex-wrap: wrap; gap: 4px; }
.card-actions { display:flex; gap: 6px; margin-top: 4px; }
.pagination-row { display:flex; justify-content: flex-end; }
</style>
