#!/bin/bash
# release.sh — OrcaFlow 릴리스 빌드 (sidecar 번들 -> frontend 빌드 -> Tauri 패키징)
#
# 출력: app/src-tauri/target/release/bundle/ 아래에 .dmg / .msi / .deb / .AppImage
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "==> OrcaFlow Release Build"

# Step 1: Sidecar 번들링 (PyInstaller)
echo ""
echo "=== Step 1/4: Bundling sidecar ==="
"$SCRIPT_DIR/bundle-sidecar.sh"

# Step 2: Sidecar 바이너리를 Tauri externalBin 경로로 복사
echo ""
echo "=== Step 2/4: Copying sidecar binary ==="
SIDECAR_BIN="$ROOT/sidecar/dist/orca-sidecar"
TAURI_BIN_DIR="$ROOT/app/src-tauri/binaries"
mkdir -p "$TAURI_BIN_DIR"

# Tauri externalBin 은 파일명에 타겟 트리플을 suffix 로 요구
case "$(uname -s)-$(uname -m)" in
    Darwin-arm64)   SUFFIX="-aarch64-apple-darwin" ;;
    Darwin-x86_64)  SUFFIX="-x86_64-apple-darwin" ;;
    Linux-x86_64)   SUFFIX="-x86_64-unknown-linux-gnu" ;;
    Linux-aarch64)  SUFFIX="-aarch64-unknown-linux-gnu" ;;
    MINGW*|MSYS*|CYGWIN*)
        SUFFIX="-x86_64-pc-windows-msvc.exe"
        SIDECAR_BIN="${SIDECAR_BIN}.exe"
        ;;
    *)
        echo "WARNING: Unknown platform $(uname -s)-$(uname -m), using no suffix"
        SUFFIX=""
        ;;
esac

cp "$SIDECAR_BIN" "$TAURI_BIN_DIR/orca-sidecar${SUFFIX}"
echo "Copied sidecar to: $TAURI_BIN_DIR/orca-sidecar${SUFFIX}"
ls -lh "$TAURI_BIN_DIR/orca-sidecar${SUFFIX}"

# Step 3: Frontend 빌드
echo ""
echo "=== Step 3/4: Building frontend ==="
cd "$ROOT/frontend" && pnpm install --frozen-lockfile 2>/dev/null || pnpm install
pnpm build

# Step 4: Tauri 빌드
echo ""
echo "=== Step 4/4: Building Tauri app ==="
cd "$ROOT/app/src-tauri" && cargo tauri build

echo ""
echo "==> Release build complete!"
echo ""
echo "Build artifacts:"
ls -lhR "$ROOT/app/src-tauri/target/release/bundle/" 2>/dev/null || echo "(bundle directory not found — check build output above)"
