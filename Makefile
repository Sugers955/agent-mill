# Agent Mill — 开发命令简化
# 用法: make [目标]

.PHONY: help dev stop logs status clean build typecheck db-migrate db-seed db-reset setup docker-up docker-down

# 默认目标
help:
	@echo ""
	@echo "Agent Mill 开发命令"
	@echo "=================="
	@echo ""
	@echo "  make setup        一键启动 Docker 环境（推荐新手）"
	@echo "  make dev          启动本地开发环境 (后端:8000 + 前端:5173)"
	@echo "  make stop         停止本地开发环境"
	@echo "  make logs         查看后端日志"
	@echo "  make status       查看运行状态"
	@echo "  make clean        清理临时文件和进程"
	@echo ""
	@echo "  make build        构建前端"
	@echo "  make typecheck    TypeScript 类型检查"
	@echo ""
	@echo "  make db-migrate   运行数据库迁移"
	@echo "  make db-seed      播种演示数据"
	@echo "  make db-reset     重置数据库"
	@echo ""
	@echo "  make docker-up    Docker 启动"
	@echo "  make docker-down  Docker 停止"
	@echo ""

# ── 一键启动 ────────────────────────────────────────────────────────────────
setup:
	@chmod +x setup.sh && ./setup.sh

# ── Docker ──────────────────────────────────────────────────────────────────
docker-up:
	docker compose up -d --build
	@echo "✅ 访问 http://localhost"

docker-down:
	docker compose down

# ── 本地开发 ────────────────────────────────────────────────────────────────

# ── 本地开发 ────────────────────────────────────────────────────────────────
dev:
	@echo "启动 Agent Mill 开发环境..."
	cd backend && source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &>/tmp/agent-mill-backend.log &
	cd frontend && npm run dev &>/tmp/agent-mill-frontend.log &
	@sleep 2 && echo "✅ 后端: http://localhost:8000  前端: http://localhost:5173"

stop:
	@pkill -f "uvicorn app.main:app" 2>/dev/null && echo "后端已停止" || echo "后端未运行"
	@pkill -f "vite" 2>/dev/null && echo "前端已停止" || echo "前端未运行"

logs:
	@tail -50 /tmp/agent-mill-backend.log

logs-f:
	@tail -f /tmp/agent-mill-backend.log

status:
	@echo "=== Backend (uvicorn) ===" && pgrep -f "uvicorn app.main:app" || echo "未运行"
	@echo "=== Frontend (vite) ===" && pgrep -f "vite" || echo "未运行"

clean:
	@pkill -f "uvicorn app.main:app" 2>/dev/null && echo "已停止后端" || echo "后端未运行"
	@pkill -f "vite" 2>/dev/null && echo "已停止前端" || echo "前端未运行"
	@rm -f /tmp/agent-mill-backend.log /tmp/agent-mill-frontend.log
	@echo "已清理临时日志"

# ── 前端构建 ────────────────────────────────────────────────────────────────
build:
	cd frontend && npm run build

typecheck:
	cd frontend && npx vue-tsc --noEmit

# ── 数据库 ──────────────────────────────────────────────────────────────────
db-migrate:
	cd backend && source .venv/bin/activate && python -m app.db.init_db

db-seed:
	cd backend && source .venv/bin/activate && python -m app.db.seed_demo

db-reset:
	@echo "⚠️  警告: 这将删除所有数据!"
	@read -p "确认删除? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	cd backend && source .venv/bin/activate && python -c "\
	import os; from dotenv import load_dotenv; load_dotenv(); \
	import pymysql; \
	conn = pymysql.connect(host=os.getenv('DB_HOST','localhost'), user=os.getenv('DB_USER','root'), password=os.getenv('DB_PASSWORD','')); \
	cursor = conn.cursor(); \
	db = os.getenv('DB_NAME','agent_mill'); \
	cursor.execute(f'DROP DATABASE IF EXISTS {db}'); \
	cursor.execute(f'CREATE DATABASE {db} CHARACTER SET utf8mb4'); conn.close(); \
	print('数据库已重建')"
	cd backend && source .venv/bin/activate && python -m app.db.init_db
	@echo "数据库已重置"