---
template: do
version: 1.0
feature: OrcaFlow
date: 2026-04-12
author: 2z
project: OrcaFlow
version_no: 0.1.0
---

# OrcaFlow Implementation Guide (Do Phase)

> **Summary**: 멀티 에이전트 오케스트레이션 플랫폼 OrcaFlow의 M1~M8 구현 가이드. 본 문서는 M1(뼈대 & 브릿지)를 중심으로 작성하며 이후 마일스톤은 진행되는 대로 업데이트한다.
>
> **Project**: OrcaFlow
> **Version**: 0.1.0
> **Author**: 2z
> **Date**: 2026-04-12
> **Status**: In Progress (M1)
> **Design Doc**: [OrcaFlow.design.md](./features/OrcaFlow.design.md)

---

## 1. Pre-Implementation Checklist

### 1.1 Documents Verified

- [x] Plan: `docs/01-plan/features/OrcaFlow.plan.md` (v0.2)
- [x] Schema: `docs/01-plan/schema.md` (v1.0)
- [x] Glossary: `docs/01-plan/glossary.md` (v1.0)
- [x] Conventions: `docs/01-plan/conventions.md` (v1.0)
- [x] Design: `docs/02-design/features/OrcaFlow.design.md` (v0.1)
- [x] 포맷터/린터 설정: `.editorconfig`, `rustfmt.toml`, `pyproject.toml`, `eslint.config.js`, `.prettierrc.json`, `tsconfig.json`

### 1.2 Environment Required (로컬 PC 전제)

- [ ] Rust toolchain 1.79+ (`rustup`) — Tauri 셸 빌드
- [ ] Tauri CLI v2 (`cargo install tauri-cli --version '^2'`) — 개발 서버/번들링
- [ ] Node.js 20+ 와 pnpm 9+ — 프론트엔드
- [ ] Python 3.11+ 와 [uv](https://docs.astral.sh/uv/) — sidecar 의존성 관리/실행
- [ ] Ollama (선택) — 로컬 LLM 테스트용
- [ ] macOS: Xcode Command Line Tools (`xcode-select --install`)
- [ ] Windows: VS Build Tools + WebView2 Runtime
- [ ] Linux: `webkit2gtk`, `libayatana-appindicator3-dev`, `librsvg2-dev`

---

## 2. Milestone M1 — 뼈대 & 브릿지

### 2.1 목표

M1 종료 시점에 **Tauri 데스크톱 앱이 Python sidecar를 자동 기동하고, `/health` 응답을 받아 Frontend에서 "sidecar ready"를 표시**한다. 이후 모든 마일스톤은 이 통신 경로 위에서 확장한다.

### 2.2 Implementation Order

#### Phase 1 — Python Sidecar (작은 FastAPI 앱)

| # | Task | File | Status |
|:-:|------|------|:------:|
| 1 | Settings (config.toml + env 로딩) | `sidecar/orca_core/config.py` | ☐ |
| 2 | 도메인 예외 | `sidecar/orca_core/errors.py` | ☐ |
| 3 | 토큰 인증 미들웨어 | `sidecar/orca_core/ipc/auth.py` | ☐ |
| 4 | FastAPI 팩토리 | `sidecar/orca_core/ipc/http_app.py` | ☐ |
| 5 | `/health` 라우트 | `sidecar/orca_core/ipc/routes/health.py` | ☐ |
| 6 | `/version` 라우트 | `sidecar/orca_core/ipc/routes/version.py` | ☐ |
| 7 | `/config` 라우트(R/O) | `sidecar/orca_core/ipc/routes/config.py` | ☐ |
| 8 | Entry point (handshake 출력) | `sidecar/orca_core/__main__.py` | ☐ |
| 9 | Smoke 테스트 | `sidecar/tests/test_health.py` | ☐ |

#### Phase 2 — Tauri Shell (Rust)

| # | Task | File | Status |
|:-:|------|------|:------:|
| 10 | `Cargo.toml` (tauri v2, reqwest, serde) | `app/src-tauri/Cargo.toml` | ☐ |
| 11 | `tauri.conf.json` | `app/src-tauri/tauri.conf.json` | ☐ |
| 12 | `build.rs` | `app/src-tauri/build.rs` | ☐ |
| 13 | 에러 타입 | `app/src-tauri/src/errors.rs` | ☐ |
| 14 | 앱 설정 모듈 | `app/src-tauri/src/config/mod.rs` | ☐ |
| 15 | Sidecar spawn + handshake | `app/src-tauri/src/bridge/sidecar.rs` | ☐ |
| 16 | HTTP 클라이언트 (토큰 주입) | `app/src-tauri/src/bridge/client.rs` | ☐ |
| 17 | `app_ready` 커맨드 | `app/src-tauri/src/commands/health.rs` | ☐ |
| 18 | `config_get` 커맨드 | `app/src-tauri/src/commands/config.rs` | ☐ |
| 19 | `main.rs` (앱 기동·상태 등록) | `app/src-tauri/src/main.rs` | ☐ |

#### Phase 3 — Frontend (Vite + React)

| # | Task | File | Status |
|:-:|------|------|:------:|
| 20 | `package.json` | `frontend/package.json` | ☐ |
| 21 | `vite.config.ts` | `frontend/vite.config.ts` | ☐ |
| 22 | `tsconfig.node.json` | `frontend/tsconfig.node.json` | ☐ |
| 23 | `index.html` | `frontend/index.html` | ☐ |
| 24 | Entry (`main.tsx`) | `frontend/src/main.tsx` | ☐ |
| 25 | Root `App.tsx` | `frontend/src/App.tsx` | ☐ |
| 26 | IPC 어댑터 (`invoke` 래퍼) | `frontend/src/lib/api/app.ts` | ☐ |
| 27 | 앱 스토어 (Zustand) | `frontend/src/stores/app-store.ts` | ☐ |
| 28 | 타입 (AppStatus 등) | `frontend/src/types/app.types.ts` | ☐ |
| 29 | 기본 스타일 | `frontend/src/styles/index.css` | ☐ |

#### Phase 4 — 통합 / 스모크

| # | Task | Status |
|:-:|------|:------:|
| 30 | `pnpm --filter frontend dev` 동작 확인 | ☐ |
| 31 | `cargo tauri dev` 동작, 프론트 로드 | ☐ |
| 32 | Sidecar 자동 spawn 후 `/health` 200 | ☐ |
| 33 | Frontend UI 에 "Sidecar ready · port/version" 표시 | ☐ |

### 2.3 Handshake Protocol (M1 핵심)

Tauri 가 sidecar 프로세스를 spawn 할 때 **port와 token을 stdout JSON 한 줄로 수신**한다. 이 한 줄이 수신되기 전까지 Tauri 는 sidecar 가 준비되지 않은 것으로 취급한다.

**stdout 첫 줄 예시 (sidecar → Tauri)**:
```json
{"kind":"handshake","port":54321,"token":"3f...","pid":12345,"version":"0.1.0"}
```

- `kind="handshake"` 외의 stdout 줄은 `app.log` 로 릴레이
- 수신 타임아웃: 기본 10초, 초과 시 sidecar kill + 재시도(최대 2회)
- 이후 모든 요청은 헤더 `X-Orca-Token: <token>` 필수
- 바인딩: 무조건 `127.0.0.1`, 포트는 OS 자동 할당(`port=0`)

### 2.4 Dependency 설치 명령

```bash
# Rust + Tauri
rustup update
cargo install tauri-cli --version '^2' --locked

# Node / pnpm
corepack enable
corepack prepare pnpm@latest --activate

# Python (uv 권장)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 프론트엔드 의존성 (나중에 package.json 있는 후)
cd frontend && pnpm install

# Python 의존성
cd sidecar && uv sync

# Tauri 개발 서버 (루트에서)
cd app/src-tauri && cargo tauri dev
```

---

## 3. Key Files to Create (M1)

### 3.1 신규 파일 (29개)

위 §2.2 표 참조. 총 29개 신규 파일.

### 3.2 수정 파일

M1 에서는 수정 대상 없음. 모두 신규 생성.

---

## 4. Dependencies

### 4.1 Python (sidecar/pyproject.toml 에 이미 선언)

`fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `anyio`, `httpx`, `structlog`, `pyyaml`

### 4.2 Rust (app/src-tauri/Cargo.toml)

- `tauri` 2.x
- `tauri-build` 2.x
- `serde`, `serde_json`
- `thiserror`, `anyhow`
- `reqwest` (sidecar 호출)
- `tokio` (async runtime)
- `tracing`, `tracing-subscriber`
- `rand` (개발용 nonce 등 필요 시)

### 4.3 Frontend (frontend/package.json)

- `react` 18.3, `react-dom`
- `@tauri-apps/api` 2.x
- `zustand`
- `clsx`, `tailwind-merge`
- Dev: `vite`, `@vitejs/plugin-react`, `typescript`, `prettier`, `eslint` + 플러그인들

---

## 5. Implementation Notes

### 5.1 Design Decisions (from design.md §6.7)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Sidecar 통신 | HTTP 127.0.0.1 + SSE | 구현 단순, 프로세스 경계 명확 |
| Sidecar 인증 | 기동 시 랜덤 토큰 헤더 | localhost 라도 타 프로세스 접근 차단 |
| 포트 할당 | OS 자동(0) | 충돌 방지 |
| 설정 1차 | `~/.orcaflow/config.toml` | 환경변수 의존 탈피 |
| 시크릿 | OS 키체인 (M3+) | DB/파일 평문 금지 |
| Python 패키지 | uv + hatchling | 빠른 의존성 해결, 재현성 |

### 5.2 Architecture Checklist (Conventions §6)

- [x] Domain 레이어는 이 M1 에서 아직 생성하지 않음(M2 에서)
- [x] Presentation → App Shell → Application (sidecar ipc) 경로만 사용
- [x] Frontend 에서 `@tauri-apps/api` 직접 사용은 `src/lib/api/` 에서만
- [x] sidecar 바인딩 `127.0.0.1` 고정

### 5.3 Security Checklist (Conventions §8)

- [x] Sidecar 외부 바인딩 금지
- [x] 토큰은 sidecar 가 생성 → stdout 한 줄로만 Tauri 에 전달
- [x] 토큰 로깅 금지 (로그에 표시 시 앞 6자 + `***`)
- [x] config 읽기 전용 (M1), 쓰기는 M2+

### 5.4 Convention Checklist

- [x] 파일명: Rust snake_case, Python snake_case, TS 컴포넌트 PascalCase
- [x] Pydantic 모델 필드 = schema.md 필드와 일치(해당되는 범위 내)
- [x] JSON 페이로드는 snake_case, 프론트엔드 내부 camelCase 변환(M1 에선 AppStatus 정도)
- [x] import 순서 규칙 준수

### 5.5 Things to Avoid

- ❌ 토큰·포트 하드코딩
- ❌ `0.0.0.0` 바인딩
- ❌ `.env` 파일에 시크릿 저장
- ❌ 프론트 컴포넌트에서 `invoke` / `fetch` 직접 호출 (반드시 `lib/api/` 경유)
- ❌ `println!`/`console.log` 프로덕션 코드에 남김 → 구조화 로그 사용

---

## 6. Testing Checklist (M1)

### 6.1 Manual Smoke

- [ ] `cargo tauri dev` 기동 시 Frontend 가 "Sidecar: starting…" → "Sidecar: ready" 로 전이
- [ ] DevTools 콘솔에 불필요한 에러 없음
- [ ] sidecar 종료 시 Tauri 가 재시작 또는 명시적 에러 표시

### 6.2 Python 단위 테스트

- [ ] `uv run pytest sidecar/tests/test_health.py` 성공
- [ ] 인증 토큰 없이 `/health` 호출 → 401

### 6.3 코드 품질

- [ ] `ruff check sidecar/` 통과
- [ ] `mypy sidecar/orca_core` 통과 (M1 범위 내 파일만)
- [ ] `cargo clippy --manifest-path app/src-tauri/Cargo.toml -- -D warnings` 통과
- [ ] `pnpm --filter frontend lint` 통과 (M1 규모 내)

---

## 7. Progress Tracking

| Date | Tasks Completed | Notes |
|------|-----------------|-------|
| 2026-04-12 | M1 스캐폴딩 시작 | 29개 신규 파일 일괄 생성 예정 |

---

## 8. Post-Implementation

### 8.1 Self-Review

- [ ] 모든 M1 Phase 1~4 파일 생성
- [ ] 코드가 실제 실행 가능 (필요 툴체인 설치 시)
- [ ] Conventions 준수

### 8.2 Next Milestones

M1 완료 후:

- **M2 — Domain & Persistence**: schema/policy/audit/journal 순수 레이어 + SQLite 초기화
- **M3 — Providers & Tools 최소**: `OpenAICompatibleAdapter`, `fs.*` 툴, `ToolRuntime`
- **M4 — Orchestrator + Planner**: GraphRunner, Planner 구조화 출력, `/runs` + SSE
- **M5 — UI 핵심**: Chat, Run Monitor, Approval Dialog
- **M6 — 노드 에디터 & Policy UI**
- **M7 — 고급 툴 & E2E 시나리오 3종**
- **M8 — 번들/배포**

Gap 분석은 M4 이후 `/pdca analyze OrcaFlow` 로 실행 권장 (초기 뼈대만으로는 Design 전체와의 매치가 낮게 나오므로).

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-04-12 | M1 가이드 초안 | 2z |
