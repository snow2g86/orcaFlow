# OrcaFlow

> **Native multi-agent orchestration for open LLMs.**
> 사용자 PC에서 직접 실행되며, 에이전트가 파일/앱/OS/브라우저에 직접 접근해 실제 업무를 수행하는 데스크톱 멀티 에이전트 오케스트레이션 플랫폼.

**버전**: 0.1.0 (MVP)

## 기본 원칙

1. **Native-first** -- Docker/VM 격리로 OrcaFlow 자체를 실행하지 않는다. 격리는 로컬 리소스 접근을 막아 제품 정체성을 훼손한다.
2. **Policy Before Action** -- 모든 파괴적/민감 작업은 정책 엔진 -> 사용자 승인 -> 변경 저널 -> 감사 로그 순서를 강제한다.
3. **Open LLM 중심** -- Ollama/vLLM/llama.cpp/LM Studio/Together/Groq/Fireworks 등 OpenAI 호환 공급자를 자유롭게 교체.
4. **재현 가능한 실행** -- 모든 Run 은 워크플로우 YAML 스냅샷과 함께 저장되어 재실행/비교 가능.

## 아키텍처 (3-Process Model)

```
+-------------------+     Tauri IPC      +------------------+     HTTP/SSE      +-------------------------+
|                   | <================> |                  | <===============> |                         |
|  Frontend         |                    |  Tauri Shell     |                   |  Python Sidecar         |
|  (WebView)        |                    |  (Rust)          |                   |  (FastAPI + orca_core)  |
|                   |                    |                  |                   |                         |
|  - React Flow     |                    |  - OS 권한       |                   |  - GraphRunner          |
|    Node Editor    |                    |  - 앱 수명주기   |                   |  - Planner              |
|  - Chat UI        |                    |  - Sidecar 감독  |                   |  - 17종 내장 툴         |
|  - Run Monitor    |                    |  - IPC 라우팅    |                   |  - Policy Engine        |
|  - Approval UI    |                    |                  |                   |  - LLM Adapters         |
|  - Policy Manager |                    |                  |                   |  - SQLite               |
|  - Settings       |                    |                  |                   |  - Audit/Journal        |
|                   |                    |                  |                   |                         |
+-------------------+                    +------------------+                   +-------------------------+
     Vite + React                            Rust + Tauri v2                        Python 3.11 + FastAPI
```

## 폴더 구조

```
OrcaFlow/
├── app/src-tauri/            # Tauri 데스크톱 셸 (Rust)
├── frontend/                 # Vite + React UI
├── sidecar/                  # Python FastAPI + orca_core
│   └── orca_core/
│       ├── schema/           # Domain: 엔티티 정의
│       ├── policy/           # Domain: 정책 엔진
│       ├── audit/            # Domain: 감사 로그
│       ├── journal/          # Domain: 변경 저널
│       ├── tools/            # Infrastructure: 내장 툴 17종
│       │   ├── fs/           #   fs.read_file, write_file, list, move, delete
│       │   ├── shell/        #   shell.exec
│       │   ├── browser/      #   browser.open, navigate, scrape, click
│       │   ├── os/           #   os.notify, clipboard_read/write, applescript, powershell
│       │   └── web/          #   web.search, http_request
│       ├── providers/        # Infrastructure: LLM 어댑터
│       ├── persistence/      # Infrastructure: SQLite
│       ├── orchestrator/     # Application: GraphRunner + Planner
│       ├── ipc/              # Presentation: FastAPI 라우트 + SSE
│       └── config.py
├── shared/fixtures/          # 샘플 워크플로우, 정책, 역할
├── scripts/                  # 빌드/개발 스크립트
├── docs/
│   ├── 01-plan/              # Plan, glossary, schema, conventions
│   └── 02-design/            # Design, Do guide
├── .github/workflows/        # GitHub Actions CI
├── CLAUDE.md                 # AI 협업 가이드
└── CONVENTIONS.md            # 요약 코딩 규약
```

## 빠른 시작

### 사전 요구 사항

- Rust 1.79+, Tauri CLI v2 (`cargo install tauri-cli --version '^2' --locked`)
- Node.js 20+, pnpm 9+
- Python 3.11+, [uv](https://docs.astral.sh/uv/)

플랫폼별 시스템 라이브러리:
- **macOS**: `xcode-select --install`
- **Windows**: VS Build Tools + WebView2 Runtime
- **Linux**: `webkit2gtk`, `libayatana-appindicator3-dev`, `librsvg2-dev`

자동 설치 도우미:
```bash
./scripts/install-deps.sh
```

### 개발 서버

```bash
./scripts/dev.sh
```

이 스크립트는 Python 의존성 동기화, Frontend 패키지 설치, Tauri dev 서버 기동을 순서대로 수행한다. `ORCA_DEV=1` 환경변수가 설정되어 sidecar 를 `uv run python -m orca_core` 로 실행한다.

### 수동 실행

```bash
# Python 의존성
cd sidecar && uv sync

# Frontend 의존성
cd frontend && pnpm install

# Tauri 개발 서버
cd app/src-tauri && ORCA_DEV=1 cargo tauri dev
```

### 테스트

```bash
# Python (345 tests, 88.37% coverage)
cd sidecar && uv run pytest

# Frontend (62 tests)
cd frontend && pnpm lint && pnpm typecheck && pnpm test

# Rust
cd app/src-tauri && cargo check && cargo clippy -- -D warnings
```

## 릴리스 빌드

```bash
./scripts/release.sh
```

빌드 과정:
1. PyInstaller 로 Python sidecar 를 단일 실행 파일로 번들링
2. 번들된 바이너리를 Tauri externalBin 경로로 복사 (플랫폼별 suffix 자동 결정)
3. Frontend 빌드 (`pnpm build`)
4. Tauri 빌드 (`cargo tauri build`)

출력: `app/src-tauri/target/release/bundle/` 아래에 플랫폼별 설치 파일 생성
- **macOS**: `.dmg`, `.app`
- **Windows**: `.msi`
- **Linux**: `.deb`, `.AppImage`

## 설정

OrcaFlow 는 `~/.orcaflow/config.toml` 에서 설정을 읽는다:

```toml
[app]
log_level = "info"              # trace | debug | info | warn | error

[sidecar]
host = "127.0.0.1"             # 항상 로컬 바인딩
port = 0                        # 0 = OS 가 자동 할당

[provider.ollama]
kind = "openai_compatible"
base_url = "http://localhost:11434/v1"

[provider.together]
kind = "openai_compatible"
base_url = "https://api.together.xyz/v1"
# API 키는 OS 키체인에 저장 (config 에 평문 저장 금지)
```

## 내장 툴 (17종)

| Namespace | Tool | 설명 | Side Effect |
|-----------|------|------|-------------|
| `fs` | `read_file` | 파일 읽기 | No |
| `fs` | `write_file` | 파일 쓰기 | Yes |
| `fs` | `list` | 디렉토리 목록 | No |
| `fs` | `move` | 파일/디렉토리 이동 | Yes |
| `fs` | `delete` | 파일/디렉토리 삭제 | Yes |
| `shell` | `exec` | 쉘 명령 실행 | Yes |
| `browser` | `open` | 브라우저 열기 | Yes |
| `browser` | `navigate` | URL 이동 | Yes |
| `browser` | `scrape` | 페이지 스크래핑 | No |
| `browser` | `click` | 요소 클릭 | Yes |
| `os` | `notify` | 시스템 알림 | Yes |
| `os` | `clipboard_read` | 클립보드 읽기 | No |
| `os` | `clipboard_write` | 클립보드 쓰기 | Yes |
| `os` | `applescript` | AppleScript 실행 (macOS) | Yes |
| `os` | `powershell` | PowerShell 실행 (Windows) | Yes |
| `web` | `search` | 웹 검색 | No |
| `web` | `http_request` | HTTP 요청 | No |

## 샘플 워크플로우

`shared/fixtures/workflows/` 에 5종의 샘플 워크플로우가 포함되어 있다:

| 워크플로우 | 설명 | 사용 툴 |
|-----------|------|---------|
| `simple-chat.yaml` | 단순 대화 (planner 만) | 없음 |
| `file-organizer.yaml` | 파일 정리 (planner + worker) | fs.list, fs.move, fs.read_file |
| `code-reviewer.yaml` | 코드 리뷰 (planner + reviewer + summarizer) | fs.list, fs.read_file, fs.write_file |
| `web-researcher.yaml` | 웹 리서치 (planner + researcher + summarizer) | web.search, web.http_request, fs.write_file |
| `multi-agent-debate.yaml` | 멀티 에이전트 토론 (supervisor + 2 workers) | 없음 (LLM 만 사용) |

## 정책 가이드

정책은 툴 호출의 허용/승인/차단 규칙을 정의한다. `shared/fixtures/policies/` 에 3종의 프리셋이 포함:

| 정책 | 모드 | 설명 |
|------|------|------|
| `default.yaml` | ask | 읽기 허용, 쓰기/쉘/브라우저는 승인 필요 |
| `strict.yaml` | strict | 쉘/OS 자동화 차단, 나머지는 모두 승인 필요 |
| `coding-assistant.yaml` | ask | 파일 읽기/쓰기 허용, 쉘은 승인, 브라우저/OS 차단 |

정책 모드:
- `auto`: 모든 작업 자동 허용 (주의: 위험)
- `ask`: 규칙에 따라 허용/승인/차단 판단
- `strict`: 명시적 허용 외 모든 작업에 승인 요구

## 문서 인덱스

| 문서 | 역할 |
|------|------|
| [Plan](./docs/01-plan/features/OrcaFlow.plan.md) | 프로젝트 목적/범위/요구사항/리스크 |
| [Glossary](./docs/01-plan/glossary.md) | 용어 SSoT |
| [Schema](./docs/01-plan/schema.md) | 엔티티/관계/DB/YAML 스키마 SSoT |
| [Conventions](./docs/01-plan/conventions.md) | 폴리글랏 코딩 규약 |
| [Design](./docs/02-design/features/OrcaFlow.design.md) | 아키텍처/IPC 프로토콜/정책 엔진 런타임 |
| [CLAUDE.md](./CLAUDE.md) | AI 협업 가이드 |

## FAQ

**Q: 어떤 LLM 을 지원하나요?**
A: OpenAI 호환 API 를 제공하는 모든 공급자를 지원합니다. Ollama, vLLM, llama.cpp, LM Studio (로컬), Together AI, Groq, Fireworks (클라우드) 등.

**Q: Docker 로 실행할 수 없나요?**
A: 의도적으로 지원하지 않습니다. OrcaFlow 의 핵심 가치는 에이전트가 사용자 PC 의 파일, 앱, 브라우저에 직접 접근하는 것입니다. 컨테이너 격리는 이를 불가능하게 합니다.

**Q: 에이전트가 위험한 작업을 하면 어떻게 되나요?**
A: 정책 엔진이 모든 툴 호출을 사전 검사합니다. 파괴적 작업은 사용자 승인을 요구하며, 변경 저널에 before/after 를 기록하고, 감사 로그에 불변 기록을 남깁니다.

**Q: API 키는 어디에 저장되나요?**
A: OS 키체인 (macOS Keychain, Windows Credential Manager) 에만 저장됩니다. config 파일, 코드, 로그에 평문 저장은 금지됩니다.

## 라이선스

TBD
