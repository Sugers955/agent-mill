<div align="center">

# 🏭 Agent Mill

### 你的数字员工工厂 — 企业级 AI 数字员工平台

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB.svg)](https://python.org)
[![Vue 3](https://img.shields.io/badge/Vue-3-42b883.svg)](https://vuejs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)

[English](README.md) | 中文

</div>

---

## 这是什么？

Agent Mill 是一个**开箱即用的企业级数字员工平台**。它让管理员像搭积木一样配置各种 AI 数字员工，终端用户通过自然语言对话与数字员工交互，完成文档处理、数据分析、代码生成、知识问答等真实业务任务。

**一句话理解**：你可以用它在 10 分钟内搭建一个能调用工具、检索知识库、处理文件、甚至多 Agent 协作的智能助手，并通过 Web 界面安全地交付给团队使用。

![指挥中心](docs/images/智慧中心.png)

---

## ⚡ 核心引擎：Claude Agent SDK

Agent Mill 是首批集成 **Anthropic Claude Agent SDK** 的开源平台之一——这是驱动 Claude.ai 智能体能力的同一套 SDK。这赋予了 Agent Mill 大多数其他平台不具备的能力：

| 能力 | 作用 |
|:-----|:-----|
| **真流式 SSE** | 实时逐 token 流式输出，包含思考过程、工具调用、结果——非模拟轮询 |
| **原生工具编排** | Claude 内置工具调用引擎，自动处理技能执行、MCP 调用和文件操作 |
| **扩展思考** | 完整展示 Claude 推理过程，在对话中以可折叠「思考卡片」呈现 |
| **Widget 渲染** | Claude 可直接生成交互式 SVG 图表、HTML 表单和数据表格 |
| **多轮自主决策** | Claude 自主决定何时调用工具、何时追问、何时给出最终答案 |
| **安全护栏** | 内置工具使用安全层——输入过滤、输出校验、系统提示词完整性保护 |

> 对于非 Anthropic 供应商（DeepSeek、千问、OpenAI 等），Agent Mill 实现了等效的 **OpenAI 兼容 tool_calls 循环**，同一套 SSE 协议体验一致。

---

## 能解决什么问题？

| 企业痛点 | Agent Mill 的解法 |
|:---------|:-----------------|
| AI 模型各自为政，无法统一管理 | 统一模型网关，一个平台管理所有 LLM 供应商 |
| 内部知识散落，AI 无法检索 | RAG 知识库，上传文档即可被 AI 引用 |
| 想让 AI 调用内部系统 API | MCP 连接器，3 种协议对接任意工具 |
| 每次用 AI 都要重新配置 | 数字员工模板，一次配置多次复用 |
| 担心数据安全和权限混乱 | 三角色 RBAC + SSO/LDAP + 审计日志 |
| 想让多个 AI 协作完成复杂任务 | 多 Agent 编排（顺序/并行/MapReduce） |
| 手机上也要用 AI 助手 | 移动端独立应用，完整体验 |

---

## 核心能力

### 🤖 数字员工管理

每个数字员工是一个独立的 AI 助手实例，可以：

- 绑定不同的 LLM 模型（Claude、DeepSeek、千问、GLM、OpenAI）
- 挂载专属技能（代码执行、文件处理、表单交互）
- 连接外部工具（数据库查询、API 调用、消息推送）
- 关联知识库（自动检索注入上下文）
- 设置推理参数（模型努力度、最大轮次）

### 🛠️ 技能系统（三种形态）

| 类型 | 描述 | 适用场景 |
|:-----|:-----|:---------|
| **path 型** | ZIP 上传 + SKILL.md + 资源文件 | 复杂业务流程，需附带资源文件 |
| **callable 型** | Python 函数直接调用 | 轻量工具，快速开发 |
| **composite 型** | YAML DAG 步骤编排 | 多步骤工作流，条件分支 |

### 🔌 MCP 连接器

| 协议 | 描述 |
|:-----|:-----|
| **stdio** | 子进程通信 |
| **sse** | Server-Sent Events |
| **http** | Streamable HTTP |

### 📚 RAG 知识库

- **向量引擎**: ZVec（阿里巴巴，Rust 内核，嵌入式，零额外容器）
- **文档管道**: 上传 → 解析（30+ 格式）→ 分块 → Embedding → 索引
- **自动注入**: 每次对话自动检索知识库注入上下文

### 🔄 多 Agent 协作

| 编排方式 | 描述 |
|:---------|:-----|
| **顺序执行** | Agent1 → Agent2 → … → AgentN |
| **并行执行** | 所有 Agent 同时处理 |
| **MapReduce** | 各自处理 → 汇总 |

![架构图](docs/images/技术架构.png)

---

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- MySQL 8.0+

### 一键启动

```bash
git clone https://github.com/Sugers955/agent-mill.git
cd agent-mill
cp .env.example .env        # 编辑数据库连接信息
make dev                    # 启动后端:8000 + 前端:5173
```

访问 **http://localhost:5173** — 登录账号 `admin` / `Admin@2026`。

### Docker 部署

```bash
docker compose up -d --build
```

### 管理脚本

```bash
./mill start      # 启动后端 + 前端
./mill stop       # 停止所有
./mill status     # 查看运行状态
./mill logs       # 查看后端日志
./mill restart    # 重启所有
```

---

## 架构概览

Agent Mill 采用前后端分离的微服务架构：

- **后端**: Python 3.11+ / FastAPI / SQLAlchemy 2.0 (async) / MySQL 8.0
- **前端**: Vue 3 / TypeScript / Vite / Pinia / Element Plus
- **流式响应**: 双路径 SSE（Anthropic Agent SDK + OpenAI 兼容 tool_calls 循环）
- **安全防护**: 7 层保护（输入过滤、技能 AST 扫描、文件沙箱、Fernet 加密）
- **存储隔离**: `storage/uploads/<user_id>/` 按用户隔离

---

## 功能完成度（23/23）

| 模块 | 状态 | 说明 |
|:-----|:----:|:-----|
| 双路径流式引擎 | ✅ 100% | Anthropic SDK + OpenAI 兼容 |
| 技能系统（三态） | ✅ 100% | path / callable / composite |
| MCP 连接器（三协议） | ✅ 100% | stdio / sse / http |
| RAG 知识库 | ✅ 100% | ZVec + 自动检索 + 30+ 格式 |
| DAG 方案包 | ✅ 100% | 6 种节点 + 人工审批 |
| 工作流编辑器 | ✅ 100% | Vue Flow 拖拽编排 |
| 模板市场 | ✅ 100% | 5 个模板 + next_steps |
| 记忆系统 | ✅ 100% | 提取 + 去重 + 衰减 + 注入 |
| 上下文压缩 | ✅ 100% | LLM 自动摘要 |
| 自学习 | ✅ 100% | 定时分析 + prompt 改进 |
| 多 Agent 协作 | ✅ 100% | 通信 + 自动消费 + 三种编排 |
| RBAC | ✅ 100% | admin / operator / user |
| SSO/LDAP | ✅ 100% | LDAP + OIDC 完整回调 |
| 审计合规 | ✅ 100% | 双表 + 脱敏 + 操作审批 |
| 数据脱敏 | ✅ 100% | 邮箱 / 手机 / 身份证 |
| API 限流 | ✅ 100% | 令牌桶 + 路径匹配 |
| 配额控制 | ✅ 100% | 用户级月度额度 |
| 告警通知 | ✅ 100% | 规则引擎 + 钉钉/企微/飞书 Webhook |
| Dashboard | ✅ 100% | 7+3 图表 + CSV 导出 |
| 文件处理 | ✅ 100% | MinerU + 多格式预览 |
| 安全体系 | ✅ 100% | 7 层防护 |
| 前端重构 | ✅ 100% | 组件化 + 暗色主题 + ARIA |
| 移动端 | ✅ 100% | 独立 Vue 应用 |

---

## 截图

| 界面 | 预览 |
|:-----|:-----|
| **指挥中心** — 数字员工工位看板 | ![指挥中心](docs/images/智慧中心.png) |
| **架构总览** | ![架构图](docs/images/技术架构.png) |
| **对话界面** | ![对话](docs/images/对话界面.png) |

---

## 许可证

[MIT License](LICENSE) — 可自由使用、修改、分发。

## 社区

- 提交 [Issues](https://github.com/Sugers955/agent-mill/issues) 报告问题
- 提交 [Pull Requests](https://github.com/Sugers955/agent-mill/pulls) 贡献代码
