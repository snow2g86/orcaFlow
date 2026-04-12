#!/bin/bash
# bundle-sidecar.sh — PyInstaller 로 Python sidecar 를 단일 실행 파일로 번들링
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SIDECAR_DIR="$ROOT/sidecar"

echo "==> Bundling Python sidecar with PyInstaller"

cd "$SIDECAR_DIR"

# PyInstaller 를 임시 설치 (pyproject.toml 에는 추가하지 않음)
echo "--- Installing PyInstaller (build-only dependency)"
uv pip install pyinstaller

# 이전 빌드 아티팩트 정리
rm -rf build/ dist/ orca-sidecar.spec 2>/dev/null || true

echo "--- Running PyInstaller"
uv run pyinstaller \
  --name orca-sidecar \
  --onefile \
  --hidden-import orca_core \
  --hidden-import orca_core.ipc \
  --hidden-import orca_core.ipc.routes \
  --hidden-import orca_core.ipc.http_app \
  --hidden-import orca_core.orchestrator \
  --hidden-import orca_core.providers \
  --hidden-import orca_core.tools \
  --hidden-import orca_core.tools.fs \
  --hidden-import orca_core.tools.shell \
  --hidden-import orca_core.tools.browser \
  --hidden-import orca_core.tools.os \
  --hidden-import orca_core.tools.web \
  --hidden-import orca_core.tools.register_all \
  --hidden-import orca_core.tools.registry \
  --hidden-import orca_core.tools.runtime \
  --hidden-import orca_core.policy \
  --hidden-import orca_core.audit \
  --hidden-import orca_core.journal \
  --hidden-import orca_core.persistence \
  --hidden-import orca_core.schema \
  --hidden-import orca_core.config \
  --hidden-import orca_core.errors \
  --collect-submodules orca_core \
  --exclude-module tkinter \
  --exclude-module matplotlib \
  --exclude-module PIL \
  --exclude-module pytest \
  --exclude-module _pytest \
  --exclude-module mypy \
  --exclude-module ruff \
  --noconfirm \
  orca_core/__main__.py

echo ""
echo "==> Sidecar binary built successfully:"
ls -lh dist/orca-sidecar*
echo ""
echo "Output: $SIDECAR_DIR/dist/orca-sidecar"
