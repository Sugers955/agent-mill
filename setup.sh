#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Agent Mill 一键启动脚本
# 用法: chmod +x setup.sh && ./setup.sh
# ============================================================

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# 检查依赖
check_deps() {
    command -v docker >/dev/null 2>&1 || error "请先安装 Docker: https://docs.docker.com/get-docker/"
    command -v docker compose >/dev/null 2>&1 || error "请先安装 Docker Compose V2"
    
    # 检查 Docker 是否运行
    docker info >/dev/null 2>&1 || error "Docker 未启动，请先启动 Docker"
}

# 生成配置文件
setup_env() {
    if [ ! -f .env ]; then
        info "生成 .env 配置文件..."
        cp .env.example .env
        
        # 自动生成密钥
        JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))" 2>/dev/null || openssl rand -base64 48 | tr -d '=')
        ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || echo "")
        
        # 写入 .env
        sed -i.bak "s|JWT_SECRET=changeme-random-secret-key|JWT_SECRET=${JWT_SECRET}|" .env
        if [ -n "$ENCRYPTION_KEY" ]; then
            sed -i.bak "s|ENCRYPTION_KEY=|ENCRYPTION_KEY=${ENCRYPTION_KEY}|" .env
        fi
        rm -f .env.bak
        
        info ".env 已生成，密钥已自动填充"
        warn "请编辑 .env 填写数据库密码和 API Key"
    else
        info ".env 已存在，跳过生成"
    fi
}

# 启动服务
start_services() {
    info "启动 Docker 服务..."
    docker compose up -d --build
    
    info "等待服务就绪..."
    local max_wait=60
    local count=0
    while [ $count -lt $max_wait ]; do
        if docker compose ps api | grep -q "healthy\|Up"; then
            break
        fi
        sleep 2
        count=$((count + 2))
        echo -ne "\r  等待中... ${count}s"
    done
    echo ""
    
    # 检查服务状态
    if docker compose ps | grep -q "Up"; then
        info "服务启动成功！"
        echo ""
        echo "=========================================="
        echo "  访问地址: http://localhost"
        echo "  后端 API: http://localhost:8000/docs"
        echo "=========================================="
        echo ""
        echo "  默认账号: admin"
        echo "  默认密码: 见 .env 中 SEED_ADMIN_PASSWORD"
        echo ""
        echo "  常用命令:"
        echo "    docker compose ps        查看状态"
        echo "    docker compose logs -f   查看日志"
        echo "    docker compose down      停止服务"
        echo ""
    else
        error "服务启动失败，请执行 docker compose logs api 查看日志"
    fi
}

# 主流程
main() {
    echo ""
    echo "  Agent Mill 一键启动"
    echo "  =================="
    echo ""
    
    check_deps
    setup_env
    start_services
}

main "$@"
