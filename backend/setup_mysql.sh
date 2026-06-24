#!/bin/bash
# 本地 MySQL 快速配置脚本

echo "=== Agent Mill MySQL 配置 ==="

# 1. 创建数据库和用户
echo "1. 创建数据库和用户..."
mysql -u root -e "
CREATE DATABASE IF NOT EXISTS agent_mill CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'agent_mill'@'localhost' IDENTIFIED BY 'agent_mill';
GRANT ALL PRIVILEGES ON agent_mill.* TO 'agent_mill'@'localhost';
FLUSH PRIVILEGES;
" 2>/dev/null

if [ $? -eq 0 ]; then
    echo "   ✅ 数据库和用户创建成功"
else
    echo "   ❌ 创建失败，请检查 MySQL 是否运行或需要密码"
    echo "   请手动执行: mysql -u root -p < setup.sql"
    exit 1
fi

# 2. 配置 .env
echo "2. 配置环境变量..."
if [ ! -f .env ]; then
    cat > .env << 'ENVEOF'
# 数据库配置
DB_TYPE=mysql
DB_HOST=localhost
DB_PORT=3306
DB_USER=agent_mill
DB_PASSWORD=agent_mill
DB_NAME=agent_mill

# 认证配置
JWT_SECRET=local-dev-secret-key-change-in-production
JWT_ALG=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=720
REFRESH_TOKEN_EXPIRE_DAYS=2
ENCRYPTION_KEY=

# 存储配置
STORAGE_ROOT=../storage
SKILLS_DIR=../storage/skills
UPLOADS_DIR=../storage/uploads
MAX_UPLOAD_MB=50

# CORS 配置
CORS_ORIGINS=http://localhost:5173

# 访问地址
APP_BASE_URL=http://localhost:5173

# 管理员账号
SEED_ADMIN_USERNAME=admin
SEED_ADMIN_PASSWORD=YOUR_ADMIN_PASSWORD
ENVEOF
    echo "   ✅ .env 文件创建成功"
else
    echo "   ⏭️  .env 文件已存在，跳过"
fi

# 3. 初始化数据库
echo "3. 初始化数据库..."
source .venv/bin/activate && python -m app.db.init_db

echo ""
echo "=== 配置完成 ==="
echo "启动命令: make dev"
echo "访问地址: http://localhost:5173"
echo "登录账号: admin / YOUR_ADMIN_PASSWORD"
