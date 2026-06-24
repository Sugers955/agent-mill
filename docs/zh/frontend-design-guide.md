# 前端设计规范

> 所有新页面必须遵循以下规范，确保风格、布局、交互一致。

---

## 一、技术栈

| 类型 | 选型 | 说明 |
|------|------|------|
| 框架 | Vue 3 + TypeScript | Composition API，`<script setup>` |
| UI 库 | Element Plus | 全局中文（zh-cn） |
| 状态管理 | Pinia | stores 目录 |
| 路由 | Vue Router | 带角色守卫 |
| 样式 | CSS 变量 | 见 `styles.css` `:root` |

---

## 二、CSS 变量（必须使用）

```css
/* 颜色 */
--m-primary: #1a73e8;          /* 主色 */
--m-primary-hover: #185abc;    /* 主色 hover */
--m-primary-soft: #e8f0fe;     /* 主色浅底 */

--m-surface: #ffffff;          /* 卡片背景 */
--m-surface-variant: #f1f3f4;  /* 次级背景 */
--m-bg: #f8f9fa;               /* 页面背景 */
--m-bg-soft: #fafbfc;          /* 浅背景 */

--m-text: #202124;             /* 主文字 */
--m-text-secondary: #5f6368;   /* 次文字 */
--m-text-tertiary: #80868b;    /* 辅助文字 */

--m-border: #e8eaed;           /* 边框 */
--m-border-strong: #dadce0;    /* 强边框 */

--m-success: #1e8e3e;          /* 成功 */
--m-warning: #f29900;          /* 警告 */
--m-danger: #d93025;           /* 危险 */

/* 圆角 */
--m-radius-sm: 8px;
--m-radius: 12px;
--m-radius-lg: 16px;
--m-radius-pill: 999px;        /* 胶囊 */

/* 阴影 */
--m-shadow-1: 0 1px 2px 0 rgba(60,64,67,.08), 0 1px 3px 1px rgba(60,64,67,.04);
```

---

## 三、页面布局模板

### 3.1 标准管理页面

```vue
<template>
  <div class="page">
    <!-- 页面标题栏 -->
    <div class="page-head">
      <span class="page-title">页面标题</span>
      <el-button type="primary" @click="onCreate">
        <el-icon><Plus /></el-icon>新建XXX
      </el-button>
    </div>

    <!-- 筛选区（可选） -->
    <div class="filters">
      <el-input placeholder="搜索..." clearable />
      <el-select placeholder="筛选..." clearable />
      <el-button type="primary">搜索</el-button>
    </div>

    <!-- 表格卡片 -->
    <div class="surface" style="padding:0">
      <el-table :data="items" stripe v-loading="loading">
        <!-- 列定义 -->
      </el-table>
      <!-- 分页（必须在 surface 内部） -->
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

    <!-- 弹窗 -->
    <el-dialog v-model="visible" title="标题" width="500px">
      <!-- 表单内容 -->
    </el-dialog>
  </div>
</template>
```

### 3.2 关键类名

| 类名 | 用途 | 样式 |
|------|------|------|
| `.page` | 页面容器 | `padding: 24px 32px` |
| `.page-head` | 标题栏 | flex 布局，标题+按钮左右排列 |
| `.page-title` | 标题文字 | 22px 600 加粗 |
| `.filters` | 筛选区 | flex 布局，间距 12px |
| `.surface` | 卡片容器 | 白色背景 + 圆角 + 边框 + 阴影 |
| `.pager` | 分页栏 | 必须在 `.surface` 内部，右对齐 |
| `.muted` | 辅助文字 | 次要颜色 |

---

## 四、表格规范

### 4.1 基础用法

```vue
<div class="surface" style="padding:0">
  <el-table :data="items" stripe v-loading="loading">
    <el-table-column prop="name" label="名称" min-width="160" show-overflow-tooltip />
    <el-table-column label="状态" width="100">
      <template #default="{ row }">
        <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
          {{ row.enabled ? '启用' : '停用' }}
        </el-tag>
      </template>
    </el-table-column>
    <el-table-column label="操作" width="160" fixed="right">
      <template #default="{ row }">
        <el-button size="small" text @click="onEdit(row)">编辑</el-button>
        <el-button size="small" text type="danger" @click="onDelete(row)">删除</el-button>
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

### 4.2 表格规则

| 规则 | 说明 |
|------|------|
| `show-overflow-tooltip` | 长文本列必须加 |
| `fixed="right"` | 操作列固定右侧 |
| `width` | 操作列 160px，状态列 100px |
| `stripe` | 斑马纹必须开启 |
| `v-loading` | 加载状态必须显示 |
| 无数据 | 显示 `No Data`（Element Plus 默认） |

---

## 五、分页规范

### 5.1 必须中文

```ts
// main.ts 已配置全局中文
app.use(ElementPlus, { locale: zhCn })
```

### 5.2 布局位置

```vue
<!-- ✅ 正确：分页在 .surface 内部 -->
<div class="surface" style="padding:0">
  <el-table>...</el-table>
  <div class="pager">
    <el-pagination ... />
  </div>
</div>

<!-- ❌ 错误：分页在 .surface 外部 -->
<div class="surface" style="padding:0">
  <el-table>...</el-table>
</div>
<div class="pager">
  <el-pagination ... />
</div>
```

### 5.3 分页参数

| 数据量 | page-sizes | 说明 |
|--------|------------|------|
| 配置类 | 不需要分页 | 一次性加载 |
| 一般数据 | `[20, 50, 100]` | 默认 20 |
| 大量数据 | `[10, 20, 50, 100]` | 默认 10 |

---

## 六、表单规范

### 6.1 弹窗表单

```vue
<el-dialog v-model="visible" :title="editing ? '编辑XXX' : '新建XXX'" width="500px">
  <el-form :model="form" label-width="100px">
    <el-form-item label="名称" required>
      <el-input v-model="form.name" placeholder="请输入名称" />
    </el-form-item>
    <el-form-item label="状态">
      <el-switch v-model="form.enabled" />
    </el-form-item>
  </el-form>
  <template #footer>
    <el-button @click="visible = false">取消</el-button>
    <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
  </template>
</el-dialog>
```

### 6.2 表单规则

| 规则 | 说明 |
|------|------|
| `label-width` | 统一 100px |
| `placeholder` | 必须提供 |
| `:loading` | 保存按钮必须有 loading 状态 |
| 弹窗宽度 | 简单表单 460-500px，复杂表单 700-900px |
| 标题 | 新建/编辑 用三元表达式 |

---

## 七、组件使用规范

### 7.1 按钮

| 场景 | 类型 | 示例 |
|------|------|------|
| 主要操作 | `type="primary"` | 新建、保存 |
| 危险操作 | `type="danger"` text | 删除 |
| 次要操作 | text | 编辑、详情 |

### 7.2 标签

| 状态 | type |
|------|------|
| 启用/成功 | `success` |
| 停用/禁用 | `info` |
| 警告 | `warning` |
| 错误/删除 | `danger` |

### 7.3 图标

```vue
<!-- 使用 Element Plus 图标 -->
<el-icon><Plus /></el-icon>
<el-icon><EditPen /></el-icon>
<el-icon><Delete /></el-icon>
<el-icon><Search /></el-icon>
```

---

## 八、目录结构

```
frontend/src/views/admin/
├── Agents.vue          智能体管理
├── Approvals.vue       审批管理
├── Dashboard.vue       统计面板
├── Departments.vue     部门管理
├── Logs.vue            日志管理
├── MCP.vue             MCP 管理
├── Models.vue          模型管理
├── Packs.vue           Solution Pack
├── Quotas.vue          额度管理
├── Roles.vue           角色管理
├── Skills.vue          技能管理
└── Users.vue           用户管理
```

---

## 九、检查清单

新页面开发完成后，检查以下项目：

- [ ] 使用 `.page` 作为页面容器
- [ ] 使用 `.page-head` 作为标题栏
- [ ] 使用 `.surface` 作为表格卡片
- [ ] 分页在 `.surface` 内部
- [ ] 分页显示中文
- [ ] 表格有 `stripe` 和 `v-loading`
- [ ] 长文本列有 `show-overflow-tooltip`
- [ ] 操作列 `fixed="right"`
- [ ] 弹窗表单有 `label-width="100px"`
- [ ] 保存按钮有 `:loading` 状态
- [ ] 删除操作使用 `type="danger" text`
- [ ] 使用 CSS 变量定义颜色
