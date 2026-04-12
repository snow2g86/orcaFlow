#!/bin/bash
# clean.sh — OrcaFlow 빌드 아티팩트 정리
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "==> Cleaning OrcaFlow build artifacts"

# Sidecar PyInstaller 아티팩트
echo "--- Cleaning sidecar build artifacts"
rm -rf "$ROOT/sidecar/build" "$ROOT/sidecar/dist" "$ROOT/sidecar/orca-sidecar.spec" 2>/dev/null || true

# Tauri externalBin 복사본
echo "--- Cleaning Tauri binaries directory"
rm -rf "$ROOT/app/src-tauri/binaries" 2>/dev/null || true

# Rust target (선택적 — --all 플래그)
if [[ "${1:-}" == "--all" ]]; then
    echo "--- Cleaning Rust target directory (this may take a moment)"
    rm -rf "$ROOT/app/src-tauri/target" 2>/dev/null || true

    echo "--- Cleaning frontend dist"
    rm -rf "$ROOT/frontend/dist" 2>/dev/null || true

    echo "--- Cleaning frontend node_modules"
    rm -rf "$ROOT/frontend/node_modules" 2>/dev/null || true
fi

echo "==> Clean complete"
