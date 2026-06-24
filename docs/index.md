---
layout: default
title: Agent Mill — Your Digital Worker Factory
---

<style>
.lang-switch { text-align: right; margin: 12px 0; font-size: 14px; }
.lang-switch a { display: inline-block; padding: 4px 14px; border: 1px solid #d0d7de; border-radius: 6px; color: #0969da; text-decoration: none; margin: 0 2px; cursor: pointer; }
.lang-switch a.active { background: #0969da; color: #fff; border-color: #0969da; }
.lang-block { display: none; }
.lang-block.active { display: block; }
.hero { text-align: center; padding: 40px 0 20px; }
.hero p { font-size: 1.15em; color: #586069; margin-top: 8px; }
.cta { margin: 24px 0; }
.cta .btn { display: inline-block; padding: 10px 24px; margin: 4px 6px; border-radius: 6px; text-decoration: none; font-weight: 500; }
.cta .btn-primary { background: #0969da; color: #fff; }
.cta .btn-secondary { background: #f6f8fa; color: #24292f; border: 1px solid #d0d7de; }
.screenshots { text-align: center; margin: 16px 0; }
.screenshots img { max-width: 100%; border: 1px solid #d0d7de; border-radius: 8px; }
.features { column-count: 2; column-gap: 24px; }
footer { text-align: center; padding: 20px 0; color: #586069; font-size: 0.9em; }
table { width: 100%; border-collapse: collapse; }
table th, table td { padding: 8px 12px; border: 1px solid #d0d7de; text-align: left; }
table th { background: #f6f8fa; font-weight: 600; }
</style>

<div class="lang-switch">
  <a class="active" onclick="switchLang('en')">English</a>
  <a onclick="switchLang('zh')">中文</a>
</div>

<script>
function switchLang(lang) {
  document.querySelectorAll('.lang-block').forEach(el => el.classList.remove('active'));
  document.getElementById('lang-' + lang).classList.add('active');
  document.querySelectorAll('.lang-switch a').forEach(el => el.classList.remove('active'));
  document.querySelector(`.lang-switch a[onclick*="${lang}"]`).classList.add('active');
}
</script>

<div id="lang-en" class="lang-block active">

<div class="hero">
  <p style="font-size:2em;font-weight:700;margin:0">🏭 Agent Mill</p>
  <p>Your Digital Worker Factory — Enterprise AI Agent Platform</p>
  <div class="cta">
    <a href="https://github.com/Sugers955/agent-mill" class="btn btn-primary">View on GitHub</a>
    <a href="#quick-start-en" class="btn btn-secondary">Quick Start</a>
  </div>
</div>

---

## What is Agent Mill?

Agent Mill is an **out-of-the-box enterprise AI agent platform**. Build intelligent assistants with tool calling, knowledge retrieval, file processing, and multi-agent collaboration within 10 minutes.

---

## ⚡ Powered by Claude Agent SDK

Agent Mill is one of the first open-source platforms to integrate **Anthropic's Claude Agent SDK** — the same SDK powering Claude.ai's agentic features.

| Capability | What It Enables |
|:-----------|:----------------|
| **True SSE Streaming** | Real-time token-by-token streaming with thinking process, tool calls, and results |
| **Native Tool Use Loop** | Claude's built-in tool orchestration — no fragile custom loops |
| **Extended Thinking** | Full access to Claude's reasoning process, displayed in the chat UI |
| **Widget Rendering** | Claude generates interactive SVG charts, HTML forms inline |
| **Multi-Turn Autonomy** | Claude decides when to call tools, ask questions, or deliver answers |
| **Safety Guardrails** | Built-in tool use safety layers |

> For non-Anthropic providers (DeepSeek, Qwen, OpenAI), Agent Mill provides an equivalent **OpenAI-compatible tool_calls loop** with unified SSE streaming.

## Screenshots

| Command Center | Chat Interface |
|:--------------:|:--------------:|
| ![](https://raw.githubusercontent.com/Sugers955/agent-mill/main/docs/images/%E6%99%BA%E6%85%A7%E4%B8%AD%E5%BF%83.png) | ![](https://raw.githubusercontent.com/Sugers955/agent-mill/main/docs/images/%E5%AF%B9%E8%AF%9D%E7%95%8C%E9%9D%A2.png) |

---

## Core Capabilities

- 🤖 **Agent Management** — Bind models, skills, MCP tools, and knowledge bases per agent
- 🛠️ **Skill System** — path/callable/composite three forms
- 🔌 **MCP Connector** — stdio/sse/http three protocols
- 📚 **RAG Knowledge Base** — Upload → Parse → Vector Search → Auto-Injection
- 🔄 **Multi-Agent Collaboration** — Sequential/Parallel/MapReduce orchestration

---

## Problems It Solves

| Enterprise Pain Point | Agent Mill's Solution |
|:----------------------|:----------------------|
| AI models scattered | Unified model gateway for all LLM providers |
| Knowledge can't be retrieved | RAG knowledge base with auto document injection |
| Need to call internal APIs | MCP connectors, 3 protocols |
| Reconfiguring AI every time | Agent templates, configure once and reuse |
| Data security concerns | 3-role RBAC + SSO/LDAP + audit logs |
| AI collaboration needed | Multi-agent orchestration |
| Mobile access needed | Standalone mobile app |

---

## Quick Start {#quick-start-en}

```bash
git clone https://github.com/Sugers955/agent-mill.git
cd agent-mill
cp .env.example .env
make dev
```

> http://localhost:5173 — `admin` / `Admin@2026`

---

## Tech Stack

| Layer | Technology |
|:------|:-----------|
| Backend | Python 3.11+ / FastAPI / SQLAlchemy 2.0 |
| Frontend | Vue 3 / TypeScript / Vite / Element Plus |
| AI SDK | Claude Agent SDK (Anthropic) + OpenAI SDK |
| Database | MySQL 8.0 |
| Vector | ZVec (Alibaba, Rust) |
| Streaming | SSE dual-path |
| Deploy | Docker Compose |

---

## License

[MIT License](https://github.com/Sugers955/agent-mill/blob/main/LICENSE)

</div>

<div id="lang-zh" class="lang-block">

<div class="hero">
  <p style="font-size:2em;font-weight:700;margin:0">🏭 Agent Mill</p>
  <p>你的数字员工工厂 — 企业级 AI 数字员工平台</p>
  <div class="cta">
    <a href="https://github.com/Sugers955/agent-mill" class="btn btn-primary">查看 GitHub</a>
    <a href="#quick-start-zh" class="btn btn-secondary">快速开始</a>
  </div>
</div>

---

## 这是什么？

Agent Mill 是一个**开箱即用的企业级数字员工平台**。10 分钟内搭建一个能调用工具、检索知识库、处理文件、多 Agent 协作的智能助手。

---

## ⚡ 核心引擎：Claude Agent SDK

Agent Mill 是首批集成 **Anthropic Claude Agent SDK** 的开源平台——这是驱动 Claude.ai 智能体能力的同一套 SDK。

| 能力 | 作用 |
|:-----|:-----|
| **真流式 SSE** | 实时逐 token 输出，含思考过程和工具调用 |
| **原生工具编排** | Claude 内置引擎自动处理技能/MCP/文件操作 |
| **扩展思考** | 完整展示推理过程，可折叠「思考卡片」 |
| **Widget 渲染** | Claude 直接生成交互式 SVG 和 HTML |
| **多轮自主决策** | 自主决定工具调用时机 |
| **安全护栏** | 内置工具使用安全层 |

> 非 Anthropic 供应商（DeepSeek、千问、OpenAI）使用等效的 **OpenAI 兼容 tool_calls 循环**，统一 SSE 协议。

---

## 核心能力

- 🤖 **数字员工管理** — 绑定模型/技能/MCP/知识库
- 🛠️ **技能系统** — path / callable / composite 三态
- 🔌 **MCP 连接器** — stdio / sse / http 三协议
- 📚 **RAG 知识库** — 上传文档 → 自动检索注入
- 🔄 **多 Agent 协作** — 顺序/并行/MapReduce 编排

---

## 快速开始 {#quick-start-zh}

```bash
git clone https://github.com/Sugers955/agent-mill.git
cd agent-mill
cp .env.example .env
make dev
```

> http://localhost:5173 — 账号 `admin` / `Admin@2026`

---

## 技术栈

| 层级 | 技术 |
|:-----|:-----|
| 后端 | Python 3.11+ / FastAPI / SQLAlchemy 2.0 |
| 前端 | Vue 3 / TypeScript / Vite / Element Plus |
| AI SDK | Claude Agent SDK (Anthropic) + OpenAI SDK |
| 数据库 | MySQL 8.0 |
| 向量引擎 | ZVec（阿里巴巴，Rust） |
| 流式 | SSE 双路径 |
| 部署 | Docker Compose |

---

## 许可证

[MIT License](https://github.com/Sugers955/agent-mill/blob/main/LICENSE)

</div>

<footer>
  <a href="https://github.com/Sugers955/agent-mill">GitHub</a> ·
  <a href="https://github.com/Sugers955/agent-mill/issues">Issues</a>
  <br><br>Made with ❤️ for the open-source community
</footer>
