---
layout: default
title: 功能展示 — Agent Mill
---

<style>
.lang-switch { text-align: right; margin: 12px 0; font-size: 14px; }
.lang-switch a { display: inline-block; padding: 4px 14px; border: 1px solid #d0d7de; border-radius: 6px; color: #0969da; text-decoration: none; margin: 0 2px; cursor: pointer; }
.lang-switch a.active { background: #0969da; color: #fff; border-color: #0969da; }
</style>

<div class="lang-switch">
  <a onclick="switchLang('en')">English</a>
  <a class="active" onclick="switchLang('zh')">中文</a>
</div>

<script>
function switchLang(lang) {
  var base = window.location.pathname.includes('/agent-mill/') ? '/agent-mill' : '';
  window.location.href = base + (lang === 'en' ? '/features.html' : '/zh/features.html');
}
</script>

# 🏭 Agent Mill — 功能全景展示

本文档逐一介绍 Agent Mill 的每个核心功能模块。

---

## 1. 指挥中心 — 数字员工工位

实时查看所有数字员工的状态、快速发起对话和管理任务。

| 视图 | 说明 |
|:-----|:-----|
| **卡片视图** | 员工名称、描述、状态指示器 |
| **工位视图** | 办公室桌面微缩场景：双显示器、LED 灯带、桌面配件 |

**核心操作**: 发起对话、创建任务、监控员工健康状态。

---

## 2. 四标签页员工编辑器

每个数字员工通过专业的 4-Tab 编辑器配置：

### Tab 1: 基础信息
- 头像上传、唯一编码、名称、业务描述、启用/停用、设为默认

### Tab 2: 角色 & Prompt
- **角色人设** — 定义员工身份、职责和语气
- **输出约束** — 格式规范、合规限制、语气要求

### Tab 3: 模型算力
- 模型选择（Claude、DeepSeek、千问、GLM、OpenAI）
- **算力滑动条** — 5 档调节，附成本/效率指南
- 高级参数：Temperature、最大 Token、最大轮次

### Tab 4: 知识库 & 技能
- 多选绑定 RAG 知识库
- 技能标签管理 + 技能市场快速添加
- MCP 连接器挂载

---

## 3. 双路径流式引擎

核心技术差异化——两条流式路径产出相同的 SSE 事件：

| 供应商 | 流式机制 |
|:-------|:---------|
| **Anthropic (Claude)** | Claude Agent SDK 原生 SSE |
| **OpenAI 兼容** | 自定义 tool_calls 多轮循环 |

**SSE 事件顺序**: `meta → thinking → text → tool_use → tool_result → file → ui → error → done`

### 实现了什么？

- 实时逐 Token 流式输出
- 思考过程可折叠展示
- 工具执行步骤实时追踪
- 内联 Widget 渲染（SVG 图表、HTML 表单）
- 文件实时生成预览

---

## 4. 技能系统（三种形态）

| 类型 | 说明 |
|:-----|:-----|
| **Path 型** | ZIP 上传 + SKILL.md + 资源文件，适合复杂业务流程 |
| **Callable 型** | Python 函数直接 import 调用，轻量快速 |
| **Composite 型** | YAML DAG 步骤编排，支持条件分支和并行执行 |

### 安全防护
- 9 条 Shell 注入规则检测
- Python AST 静态分析
- 上传拦截 + 审计记录

---

## 5. MCP 连接器系统

三种传输协议对接任意外部工具：

| 协议 | 适用场景 |
|:-----|:---------|
| **stdio** | 本地子进程工具 |
| **sse** | 长连接服务 |
| **http** | REST API |

**管理功能**: CRUD + 连接测试 + 工具列表发现 + 自动生成中文摘要 + 按员工隔离。

---

## 6. RAG 知识库

| 阶段 | 技术 |
|:-----|:-----|
| **上传** | 30+ 文件格式 |
| **解析** | MinerU 引擎 + 自动降级 |
| **分块** | 500 字符窗口，50 重叠 |
| **向量化** | OpenAI 兼容 API |
| **向量库** | ZVec（阿里巴巴，Rust 内核，嵌入式） |
| **检索** | 余弦相似度，top_k 可配 |

**自动注入**: 每次对话自动检索知识库并注入系统提示词。

---

## 7. 多 Agent 协作

| 模式 | 说明 |
|:-----|:-----|
| **顺序** | Agent1 → Agent2 → … → AgentN |
| **并行** | 所有 Agent 同时处理 |
| **MapReduce** | 各自处理 → 汇总 |

**通信**: 异步消息传递，支持优先级（普通/高）、消息委托、自动消费轮询。

---

## 8. 工作流 & 方案包编辑器

- **Vue Flow 画布** — 拖拽式工作流编辑器
- **6 种节点**: 技能 / 并行组 / 聚合 / 条件分支 / 子Agent / 人工审批
- **持久化**: 每个节点执行后写入数据库
- **可恢复**: 断点续跑
- **执行追踪**: 完整运行历史

---

## 9. Dashboard 统计面板

- **7+3 个 ECharts 图表**: Token 趋势、用户 Top10、员工分布、模型成本、部门统计、员工效果、延迟趋势、错误率趋势、系统健康
- **Token 明细**: 分页查询 + CSV 导出
- **4-Tab 布局**: 概览 / 用户 / 成本 / 性能

---

## 10. 企业级特性

| 功能 | 说明 |
|:-----|:-----|
| **RBAC** | admin / operator / user 三角色 |
| **SSO/LDAP** | LDAP 认证 + OIDC 完整回调 |
| **审计日志** | 管理操作 + 调用日志双表 |
| **数据脱敏** | 自动脱敏邮箱/手机/身份证号 |
| **API 限流** | 令牌桶，按路径限制 |
| **配额控制** | 用户级月度额度 |
| **告警通知** | 规则引擎 + 钉钉/企微/飞书 Webhook |

---

## 11. 移动端

独立 Vue 3 应用 `/m.html`，Hash 路由，完全独立的路由/状态/视图/样式。

---

## 12. 文件处理

| 格式 | 解析方式 |
|:-----|:---------|
| TXT/MD/CSV/JSON/HTML/XML/YAML | 直接读取 |
| PDF | MinerU → pypdf 降级 |
| DOCX | MinerU → python-docx 降级 |
| XLSX | MinerU → openpyxl 降级 |
| 图片 | MinerU OCR |

**预览**: HTML iframe / PDF 原生 / Markdown / 代码 / SVG / 图片（JWT 鉴权 + 过期 Token）。
