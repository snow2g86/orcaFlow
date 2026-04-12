#!/bin/bash
# dev.sh — OrcaFlow 개발 서버 기동
#
# 사전 요구: Rust 1.79+, Tauri CLI v2, Node.js 20+, pnpm 9+, Python 3.11+, uv
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "==> OrcaFlow Dev Server"

# Step 1: Python 의존성 동기화
echo "--- Syncing Python dependencies"
cd "$ROOT/sidecar" && uv sync

# Step 2: Frontend 의존성 설치
echo "--- Installing frontend dependencies"
cd "$ROOT/frontend" && pnpm install --frozen-lockfile 2>/dev/null || pnpm install

# Step 3: Tauri 개발 서버 (sidecar spawn + frontend dev server)
echo "--- Starting Tauri dev server"
cd "$ROOT/app/src-tauri"
ORCA_DEV=1 cargo tauri dev
