> 产品思考见 [docs/insights/why-raw-file-mode.md](../insights/why-raw-file-mode.md)

# 文件原始直传（parse_mode=never）

## 背景
默认情况下，用户在对话框上传的文件会被 `parse_uploaded_file` 异步解析为 markdown，并在发送时拼到 prompt 里塞给模型。但部分场景（盖章 PDF、需 OCR 截图、二进制专用格式等）需要把**原始文件**交给 skill 或 MCP 工具直接处理，文本提取没有意义甚至有害。

## 设计

### 1. Agent 层开关
Agent 的 `upload_policy_json` 新增字段：
```json
{ "parse_mode": "auto" | "never" }
```
- `auto`（默认）：保持现有解析行为，向后兼容
- `never`：上传时 `parse_status` 直接置为 `"skipped"`，不调用解析后台任务

### 2. 文件状态
`UploadedFile.parse_status` 新增枚举值 `"skipped"`。其它已有值：`parsing` / `done` / `failed` 不变。

### 3. 数据流

| 阶段 | 文件 | 落库字段 | 给模型的 prompt 形态 |
|---|---|---|---|
| 上传 | parse_mode=auto | parse_status=parsing → done | 完整解析后的 markdown |
| 上传 | parse_mode=never | parse_status=skipped | 本地路径 + 短期签名 URL |
| 发送 | skipped 文件 | chat.py 注入 `raw_url` + `path` 到 files[] | `_render_attachments` 输出"原始文件直传"块 |

### 4. 关键文件

| 文件 | 改动 |
|---|---|
| [backend/app/api/files.py](../../backend/app/api/files.py) | upload 根据 `parse_mode` 决定是否调度解析；`/raw` 接受 file-scoped token |
| [backend/app/core/security.py](../../backend/app/core/security.py) | 新增 `create_file_token(file_id, user_id, minutes=30)` |
| [backend/app/core/config.py](../../backend/app/core/config.py) | 新增 `BACKEND_BASE_URL`，缺省回退到 `APP_BASE_URL` |
| [backend/app/api/chat.py](../../backend/app/api/chat.py) | 对 skipped 文件生成签名 URL 并附加 `raw_url` / `id` |
| [backend/app/runtime/agent_runner.py](../../backend/app/runtime/agent_runner.py) | `_render_attachments` 为 skipped 文件输出 path/url 引导段 |
| [frontend/src/views/admin/Agents.vue](../../frontend/src/views/admin/Agents.vue) | 表单新增"文件解析模式"单选 |
| [frontend/src/views/chat/Chat.vue](../../frontend/src/views/chat/Chat.vue) | 文件 chip 显示"原始文件"状态 |
| [frontend/src/mobile/views/Chat.vue](../../frontend/src/mobile/views/Chat.vue) | 移动端同上 |

### 5. Token 协议
| 字段 | 值 |
|---|---|
| type | `"file"` |
| sub | user_id |
| file_id | 文件 id |
| exp | 默认 60 分钟（chat 注入时） |

`/api/files/{id}/raw` 在 `_resolve_caller_dual` 中判断：若 token type 是 `"file"`，必须满足 `file_id == 路径中的 file_id`，从而做到"单文件、单用户、短时效"。

### 6. skill / MCP 调用方式
模型在 prompt 里会看到形如：
```
### 📎 报价单.pdf  · 原始文件直传 (mime=application/pdf, size=128345B)
- 本地路径(供 skill 脚本读取): `/data/uploads/3/abcd.pdf`
- 下载 URL(供 MCP / 远程工具拉取): `https://host/api/files/123/raw?t=<jwt>`
- 调用工具时请把上面的 path 或 url 作为参数传入,不要尝试在对话中读取该文件内容。
```
- **skill**：通过 `run_skill_script` 把 path 作为 kwargs 之一传入，本地脚本直接 `open()`
- **MCP**：把 URL 作为参数传给工具，server 通过 HTTP 拉取（要求 MCP server 可访问 backend）

### 7. 部署要求
- **必须**在 `backend/.env` 配 `BACKEND_BASE_URL=http://<host>:<port>`，指向 backend 监听地址（不是前端 5173）。缺省回退到 `APP_BASE_URL`(前端地址)，MCP 多半访问不到。
- 若 backend 与 MCP server 在不同主机，`BACKEND_BASE_URL` 必须是 MCP 可访问的外网/同 VPC 地址
- 默认 60 分钟过期，超时后 MCP 拉取会 401；当前 chat 流是一次性请求，60 分钟足够

### 7.1 路径 vs URL 的选择
- `UPLOADS_DIR` 默认 `../storage/uploads`(相对 backend cwd)，runner 会 `Path(...).resolve()` 转绝对路径后注入 prompt
- 即使有绝对路径，**MCP server 也未必能访问**(进程隔离 / docker 容器隔离 / 跨主机)。所以 prompt 里**优先推荐 URL**，path 仅作为"工具与 backend 共享 fs"时的优化项
- skill 调用 `run_skill_script` 时确定与 backend 同进程，可放心传 path

### 8. 兼容性
- 老 Agent（无 `parse_mode`）默认按 `auto` 处理，行为不变
- 老前端读取 `parse_status="skipped"` 会落到默认分支显示"附件"，不会崩
- 老解析失败/进行中的逻辑不变
