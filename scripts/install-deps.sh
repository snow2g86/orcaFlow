#!/bin/bash
# install-deps.sh — OrcaFlow 개발에 필요한 사전 요구사항 설치 도우미
#
# 지원 플랫폼: macOS (Homebrew), Ubuntu/Debian (apt), Windows (winget/choco 안내)
set -euo pipefail

echo "==> OrcaFlow Dependency Installer"
echo ""

check_cmd() {
    command -v "$1" >/dev/null 2>&1
}

# -- 플랫폼 감지 --
OS="$(uname -s)"
case "$OS" in
    Darwin)
        echo "Platform: macOS"
        echo ""

        # Xcode CLT
        if ! xcode-select -p >/dev/null 2>&1; then
            echo "--- Installing Xcode Command Line Tools"
            xcode-select --install
            echo "    Xcode CLT 설치 팝업이 뜨면 'Install' 을 클릭하세요."
            echo "    설치 완료 후 이 스크립트를 다시 실행하세요."
            exit 0
        fi
        echo "[OK] Xcode Command Line Tools"

        # Homebrew
        if ! check_cmd brew; then
            echo "--- Installing Homebrew"
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        fi
        echo "[OK] Homebrew"

        # Rust
        if ! check_cmd rustc; then
            echo "--- Installing Rust via rustup"
            curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
            source "$HOME/.cargo/env"
        fi
        echo "[OK] Rust $(rustc --version 2>/dev/null | cut -d' ' -f2)"

        # Node.js
        if ! check_cmd node; then
            echo "--- Installing Node.js via Homebrew"
            brew install node
        fi
        echo "[OK] Node.js $(node --version 2>/dev/null)"

        # pnpm
        if ! check_cmd pnpm; then
            echo "--- Installing pnpm"
            npm install -g pnpm
        fi
        echo "[OK] pnpm $(pnpm --version 2>/dev/null)"

        # Python
        if ! check_cmd python3; then
            echo "--- Installing Python via Homebrew"
            brew install python@3.11
        fi
        echo "[OK] Python $(python3 --version 2>/dev/null | cut -d' ' -f2)"

        # uv
        if ! check_cmd uv; then
            echo "--- Installing uv"
            curl -LsSf https://astral.sh/uv/install.sh | sh
        fi
        echo "[OK] uv $(uv --version 2>/dev/null | cut -d' ' -f2)"

        # Tauri CLI
        if ! cargo install --list 2>/dev/null | grep -q "tauri-cli"; then
            echo "--- Installing Tauri CLI v2"
            cargo install tauri-cli --version "^2" --locked
        fi
        echo "[OK] Tauri CLI"
        ;;

    Linux)
        echo "Platform: Linux"
        echo ""

        # 시스템 라이브러리 (Ubuntu/Debian)
        if check_cmd apt-get; then
            echo "--- Installing system libraries (requires sudo)"
            sudo apt-get update -qq
            sudo apt-get install -y -qq \
                libwebkit2gtk-4.1-dev \
                libayatana-appindicator3-dev \
                librsvg2-dev \
                build-essential \
                curl \
                wget \
                file \
                libssl-dev \
                libgtk-3-dev \
                squashfs-tools \
                patchelf
        fi

        # Rust
        if ! check_cmd rustc; then
            echo "--- Installing Rust via rustup"
            curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
            source "$HOME/.cargo/env"
        fi
        echo "[OK] Rust $(rustc --version 2>/dev/null | cut -d' ' -f2)"

        # Node.js (via nvm or direct)
        if ! check_cmd node; then
            echo "--- Installing Node.js 20 LTS"
            curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
            sudo apt-get install -y nodejs
        fi
        echo "[OK] Node.js $(node --version 2>/dev/null)"

        # pnpm
        if ! check_cmd pnpm; then
            echo "--- Installing pnpm"
            npm install -g pnpm
        fi
        echo "[OK] pnpm $(pnpm --version 2>/dev/null)"

        # Python
        if ! check_cmd python3; then
            echo "--- Installing Python 3.11"
            sudo apt-get install -y python3.11 python3.11-venv
        fi
        echo "[OK] Python $(python3 --version 2>/dev/null | cut -d' ' -f2)"

        # uv
        if ! check_cmd uv; then
            echo "--- Installing uv"
            curl -LsSf https://astral.sh/uv/install.sh | sh
        fi
        echo "[OK] uv $(uv --version 2>/dev/null | cut -d' ' -f2)"

        # Tauri CLI
        if ! cargo install --list 2>/dev/null | grep -q "tauri-cli"; then
            echo "--- Installing Tauri CLI v2"
            cargo install tauri-cli --version "^2" --locked
        fi
        echo "[OK] Tauri CLI"
        ;;

    MINGW*|MSYS*|CYGWIN*)
        echo "Platform: Windows"
        echo ""
        echo "Windows 에서는 다음을 수동 설치하세요:"
        echo ""
        echo "  1. Visual Studio Build Tools (C++ 데스크톱 개발)"
        echo "     https://visualstudio.microsoft.com/visual-cpp-build-tools/"
        echo ""
        echo "  2. WebView2 Runtime (Windows 10+ 에는 보통 포함)"
        echo "     https://developer.microsoft.com/en-us/microsoft-edge/webview2/"
        echo ""
        echo "  3. Rust: https://rustup.rs"
        echo "  4. Node.js 20+: https://nodejs.org"
        echo "  5. pnpm: npm install -g pnpm"
        echo "  6. Python 3.11+: https://python.org"
        echo "  7. uv: pip install uv"
        echo "  8. Tauri CLI: cargo install tauri-cli --version '^2' --locked"
        ;;

    *)
        echo "Unknown platform: $OS"
        echo "Please install manually: Rust, Node.js, pnpm, Python 3.11+, uv, Tauri CLI v2"
        exit 1
        ;;
esac

echo ""
echo "==> All dependencies checked. Run 'scripts/dev.sh' to start developing."
