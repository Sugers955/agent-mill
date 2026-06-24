# 部署指南

本文档提供 Agent Mill 的完整部署指南，包括 Docker 一键部署和手动部署两种方式。

---

## 目录

- [系统要求](#系统要求)
- [Docker 部署（推荐）](#docker-部署推荐)
- [手动部署](#手动部署)
- [环境变量配置](#环境变量配置)
- [常见问题](#常见问题)

---

## 系统要求

### 最低配置

| 资源 | 要求 |
|------|------|
| CPU | 2 核 |
| 内存 | 4 GB |
| 磁盘 | 20 GB SSD |
| 操作系统 | Linux / macOS / Windows (WSL2) |

### 推荐配置

| 资源 | 要求 |
|------|------|
| CPU | 4 核 |
| 内存 | 8 GB |
| 磁盘 | 50 GB SSD |
| 操作系统 | Ubuntu 22.04+ / CentOS 8+ |

### 软件依赖

| 软件 | 版本要求 |
|------|----------|
| Docker | 24.0+ |
| Docker Compose | v2.20+ |
| Python | 3.11+ |
| Node.js | 18+ |
| MySQL | 8.0+ |

---

## Docker 部署（推荐）

### 1. 获取代码

```bash
git clone https://github.com/Sugers955/agent-mill.git
cd agent-mill
```

### 2. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑环境变量
vim .env
```

### 3. 必须配置的变量

```bash
# 数据库配置
DB_HOST=mysql
DB_PORT=3306
DB_USER=agent_mill
DB_PASSWORD=your_secure_password
DB_NAME=agent_mill

# 安全配置
JWT_SECRET=your-random-secret-key-at-least-32-chars
ENCRYPTION_KEY=your-fernet-key

# AI 模型配置（至少配置一个）
ANTHROPIC_API_KEY=sk-ant-xxx
# 或
OPENAI_API_KEY=sk-xxx

# 种子用户密码
SEED_ADMIN_PASSWORD=admin123
SEED_USER_PASSWORD=user123
```

### 4. 启动服务

```bash
# 首次部署
make deploy

# 或直接使用 docker compose
docker compose up -d
```

### 5. 验证部署

```bash
# 查看服务状态
make deploy-status

# 查看日志
make deploy-logs

# 访问应用
# http://localhost
```

### 6. 常用命令

```bash
# 启动
make deploy

# 停止（保留数据）
make deploy-down

# 停止并删除数据（危险！）
docker compose down -v

# 更新代码后重新部署
make deploy-update

# 查看实时日志
docker compose logs -f api
docker compose logs -f web
```

---

## 手动部署

### 1. 安装依赖

#### 后端

```bash
cd backend

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -e .
```

#### 前端

```bash
cd frontend

# 安装依赖
npm install

# 构建生产版本
npm run build
```

### 2. 配置数据库

```sql
-- 登录 MySQL
mysql -u root -p

-- 创建数据库
CREATE DATABASE agent_mill CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 创建用户
CREATE USER 'agent_mill'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON agent_mill.* TO 'agent_mill'@'localhost';
FLUSH PRIVILEGES;
```

### 3. 配置后端

```bash
cd backend

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件

# 启动后端
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 4. 配置前端

```bash
cd frontend

# 配置 Nginx 或使用 Vite 开发服务器
npm run dev  # 开发环境
# 或
npm run build && npx serve dist  # 生产环境预览
```

### 5. 配置反向代理（生产环境）

#### Nginx 配置示例

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 重定向到 HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # 前端静态文件
    location / {
        root /path/to/agent-mill/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE 支持
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding off;
        proxy_buffering off;
        proxy_cache off;
    }
}
```

---

## 环境变量配置

### 完整变量列表

| 变量名 | 必填 | 默认值 | 说明 |
|--------|------|--------|------|
| `DB_HOST` | ✅ | localhost | 数据库主机 |
| `DB_PORT` | ❌ | 3306 | 数据库端口 |
| `DB_USER` | ✅ | root | 数据库用户 |
| `DB_PASSWORD` | ✅ | - | 数据库密码 |
| `DB_NAME` | ✅ | agent_mill | 数据库名 |
| `JWT_SECRET` | ✅ | - | JWT 签名密钥（至少 32 字符） |
| `ENCRYPTION_KEY` | ✅ | - | Fernet 加密密钥 |
| `ANTHROPIC_API_KEY` | ⚠️ | - | Anthropic API Key（至少配置一个） |
| `OPENAI_API_KEY` | ⚠️ | - | OpenAI API Key（至少配置一个） |
| `SEED_ADMIN_PASSWORD` | ❌ | admin123 | 管理员初始密码 |
| `SEED_USER_PASSWORD` | ❌ | user123 | 普通用户初始密码 |
| `DEBUG` | ❌ | false | 调试模式 |
| `CORS_ORIGINS` | ❌ | * | CORS 允许的源 |

### 生成安全密钥

```bash
# 生成 JWT 密钥
openssl rand -hex 32

# 生成 Fernet 加密密钥
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## 常见问题

### 1. 数据库连接失败

**症状**：`Can't connect to MySQL server`

**解决方案**：

```bash
# 检查 MySQL 是否运行
docker compose ps mysql

# 检查数据库配置
cat .env | grep DB_

# 测试连接
mysql -h localhost -u agent_mill -p
```

### 2. API Key 无效

**症状**：`Authentication failed` 或 `Invalid API key`

**解决方案**：

```bash
# 检查 API Key 配置
cat .env | grep API_KEY

# 测试 API Key
curl -H "Authorization: Bearer $ANTHROPIC_API_KEY" https://api.anthropic.com/v1/messages
```

### 3. 内存不足

**症状**：`OOMKilled` 或 `MemoryError`

**解决方案**：

```bash
# 查看容器资源使用
docker stats

# 增加内存限制（docker-compose.yml）
services:
  api:
    deploy:
      resources:
        limits:
          memory: 4G
```

### 4. 端口冲突

**症状**：`Bind for 0.0.0.0:8000 failed: port is already allocated`

**解决方案**：

```bash
# 查看端口占用
lsof -i :8000

# 修改端口映射（docker-compose.yml）
services:
  api:
    ports:
      - "8001:8000"
```

### 5. 文件上传失败

**症状**：`413 Request Entity Too Large`

**解决方案**：

```bash
# Nginx 配置
client_max_body_size 100M;

# 检查磁盘空间
df -h
```

---

## 生产环境建议

### 安全建议

1. 使用 HTTPS（通过 Let's Encrypt 或商业证书）
2. 配置防火墙，仅开放必要端口
3. 定期更新系统和依赖
4. 备份数据库和用户上传文件
5. 启用审计日志监控

### 性能建议

1. 使用 SSD 存储
2. 配置 Redis 缓存（可选）
3. 使用 CDN 加速静态资源
4. 配置负载均衡（多实例部署）

### 监控建议

1. 配置日志收集（ELK / Loki）
2. 设置性能监控（Prometheus + Grafana）
3. 配置告警通知（钉钉 / 企微 / 飞书）

---

## 获取帮助

如果遇到问题，请通过以下方式获取帮助：

- 查看 [GitHub Issues](https://github.com/Sugers955/agent-mill/issues)
- 搜索 [GitHub Discussions](https://github.com/Sugers955/agent-mill/discussions)
- 提交新的 Issue 或 Discussion
