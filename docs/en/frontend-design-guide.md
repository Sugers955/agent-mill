# Frontend Design Guide

> All new pages must follow these guidelines to ensure consistent style, layout, and interaction.

---

## 1. Tech Stack

| Type | Choice | Description |
|------|--------|-------------|
| Framework | Vue 3 + TypeScript | Composition API, `<script setup>` |
| UI Library | Element Plus | Global Chinese (zh-cn) |
| State Management | Pinia | stores directory |
| Routing | Vue Router | With role guards |
| Styling | CSS Variables | See `styles.css` `:root` |

---

## 2. CSS Variables (Must Use)

```css
/* Colors */
--m-primary: #1a73e8;          /* Primary color */
--m-primary-hover: #185abc;    /* Primary hover */
--m-primary-soft: #e8f0fe;     /* Primary light background */

--m-surface: #ffffff;          /* Card background */
--m-surface-variant: #f1f3f4;  /* Secondary background */
--m-bg: #f8f9fa;               /* Page background */
--m-bg-soft: #fafbfc;          /* Light background */

--m-text: #202124;             /* Primary text */
--m-text-secondary: #5f6368;   /* Secondary text */
--m-text-tertiary: #80868b;    /* Tertiary text */

--m-border: #e8eaed;           /* Border */
--m-border-strong: #dadce0;    /* Strong border */

--m-success: #1e8e3e;          /* Success */
--m-warning: #f29900;          /* Warning */
--m-danger: #d93025;           /* Danger */

/* Border Radius */
--m-radius-sm: 8px;
--m-radius: 12px;
--m-radius-lg: 16px;
--m-radius-pill: 999px;        /* Pill shape */

/* Shadow */
--m-shadow-1: 0 1px 2px 0 rgba(60,64,67,.08), 0 1px 3px 1px rgba(60,64,67,.04);
```

---

## 3. Page Layout Templates

### 3.1 Standard Admin Page

```vue
<template>
  <div class="page">
    <!-- Page header bar -->
    <div class="page-head">
      <span class="page-title">Page Title</span>
      <el-button type="primary" @click="onCreate">
        <el-icon><Plus /></el-icon>Create XXX
      </el-button>
    </div>

    <!-- Filter area (optional) -->
    <div class="filters">
      <el-input placeholder="Search..." clearable />
      <el-select placeholder="Filter..." clearable />
      <el-button type="primary">Search</el-button>
    </div>

    <!-- Table card -->
    <div class="surface" style="padding:0">
      <el-table :data="items" stripe v-loading="loading">
        <!-- Column definitions -->
      </el-table>
      <!-- Pagination (must be inside .surface) -->
      <div class="pager">
        <el-pagination
          background
          layout="total, sizes, prev, pager, next"
          :total="total"
          :page-size="pageSize"
          :current-page="page"
          :page-sizes="[20, 50, 100]"
          @current-change="onPageChange"
          @size-change="onSizeChange"
        />
      </div>
    </div>

    <!-- Dialog -->
    <el-dialog v-model="visible" title="Title" width="500px">
      <!-- Form content -->
    </el-dialog>
  </div>
</template>
```

### 3.2 Key Class Names

| Class | Purpose | Style |
|-------|---------|-------|
| `.page` | Page container | `padding: 24px 32px` |
| `.page-head` | Header bar | Flex layout, title + button left-right |
| `.page-title` | Title text | 22px 600 bold |
| `.filters` | Filter area | Flex layout, 12px gap |
| `.surface` | Card container | White bg + rounded corners + border + shadow |
| `.pager` | Pagination bar | Must be inside `.surface`, right-aligned |
| `.muted` | Auxiliary text | Secondary color |

---

## 4. Table Guidelines

### 4.1 Basic Usage

```vue
<div class="surface" style="padding:0">
  <el-table :data="items" stripe v-loading="loading">
    <el-table-column prop="name" label="Name" min-width="160" show-overflow-tooltip />
    <el-table-column label="Status" width="100">
      <template #default="{ row }">
        <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
          {{ row.enabled ? 'Enabled' : 'Disabled' }}
        </el-tag>
      </template>
    </el-table-column>
    <el-table-column label="Actions" width="160" fixed="right">
      <template #default="{ row }">
        <el-button size="small" text @click="onEdit(row)">Edit</el-button>
        <el-button size="small" text type="danger" @click="onDelete(row)">Delete</el-button>
      </template>
    </el-table-column>
  </el-table>
  <div class="pager">
    <el-pagination background layout="total, sizes, prev, pager, next"
      :total="total" :page-size="pageSize" :current-page="page"
      :page-sizes="[20, 50, 100]"
      @current-change="onPageChange" @size-change="onSizeChange" />
  </div>
</div>
```

### 4.2 Table Rules

| Rule | Description |
|------|-------------|
| `show-overflow-tooltip` | Required for long text columns |
| `fixed="right"` | Actions column fixed to right |
| `width` | Actions column 160px, status column 100px |
| `stripe` | Zebra striping must be enabled |
| `v-loading` | Loading state must be displayed |
| No data | Show `No Data` (Element Plus default) |

---

## 5. Pagination Guidelines

### 5.1 Chinese Locale

```ts
// main.ts configures global Chinese
app.use(ElementPlus, { locale: zhCn })
```

### 5.2 Layout Position

```vue
<!-- ✅ Correct: Pagination inside .surface -->
<div class="surface" style="padding:0">
  <el-table>...</el-table>
  <div class="pager">
    <el-pagination ... />
  </div>
</div>

<!-- ❌ Wrong: Pagination outside .surface -->
<div class="surface" style="padding:0">
  <el-table>...</el-table>
</div>
<div class="pager">
  <el-pagination ... />
</div>
```

### 5.3 Pagination Parameters

| Data Volume | page-sizes | Description |
|-------------|------------|-------------|
| Config data | No pagination needed | Load all at once |
| General data | `[20, 50, 100]` | Default 20 |
| Large data | `[10, 20, 50, 100]` | Default 10 |

---

## 6. Form Guidelines

### 6.1 Dialog Form

```vue
<el-dialog v-model="visible" :title="editing ? 'Edit XXX' : 'Create XXX'" width="500px">
  <el-form :model="form" label-width="100px">
    <el-form-item label="Name" required>
      <el-input v-model="form.name" placeholder="Enter name" />
    </el-form-item>
    <el-form-item label="Status">
      <el-switch v-model="form.enabled" />
    </el-form-item>
  </el-form>
  <template #footer>
    <el-button @click="visible = false">Cancel</el-button>
    <el-button type="primary" :loading="saving" @click="onSave">Save</el-button>
  </template>
</el-dialog>
```

### 6.2 Form Rules

| Rule | Description |
|------|-------------|
| `label-width` | Uniform 100px |
| `placeholder` | Must be provided |
| `:loading` | Save button must have loading state |
| Dialog width | Simple forms 460-500px, complex forms 700-900px |
| Title | Use ternary for Create/Edit |

---

## 7. Component Usage Guidelines

### 7.1 Buttons

| Scenario | Type | Example |
|----------|------|---------|
| Primary action | `type="primary"` | Create, Save |
| Destructive action | `type="danger"` text | Delete |
| Secondary action | text | Edit, Details |

### 7.2 Tags

| Status | Type |
|--------|------|
| Enabled/Success | `success` |
| Disabled/Inactive | `info` |
| Warning | `warning` |
| Error/Delete | `danger` |

### 7.3 Icons

```vue
<!-- Use Element Plus icons -->
<el-icon><Plus /></el-icon>
<el-icon><EditPen /></el-icon>
<el-icon><Delete /></el-icon>
<el-icon><Search /></el-icon>
```

---

## 8. Directory Structure

```
frontend/src/views/admin/
├── Agents.vue          Digital workforce management
├── Approvals.vue       Approval management
├── Dashboard.vue       Statistics panel
├── Departments.vue     Department management
├── Logs.vue            Log management
├── MCP.vue             MCP management
├── Models.vue          Model management
├── Packs.vue           Solution Packs
├── Quotas.vue          Quota management
├── Roles.vue           Role management
├── Skills.vue          Skill management
└── Users.vue           User management
```

---

## 9. Checklist

After completing a new page, verify:

- [ ] Uses `.page` as page container
- [ ] Uses `.page-head` as header bar
- [ ] Uses `.surface` as table card
- [ ] Pagination is inside `.surface`
- [ ] Pagination displays Chinese
- [ ] Table has `stripe` and `v-loading`
- [ ] Long text columns have `show-overflow-tooltip`
- [ ] Actions column has `fixed="right"`
- [ ] Dialog form has `label-width="100px"`
- [ ] Save button has `:loading` state
- [ ] Delete action uses `type="danger" text`
- [ ] Uses CSS variables for colors
