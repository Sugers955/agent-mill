# H3C Agent 智能体平台

一个基于 Claude Agent SDK 的 SaaS 智能体平台。

- **后端**: FastAPI + SQLAlchemy + PostgreSQL + Claude Agent SDK
- **前端**: Vue 3 + Vite + Element Plus
- **角色**: 超级管理员 / 运营管理员 / 普通用户
- **核心能力**: 多智能体管理、Skill (原子 + YAML DAG 组合)、MCP、模型切换、文件上传、流式对话、审计/调用日志

## 快速开始 (本地开发)

### 1. 启动 PostgreSQL

```bash
docker run -d --name h3c-pg -p 5432:5432 \
  -e POSTGRES_USER=h3c -e POSTGRES_PASSWORD=h3c -e POSTGRES_DB=h3c_agent \
  postgres:16
```

### 2. 启动后端

```bash
cd backend
cp .env.example .env
# 生成加密密钥(可选)
python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"
# 把输出贴到 .env 的 ENCRYPTION_KEY

pip install -e .
python -m app.db.init_db   # 建表 + 默认管理员
uvicorn app.main:app --reload --port 8000
```

默认管理员: `admin` / `admin123`

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

打开 http://localhost:5173

## Docker Compose 一键部署

```bash
docker-compose up -d --build
docker-compose exec api python -m app.db.init_db
```

访问 http://localhost:5173

## 核心目录

```
backend/
  app/
    api/           HTTP 路由
      admin/       管理端 CRUD
    core/          配置、安全、加密
    db/            ORM + 迁移
    runtime/       Skill 加载器、DAG 执行器、SDK 封装、MCP 管理
    schemas/       Pydantic
frontend/
  src/
    views/chat/    用户聊天界面
    views/admin/   管理端
storage/
  skills/          原子 Skill 目录
  uploads/         用户上传文件
```

## Skill 类型

### 原子 Skill (`type: atomic`)

两种来源:

- **目录式**: `source_json: { "path": "/path/to/skill_dir" }` — 由 Claude Agent SDK 直接加载
- **Python 调用**: `source_json: { "callable": "module.path:func" }` — 在进程内导入并调用

### 组合 Skill (`type: composite`)

YAML 定义的 DAG。被编译成虚拟 Skill 暴露给 Agent,触发时由内置 DAG 执行器按 `depends_on` 拓扑顺序执行,同层并行。

```yaml
name: contract_review_flow
description: 合同审查流程
steps:
  - id: extract
    skill: pdf_extract
    input:
      file: "{{trigger.file}}"
  - id: analyze
    skill: llm_call
    depends_on: [extract]
    input:
      text: "{{extract.value}}"
```

模板变量 `{{step_id.field}}` 仅做结构化字段替换,不进行 eval。

## API 摘要

```
POST /api/auth/login                       登录
GET  /api/auth/me                          当前用户

GET  /api/agents                           我可用的智能体
GET  /api/conversations                    我的会话
POST /api/conversations                    新建会话
POST /api/conversations/{id}/messages      发消息 (SSE 流)

POST /api/files/upload                     上传文件

# 管理端 (admin / operator)
CRUD /api/admin/{users,models,mcp,skills,agents}
GET  /api/admin/logs/{calls,audit}
```

## 后续路线 (Phase 2)

- 子 Agent 委托 (层次三)
- 成本/配额管控
- SSO (OIDC/LDAP)
- S3/MinIO 存储
- Skill 市场
