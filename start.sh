#!/usr/bin/env bash
# Agent Mill — 一键启动脚本
# 启动顺序：backend (uvicorn :8000) → frontend (vite :5173)
# 日志：/tmp/agent-mill-backend.log、/tmp/agent-mill-frontend.log
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[start] killing old uvicorn/vite processes ..."
pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
sleep 1

echo "[start] launching backend (uvicorn) on http://localhost:8000 ..."
cd "$ROOT/backend"
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload \
  > /tmp/agent-mill-backend.log 2>&1 &
BACKEND_PID=$!
echo "[start] backend pid=$BACKEND_PID"

echo "[start] launching frontend (vite) on http://localhost:5173 ..."
cd "$ROOT/frontend"
npm run dev > /tmp/agent-mill-frontend.log 2>&1 &
FRONTEND_PID=$!
echo "[start] frontend pid=$FRONTEND_PID"

sleep 4
echo
echo "[start] ready. logs:"
echo "  backend  : tail -f /tmp/agent-mill-backend.log"
echo "  frontend : tail -f /tmp/agent-mill-frontend.log"
echo
echo "  http://localhost:5173"
