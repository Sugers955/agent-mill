#!/usr/bin/env bash
# deploy.sh — Agent Mill 一键服务器部署脚本
#
# 首次部署:  ./deploy.sh
# 更新部署:  ./deploy.sh --update
# 强制重建:  ./deploy.sh --rebuild
# 查看日志:  ./deploy.sh --logs
# 停止服务:  ./deploy.sh --down

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# ── 颜色 ─────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${GREEN}[deploy]${NC} $*"; }
warn()  { echo -e "${YELLOW}[ warn ]${NC} $*"; }
error() { echo -e "${RED}[error ]${NC} $*"; exit 1; }
step()  { echo -e "\n${BLUE}══ $* ══${NC}"; }

# ── 错误时自动打印日志 ────────────────────────────────────────────────────────
on_error() {
  local line=$1
  echo -e "\n${RED}══ 部署失败（脚本第 ${line} 行）══${NC}"
  if [[ -n "${COMPOSE:-}" ]]; then
    echo -e "${YELLOW}── 容器状态 ──${NC}"
    $COMPOSE ps 2>/dev/null || true
    echo -e "\n${YELLOW}── 最近日志（各服务后 60 行）──${NC}"
    $COMPOSE logs --tail=60 --no-color 2>/dev/null || true
  fi
  echo -e "\n${YELLOW}提示: 修复后可运行 ./deploy.sh --logs 查看完整日志${NC}"
}
trap 'on_error $LINENO' ERR

# ── 参数解析 ──────────────────────────────────────────────────────────────────
MODE="deploy"
for arg in "$@"; do
  case $arg in
    --update)  MODE="update"  ;;
    --rebuild) MODE="rebuild" ;;
    --logs)    MODE="logs"    ;;
    --down)    MODE="down"    ;;
    --status)  MODE="status"  ;;
    -h|--help)
      echo "用法: $0 [选项]"
      echo "  (无选项)   首次部署（完整构建 + 初始化数据库）"
      echo "  --update   拉取最新代码后重新构建并重启服务"
      echo "  --rebuild  强制重建所有镜像（不使用缓存）"
      echo "  --logs     实时查看所有服务日志"
      echo "  --status   查看服务运行状态"
      echo "  --down     停止并移除容器（数据卷保留）"
      exit 0
      ;;
  esac
done

# ── 检测 docker compose 命令 ──────────────────────────────────────────────────
detect_compose() {
  if docker compose version >/dev/null 2>&1; then
    echo "docker compose"
  elif command -v docker-compose >/dev/null 2>&1; then
    echo "docker-compose"
  else
    error "未找到 docker compose。请先安装 Docker Desktop 或 docker-compose-plugin。"
  fi
}

# ── 子命令：日志 / 状态 / 停止 ────────────────────────────────────────────────
COMPOSE="$(detect_compose)"

if [[ "$MODE" == "logs" ]]; then
  $COMPOSE logs -f --tail=100
  exit 0
fi

if [[ "$MODE" == "status" ]]; then
  $COMPOSE ps
  exit 0
fi

if [[ "$MODE" == "down" ]]; then
  warn "即将停止并移除所有容器（数据卷不删除）..."
  $COMPOSE down
  info "已停止。数据卷 pgdata 和 storage/ 目录保留。"
  exit 0
fi

# ── 前置检查 ──────────────────────────────────────────────────────────────────
step "检查环境"

command -v docker >/dev/null 2>&1 || error "未找到 docker，请先安装。"
info "Docker: $(docker --version)"
info "Compose: $($COMPOSE version --short 2>/dev/null || $COMPOSE version | head -1)"

# ── 检查 .env ─────────────────────────────────────────────────────────────────
step "检查配置文件"

if [[ ! -f .env ]]; then
  if [[ -f .env.example ]]; then
    cp .env.example .env
    warn ".env 不存在，已从 .env.example 复制。"
    warn "请编辑 .env 填写真实值后重新运行 $0"
    warn ""
    warn "  必填项："
    warn "    DB_PASSWORD        — 数据库密码"
    warn "    JWT_SECRET         — 认证密钥（建议 48+ 字节随机串）"
    warn "    ENCRYPTION_KEY     — Fernet 加密密钥"
    warn "    APP_BASE_URL       — 服务器访问地址（含端口）"
    warn "    SEED_ADMIN_PASSWORD — 初始管理员密码"
    echo
    error "请先编辑 .env 再重新运行。"
  else
    error ".env 和 .env.example 均不存在，无法继续。"
  fi
fi

# 检查关键占位符
PLACEHOLDERS=()
grep -q "change-me-secure-password"    .env 2>/dev/null && PLACEHOLDERS+=("DB_PASSWORD")
grep -q "change-me-32-plus"            .env 2>/dev/null && PLACEHOLDERS+=("JWT_SECRET")
grep -q "change-me-admin-password"     .env 2>/dev/null && PLACEHOLDERS+=("SEED_ADMIN_PASSWORD")
grep -q "your-server-ip"               .env 2>/dev/null && PLACEHOLDERS+=("APP_BASE_URL")

if [[ ${#PLACEHOLDERS[@]} -gt 0 ]]; then
  warn ".env 中以下字段仍为示例值，请修改后再用于生产："
  for p in "${PLACEHOLDERS[@]}"; do warn "  - $p"; done
  echo
  read -r -p "是否仍要继续部署？[y/N] " confirm
  [[ "$confirm" =~ ^[Yy]$ ]] || exit 1
fi

info ".env 检查完成"

# .env 变量导入 shell（用于后续 pg_isready 等命令读取 DB_USER/DB_NAME）
set -a
# shellcheck source=.env
source .env
set +a

# ── 创建 storage 子目录 ────────────────────────────────────────────────────────
step "准备存储目录"

mkdir -p storage/uploads storage/skills storage/outputs
touch storage/uploads/.gitkeep storage/skills/.gitkeep 2>/dev/null || true
info "storage/ 目录就绪"

# ── 构建镜像 ──────────────────────────────────────────────────────────────────
step "构建 Docker 镜像"

if [[ "$MODE" == "update" ]]; then
  info "增量构建（使用缓存）..."
  $COMPOSE build
elif [[ "$MODE" == "rebuild" ]]; then
  info "强制重建（不使用缓存）..."
  $COMPOSE build --no-cache
else
  info "首次构建..."
  $COMPOSE build --no-cache
fi

# ── 启动服务 ──────────────────────────────────────────────────────────────────
step "启动服务"

$COMPOSE up -d

# 给容器 5s 初始化，再确认是否都在 running
sleep 5
step "容器启动状态"
$COMPOSE ps

# ── 等待数据库就绪 ────────────────────────────────────────────────────────────
step "等待数据库就绪"

DB_READY=false
for i in $(seq 1 30); do
  if $COMPOSE exec -T db pg_isready -U "${DB_USER:-agent_mill}" -d "${DB_NAME:-agent_mill}" >/dev/null 2>&1; then
    DB_READY=true
    break
  fi
  echo -n "."
  sleep 2
done
echo

$DB_READY || {
  echo -e "\n${RED}数据库 60s 内未就绪，db 容器日志：${NC}"
  $COMPOSE logs --tail=80 db
  exit 1
}
info "数据库已就绪"

# ── 初始化 / 迁移数据库 ───────────────────────────────────────────────────────
step "初始化数据库"

if $COMPOSE exec -T api python -m app.db.init_db 2>&1; then
  info "数据库初始化完成"
else
  echo -e "\n${RED}init_db 失败，api 容器日志：${NC}"
  $COMPOSE logs --tail=80 api
  warn "如果是「表已存在」错误属正常（重复部署），其他错误请检查上方日志"
fi

# ── 验证服务状态 ──────────────────────────────────────────────────────────────
step "验证服务"

sleep 3
$COMPOSE ps

# 读取访问地址
APP_URL=$(grep -E "^APP_BASE_URL=" .env 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'")
ADMIN_PASS=$(grep -E "^SEED_ADMIN_PASSWORD=" .env 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'")
ADMIN_USER=$(grep -E "^SEED_ADMIN_USERNAME=" .env 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'" || echo "admin")

echo
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║               部署完成！                                ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║${NC}  访问地址:  ${BLUE}${APP_URL:-http://<your-server-ip>}${NC}"
echo -e "${GREEN}║${NC}  管理员:    ${ADMIN_USER:-admin} / ${ADMIN_PASS:-见 .env SEED_ADMIN_PASSWORD}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║${NC}  查看日志:  ./deploy.sh --logs"
echo -e "${GREEN}║${NC}  查看状态:  ./deploy.sh --status"
echo -e "${GREEN}║${NC}  更新部署:  git pull && ./deploy.sh --update"
echo -e "${GREEN}║${NC}  停止服务:  ./deploy.sh --down"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo
warn "安全提醒：首次登录后请立即在管理界面修改默认管理员密码！"
