#!/usr/bin/env bash
# Agent Forge — 一键停止
pkill -f "uvicorn app.main:app" 2>/dev/null && echo "[stop] backend killed" || echo "[stop] backend not running"
pkill -f "vite" 2>/dev/null && echo "[stop] frontend killed" || echo "[stop] frontend not running"
