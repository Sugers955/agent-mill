---
layout: default
title: Features — Agent Mill
---

<style>
.lang-switch { text-align: right; margin: 12px 0; font-size: 14px; }
.lang-switch a { display: inline-block; padding: 4px 14px; border: 1px solid #d0d7de; border-radius: 6px; color: #0969da; text-decoration: none; margin: 0 2px; cursor: pointer; }
.lang-switch a.active { background: #0969da; color: #fff; border-color: #0969da; }
</style>

<div class="lang-switch">
  <a class="active" onclick="switchLang('en')">English</a>
  <a onclick="switchLang('zh')">中文</a>
</div>

<script>
function switchLang(lang) {
  var base = window.location.pathname.includes('/agent-mill/') ? '/agent-mill' : '';
  window.location.href = base + (lang === 'zh' ? '/zh/features.html' : '/features.html');
}
</script>

# 🏭 Agent Mill — Feature Showcase

This document walks through every major feature of Agent Mill with screenshots and explanations.

---

## 1. Command Center — Agent Workstation

The command center provides a real-time overview of all your AI agents, their status, and quick access to conversations and tasks.

| View | Description |
|:-----|:------------|
| **Grid View** | Card-based layout showing agent names, descriptions, status indicators |
| **Station View** | Visual office-desk diorama with dual monitors, status LEDs, and desk accessories |

**Key actions**: Start a conversation, create tasks, monitor agent health.

---

## 2. Multi-Tab Agent Editor

Each agent is configured through a professional 4-tab editor:

### Tab 1: Basic Info
- Avatar upload, unique code, display name, business description
- Enable/disable toggle, set as default agent

### Tab 2: Role & Prompt
- **Persona setting** — Define the agent's identity, responsibilities, and tone
- **Output constraints** — Format rules, compliance limits, tone guidelines

### Tab 3: Model & Compute
- Model selection (Claude, DeepSeek, Qwen, GLM, OpenAI)
- **Compute slider** — 5 levels from Lite to Max, with cost/efficiency guidance
- Advanced parameters: Temperature, max tokens, max turns

### Tab 4: Knowledge & Skills
- **Knowledge base binding** — Multi-select RAG knowledge bases
- **Skill mounting** — Tag-based skill management with quick-add from skill market
- **MCP connector binding** — Attach external tool connectors

---

## 3. Dual-Path Streaming Engine

Agent Mill's core technical differentiator — two streaming paths that produce identical SSE events:

| Provider | Streaming Mechanism |
|:---------|:-------------------|
| **Anthropic (Claude)** | Claude Agent SDK native SSE — true streaming with thinking + tool_use events |
| **OpenAI-compatible** | Custom tool_calls multi-turn loop (DeepSeek, Qwen, GLM, OpenAI) |

**SSE Event Order**: `meta → thinking → text → tool_use → tool_result → file → ui → error → done`

### What This Enables

- **Real-time token streaming** — No waiting for full response
- **Thinking display** — Collapsible "thinking card" showing Claude's reasoning
- **Tool execution trace** — Live step-by-step tool call visualization
- **Widget rendering** — Inline SVG charts, HTML forms, data tables
- **File generation** — Real-time file creation and preview

---

## 4. Skill System (Three Forms)

| Type | Description |
|:-----|:------------|
| **Path** | ZIP upload with SKILL.md + resource files. Ideal for complex business processes. |
| **Callable** | Python function direct import. Lightweight tools, rapid development. |
| **Composite** | YAML DAG step orchestration with conditional branching and parallel execution. |

### Security
- 9-rule shell injection pattern detection
- Python AST static analysis (blocks eval/exec/subprocess)
- Upload interception with audit logging

---

## 5. MCP Connector System

Three transport protocols to connect any external tool:

| Protocol | Use Case |
|:---------|:---------|
| **stdio** | Local subprocess tools (CLI, scripts) |
| **sse** | Server-Sent Events for long-running connections |
| **http** | Streamable HTTP for REST APIs |

**Management**: CRUD + connection test + tool list discovery + auto-generated Chinese summaries + per-agent isolation.

---

## 6. RAG Knowledge Base

| Stage | Technology |
|:------|:-----------|
| **Upload** | 30+ file formats (PDF, DOCX, XLSX, images, code) |
| **Parse** | MinerU engine with auto-fallback |
| **Chunk** | 500-char window, 50-char overlap |
| **Embedding** | OpenAI-compatible API (text-embedding-3-small) |
| **Vector Store** | ZVec (Alibaba, Rust kernel, embedded — no extra containers) |
| **Retrieval** | Cosine similarity, configurable top_k |

**Auto-injection**: Every conversation turn automatically retrieves relevant knowledge and injects it into the system prompt.

---

## 7. Multi-Agent Collaboration

| Mode | Description |
|:-----|:------------|
| **Sequential** | Agent1 → Agent2 → ... → AgentN |
| **Parallel** | All agents process simultaneously |
| **MapReduce** | Individual processing → aggregation |

**Communication**: Asynchronous message passing with priority support (normal/high), message delegation, and auto-consumption polling.

---

## 8. Workflow & Solution Pack Editor

- **Vue Flow canvas** — Drag-and-drop workflow editor
- **6 node types**: skill, parallel_group, aggregator, condition, sub_agent, human_approval
- **Persistence**: Each node writes to DB on execution
- **Resumability**: Breakpoint recovery for failed workflows
- **Human approval**: Pause and wait for manual approval
- **Execution trace**: Complete run history

---

## 9. Dashboard & Analytics

- **7+3 ECharts charts**: Token trend, user top 10, agent distribution, model cost, department stats, agent effectiveness, latency trend, error rate trend, system health
- **Token detail**: Paginated query with user/agent/model/date filtering, CSV export
- **4-tab layout**: Overview, users, cost, performance

---

## 10. Enterprise Features

| Feature | Description |
|:--------|:------------|
| **RBAC** | Three roles: admin/operator/user |
| **SSO/LDAP** | LDAP bind + OIDC full callback flow |
| **Audit Logs** | Dual-table: admin operations + call logs |
| **Data Masking** | Auto-mask email/phone/ID card in logs |
| **Rate Limiting** | Token bucket per-path |
| **Quota Control** | User-level monthly token/cost limits |
| **Alert Notifications** | Rule engine + DingTalk/WeChat/Feishu webhooks |

---

## 11. Mobile App

Independent Vue 3 application at `/m.html` with:
- Hash-based routing (fully separate from desktop)
- Dedicated stores, views, and styles
- Core chat, task management, notification, and space features

---

## 12. File Processing

| Format | Engine |
|:-------|:-------|
| TXT/MD/CSV/JSON/HTML/XML/YAML | Direct read |
| PDF | MinerU → pypdf fallback |
| DOCX | MinerU → python-docx fallback |
| XLSX | MinerU → openpyxl fallback |
| Images | MinerU OCR |

**Preview**: HTML iframe, PDF native, Markdown, code, SVG, images (JWT-secured with expiring tokens).

---

## Complete Module Checklist

| # | Module | Status |
|:--|:-------|:------:|
| 1 | Dual-path Streaming (Anthropic + OpenAI) | ✅ |
| 2 | Skill System (path/callable/composite) | ✅ |
| 3 | MCP Connector (stdio/sse/http) | ✅ |
| 4 | RAG Knowledge Base | ✅ |
| 5 | DAG Solution Pack | ✅ |
| 6 | Workflow Editor (Vue Flow) | ✅ |
| 7 | Template Market | ✅ |
| 8 | Memory System | ✅ |
| 9 | Context Compression | ✅ |
| 10 | Self-Learning | ✅ |
| 11 | Multi-Agent Collaboration | ✅ |
| 12 | RBAC | ✅ |
| 13 | SSO/LDAP | ✅ |
| 14 | Audit & Compliance | ✅ |
| 15 | Data Masking | ✅ |
| 16 | API Rate Limiting | ✅ |
| 17 | Quota Control | ✅ |
| 18 | Alert Notifications | ✅ |
| 19 | Dashboard & Analytics | ✅ |
| 20 | File Processing | ✅ |
| 21 | Security (7 layers) | ✅ |
| 22 | Mobile App | ✅ |
