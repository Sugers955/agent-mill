# Agent Forge 智能体平台

基于 [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk) 的企业级 SaaS 智能体平台。一套后台,支持多个智能体,管理员配置、普通用户使用,提供完整的 Skill / MCP / 模型 / 文件 / 安全 / 审计 闭环。

- **后端**:FastAPI · SQLAlchemy 2.0 (async) · PostgreSQL · Claude Agent SDK · OpenAI Python SDK
- **前端**:Vue 3 · Vite · TypeScript · Pinia · Element Plus
- **AI 解析**:[MinerU](https://mineru.net) 云端/私有化双模式 + 本地 Python 库 fallback

---

## 一、功能总览

| 模块 | 关键能力 |
|---|---|
| **认证 / 权限** | 本地账号 + JWT(access + refresh)+ RBAC 三角色(admin / operator / user)+ 部门(用户分组)+ Agent 角色可见性 |
| **智能体** | 多智能体 / 默认智能体 / 模型 + 降级模型 / 挂载 Skill 与 MCP / 角色可见性 / 文件上传策略 / system_prompt |
| **模型管理** | Anthropic / DeepSeek / Qwen / GLM / OpenAI / 任意 OpenAI 兼容,API Key Fernet 加密存储,extra_params 透传(如关思考),一键测试 |
| **Skill 仓库** | path 型(SKILL.md 包)/ composite(YAML DAG)/ callable(Python 函数)三种类型;ZIP 包上传 + 静态扫描;在线浏览文件树 + Markdown 在线编辑保存;按 Agent 文件级隔离(per-agent .claude/skills/ 沙箱);跨路径调度(`save_output_file` / `_read_skill_file` / `run_skill_script`) |
| **MCP 连接器** | stdio / SSE / Streamable-HTTP 三种 transport;管理端实时连接 + 列举工具 + 输入 schema 展示;按 Agent 隔离;运行时按需注入 |
| **聊天与流式** | 多会话 + 历史持久化 + 多轮上下文(默认 30 条)+ 真·token-by-token 流式(Claude Agent SDK partial messages);思考过程独立 thinking 卡片(支持 DeepSeek-Reasoner reasoning_content);工具/MCP/Skill 调用步骤卡片实时展示 |
| **文件上传与解析** | 用户在对话框上传(per-user 物理隔离)→ 异步解析 → MinerU 云端/私有化 → 失败回退本地库(pypdf/python-docx/openpyxl/bs4)→ Markdown 注入 prompt;支持多次引用、解析中可见状态、失败可重试 |
| **文件预览与下载** | 类 Gemini Canvas 右侧分屏;HTML / PDF / Markdown / SVG / 图片 / 文本代码 在线预览;Word / PPT / Excel 仅下载;一次性 token URL,跨用户/过期/路径穿越全 block;Skill 产物自动登记下载链接 |
| **生成式 UI** | Skill 输出嵌入式 Widget 渲染(向智能体回拨消息);右侧分屏可拖动尺寸 |
| **安全加固** | Anthropic 路径默认禁 Bash/Write/Edit;system_prompt 注入安全规则;输入正则过滤(injection / shell);Skill 上传静态扫描(AST 级危险 import 黑名单);文件级 cwd 沙箱(per-agent symlink);所有 admin / 工具调用 / 文件 操作埋点审计 |
| **审计与日志** | `call_logs`(token/延迟/状态)+ `audit_logs`(管理操作 / 安全拦截 / 文件下载)双表,管理端筛选查询 |
| **生命周期** | 文件 30 天未引用自动清理;Conversation 删除级联消息;UploadedFile last_used_at 跟踪 |
| **生产部署** | Docker Compose 一键起 db/api/web;`storage/` 卷持久化 |

---

## 二、目录结构

```
h3c-agent/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── auth.py                  登录 / 刷新 / me
│   │   │   ├── chat.py                  会话 / 消息 / SSE 流式
│   │   │   ├── files.py                 上传 / 异步解析 / 状态查询 / 重试 / raw 直链
│   │   │   ├── downloads.py             token URL 下载(Skill 产物)
│   │   │   └── admin/
│   │   │       ├── users.py             用户 + 角色 CRUD
│   │   │       ├── departments.py       部门树
│   │   │       ├── models.py            模型管理 + 测试
│   │   │       ├── mcp.py               MCP 连接器 + 工具列表
│   │   │       ├── skills.py            Skill ZIP 上传 / 文件树 / 在线编辑 / 静态扫描
│   │   │       ├── agents.py            Agent 配置 (含上传策略)
│   │   │       └── logs.py              call/audit 日志
│   │   ├── core/
│   │   │   ├── config.py                env 配置(MinerU / JWT / 上传等)
│   │   │   ├── crypto.py                Fernet 加密(API Key)
│   │   │   ├── security.py              JWT / bcrypt
│   │   │   └── security_rules.py        SAFETY_PREFIX + 输入过滤正则
│   │   ├── runtime/
│   │   │   ├── agent_runner.py          双路径流式(Anthropic SDK + OpenAI 兼容);Skill/MCP/file 编排;widget 协议;tool-use 状态卡
│   │   │   ├── skill_loader.py          composite YAML 校验 + DAG 拓扑
│   │   │   ├── dag_executor.py          DAG 并行执行 + 模板变量
│   │   │   ├── mcp_manager.py           MCP 客户端工厂
│   │   │   └── widget_guidelines.py     生成式 UI 指南
│   │   ├── services/
│   │   │   ├── audit.py                 审计辅助
│   │   │   ├── downloads.py             下载令牌登记 / 校验
│   │   │   ├── file_cleanup.py          30 天 orphan 清理(后台 task)
│   │   │   ├── file_parser.py           解析路由(text / MinerU / 本地库)
│   │   │   ├── mineru_client.py         MinerU 云端/本地双模式
│   │   │   └── skill_scan.py            shell + Python AST 扫描
│   │   ├── db/
│   │   │   ├── models.py                14+ 表
│   │   │   └── init_db.py               幂等迁移 + 默认 admin
│   │   ├── schemas/                     Pydantic
│   │   ├── deps.py                      JWT 依赖 + 角色守卫
│   │   └── main.py                      入口 + lifespan(挂载清理任务)
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── views/
│   │   │   ├── chat/Chat.vue            对话页(50/50 分屏 / 思考块 / 步骤卡 / 文件 chip / 预览面板)
│   │   │   ├── admin/                   8 个管理页
│   │   │   ├── Layout.vue               左侧 NavigationRail + Topbar
│   │   │   └── Login.vue                Glassmorphism 登录页
│   │   ├── components/
│   │   │   ├── FileCard.vue             文件卡片(下载 / 预览)
│   │   │   ├── PreviewPanel.vue         右侧分屏多类型渲染
│   │   │   └── WidgetRenderer.vue       生成式 UI Widget
│   │   ├── api/                         统一 axios 封装 + 拦截
│   │   ├── stores/                      Pinia(auth + chat)
│   │   ├── router/                      路由 + 角色守卫
│   │   └── styles.css                   Material 3 token + Google 蓝/红/黄/绿
│   ├── vite.config.ts                   含 SSE 反代禁缓冲
│   └── Dockerfile
├── storage/
│   ├── uploads/<user_id>/               用户上传(物理隔离)
│   ├── outputs/<user_id>/               Skill / 工具产物
│   └── skills/<code>/                   path 型 Skill 包
└── docker-compose.yml
```

---

## 三、核心机制

### 3.1 角色与可见性

| 角色 | 权限 |
|---|---|
| **admin** | 全部:用户 / 角色 / 部门 / Agent / Skill / MCP / 模型 / 日志 + 使用 |
| **operator** | 配置 Skill / MCP / Agent / 模型 + 查看日志 + 使用,**不能管用户/角色/部门** |
| **user** | 仅使用 chat;能看到的 Agent 通过 `role_agent_grants` 控制 |

### 3.2 双流式路径

**Anthropic 路径**(provider=anthropic)
- 使用 Claude Agent SDK,`include_partial_messages=True` 走 `content_block_delta` 真流式
- 文件级 Skill 沙箱:`<tmp>/.claude/skills/` 仅符号链接当前 Agent 选中的 Skill
- 工具白名单:Read / Glob / Grep / Skill / WebSearch / `mcp__<server>` —— Bash/Write/Edit 全局禁

**OpenAI 兼容路径**(provider=deepseek/qwen/glm/openai/openai-compatible)
- `/v1/chat/completions` stream + `tool_calls`
- 多轮 function-calling 循环(MAX 8 轮)
- DeepSeek-Reasoner `reasoning_content` 自动回传
- MCP / Skill 都翻译成 OpenAI function tools,运行时路由

### 3.3 Skill 三态

| 类型 | 形态 | 执行方式 |
|---|---|---|
| **path 型 atomic** | ZIP 上传 → SKILL.md + 资源文件 | Anthropic SDK 通过 cwd 文件级加载;OpenAI 路径模型先调 `_read_skill_file` 加载 SKILL.md,再用 `run_skill_script` 调内含 Python(in-process,无 Bash) |
| **callable atomic** | source_json.callable: `module.path:func` | 直接 import 调用(admin 才能创建,有 audit) |
| **composite (YAML DAG)** | 步骤 + depends_on + 模板变量 | DAGExecutor 拓扑分层 + 同层并行,变量替换不走 eval |

每次请求:`storage/skills/<code>/` 的 Skill 按 Agent 选择 symlink 进 `tmp/.claude/skills/` —— 物理沙箱,Read/Bash 也跨不到别的 Skill。

### 3.4 文件解析

```
TXT/MD/CSV/JSON/HTML/...  → 直接读
PDF/DOCX/PPTX/XLSX/PNG/JPG → MinerU(云端/私有化)→ 失败回退本地库
其它                       → 标记 failed,可重试
```

- MinerU 云端流程:申请预签名 URL → PUT 上传 → 轮询 batch 结果 → 拿 markdown
- 私有化部署只改三个 env(`MINERU_MODE=local`、`MINERU_BASE_URL`、`MINERU_API_KEY`),业务代码零侵入
- 解析硬上限 20K 字符,超长截头尾省中间

### 3.5 文件下载与预览

- 上传文件:`/api/files/{id}/raw` + 双通道鉴权(Bearer 头 / `?t=<jwt>` query)
- Skill / 工具产物:`download_tokens` 表登记 + `/api/downloads/{token}` 短 URL
- 跨用户访问 / 过期 / 路径穿越 全部 block
- 右侧分屏渲染:HTML iframe / PDF 浏览器原生 / Markdown 渲染 / 文本代码块 / SVG 内嵌 / 图片;Office 仅下载

### 3.6 安全加固(分层)

1. **工具白名单**(运行时层):Anthropic 路径默认禁 Bash/Write/Edit
2. **system_prompt 安全前缀**(模型层):每个 Agent 强制注入,反 prompt injection
3. **输入正则过滤**(网关层):shell 命令、injection 套路、敏感路径模式 → 直接 400 + 审计
4. **Skill 静态扫描**(上传时):shell pattern + Python AST(eval/exec/subprocess/os.system 黑名单)
5. **文件 cwd 沙箱**(SDK 层):per-agent 临时 dir,模型物理上看不到别的 Skill
6. **下载令牌**(出口层):一次性 token / 24h 过期 / user_id 校验 / 路径穿越拒绝
7. **API Key 加密**:Fernet 存 DB,前端只看到 `has_api_key`

### 3.7 审计

| 表 | 用途 |
|---|---|
| `audit_logs` | 管理 CRUD + 文件上传/下载/重解析 + 输入过滤命中 + Skill 上传拦截 |
| `call_logs` | 每次对话:token in/out / 延迟 / 状态 / 错误 / 模型 |

管理端日志页支持按用户 / Agent 筛选 + 翻页 + 详情 JSON 展开。

---

## 四、快速开始

### 4.1 一键启动 / 停止（推荐日常开发使用）

```bash
# 在仓库根目录
./start.sh        # 启动 backend (8000) + frontend (5173)
./stop.sh         # 停止所有服务

# 实时查看日志
tail -f /tmp/agent-forge-backend.log
tail -f /tmp/agent-forge-frontend.log
```

`start.sh` 会先 kill 旧进程，再以 `--reload` 模式起后端、`vite dev` 起前端。脚本要求：
- 后端虚拟环境已建在 `backend/.venv/`
- 前端 `node_modules` 已 `npm install` 过

首次跑请先看 4.2 完成依赖安装与建表。

### 4.2 本地开发（首次安装）

```bash
# 1. PostgreSQL
docker run -d --name h3c-pg -p 5432:5432 \
  -e POSTGRES_USER=h3c -e POSTGRES_PASSWORD=h3c -e POSTGRES_DB=h3c_agent \
  postgres:16

# 2. 后端
cd backend
python -m venv .venv && source .venv/bin/activate
cp .env.example .env
# 编辑 .env 填入:
#   - JWT_SECRET / ENCRYPTION_KEY (任意 base64 32 字节)
#   - MINERU_API_KEY (mineru.net 申请)
pip install -e .
python -m app.db.init_db          # 建表 + 默认 admin / admin123
uvicorn app.main:app --reload --port 8000

# 3. 前端
cd ../frontend
npm install
npm run dev                        # http://localhost:5173
```

### 4.3 Docker Compose

```bash
docker-compose up -d --build
docker-compose exec api python -m app.db.init_db
```

### 4.4 关键 env

```bash
# 数据库
DATABASE_URL=postgresql+asyncpg://h3c:h3c@localhost:5432/h3c_agent

# 鉴权
JWT_SECRET=<32+ 字节随机>
ENCRYPTION_KEY=<Fernet 32 字节>

# MinerU(云端)
MINERU_MODE=cloud                  # cloud | local | disabled
MINERU_BASE_URL=https://mineru.net
MINERU_API_KEY=<token>
MINERU_TIMEOUT_SEC=60

# MinerU(私有化,后期切换)
MINERU_MODE=local
MINERU_BASE_URL=http://10.0.0.50:8000
MINERU_API_KEY=                    # 私有化通常不需要

# 文件
MAX_UPLOAD_MB=50
PARSED_MARKDOWN_HARD_LIMIT=20000
```

---

## 五、API 速查

### 用户端

```
POST   /api/auth/login                              登录
POST   /api/auth/refresh                            刷新 token
GET    /api/auth/me                                 当前用户

GET    /api/agents                                  我可用的 Agent
GET    /api/agents/default                          我的默认 Agent
GET    /api/agents/{id}/capabilities                Agent 能力(模型/Skill/MCP)
GET    /api/agents/{id}/mcps/{mid}/tools            实时拉取该 Agent 某 MCP 的工具列表

GET    /api/conversations                           我的会话
POST   /api/conversations                           新建会话
PATCH  /api/conversations/{id}                      重命名
DELETE /api/conversations/{id}                      删除
GET    /api/conversations/{id}/messages             消息列表(自动 hydrate 文件)
POST   /api/conversations/{id}/messages             发消息(SSE 流)

POST   /api/files/upload                            上传文件(后台异步解析)
GET    /api/files/{id}                              查解析状态
POST   /api/files/{id}/reparse                      重试解析
DELETE /api/files/{id}                              删除
GET    /api/files/{id}/raw                          原始文件流(支持 ?t= 直链)
GET    /api/downloads/{token}                       Skill 产物下载(token URL)
```

### 管理端(`/api/admin/`)

```
roles            users           departments        # 用户体系
models                                              # 模型 + /test
mcp              + /{id}/ping  + /{id}/tools        # MCP
skills           + /upload  + /{id}/files  + /{id}/file (PUT 在线编辑)
agents
logs/calls       logs/audit                         # 双日志
```

### SSE 事件类型

```
meta          首次响应,带 agent/model/provider
thinking      思考过程 token(可折叠)
text          正文 token(流式)
tool_use      工具调用开始(状态卡)
tool_result   工具返回(状态卡 done)
file          文件产物登记(下载卡片)
error         流式错误
done          结束 + token 用量 + 延迟
```

---

## 六、数据模型(主要表)

```
roles, users, departments
role_agent_grants                    用户角色 → Agent 可见

models                               provider + api_key_enc + extra_params
mcp_connectors
skills                               type ∈ {atomic, composite}

agents                               default_model_id + system_prompt + upload_policy_json
agent_skills, agent_mcps             多对多

conversations                        user × agent
messages                             content_json(text/thinking/files) + tool_calls_json

uploaded_files                       parse_status / parsed_markdown / parsed_chars / last_used_at
download_tokens                      token + expires_at + user_id

audit_logs                           who / action / target / detail_json
call_logs                            tokens / latency / status
```

---

## 七、二次开发指引

| 我想... | 改这里 |
|---|---|
| 接新模型供应商 | `agent_runner.py:_stream_via_openai` provider 路由(已通 OpenAI 兼容协议)+ 前端 `Models.vue` PROVIDERS 数组 |
| 加新文件类型解析 | `services/file_parser.py:_local_for_ext` + `MINERU_EXTS` |
| 私有化 MinerU | 改 env;若接口形状不同,改 `services/mineru_client.py` 单文件 |
| 新增 Skill 工具 | `agent_runner.py:_build_openai_tools` 加 function 定义 + `_exec_skill` 加分派 |
| 加自定义安全规则 | `core/security_rules.py` 加正则 |
| 新增预览类型 | `components/PreviewPanel.vue` + `FileCard.vue` PREVIEWABLE 集合 |

---

## 八、生产前 Checklist

- [ ] 替换 `JWT_SECRET` 为 32+ 字节随机
- [ ] 生成 `ENCRYPTION_KEY`(`python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"`)
- [ ] 开启 HTTPS(SSE 流式 nginx 已配 `proxy_buffering off`)
- [ ] 改 admin 默认密码
- [ ] 设置全局 `MAX_UPLOAD_MB`、按 Agent 配 `max_size_mb` / `max_files_per_send`
- [ ] 给关键 Agent 配 `allowed_ext` 白名单
- [ ] 验证 MinerU 配额 / 切私有化部署
- [ ] 定期备份 `storage/` 卷 + Postgres
- [ ] 检查日志页(管理端)看是否有 `input_filter_blocked` / `skill.upload_blocked` 异常爆点

---

## 九、版本规划

**MVP(已完成)**
- 双路径流式 / Skill 三态 / MCP 三 transport / MinerU 解析 / 文件预览 / 安全加固 / 审计

**Phase 2**
- 子 Agent 委托(主-从架构)
- 配额 / 成本控制
- SSO 接入(OIDC / LDAP)
- S3 / MinIO 文件存储
- Skill 市场(导出/导入)
- 流量限速 / 异常告警

---

## 十、致谢

- [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk) — 智能体核心
- [MinerU](https://mineru.net) — 文档解析
- [Element Plus](https://element-plus.org) — UI 组件
