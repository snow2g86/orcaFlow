---
template: plan
version: 1.2
feature: OrcaFlow
date: 2026-04-12
author: 2z
project: OrcaFlow
version_no: 0.1.0
---

# OrcaFlow Planning Document

> **Summary**: 사용자가 자연어와 UI를 조합해 원하는 방식으로 오픈 LLM 기반 멀티 에이전트 워크플로우를 구성·실행할 수 있는 오케스트레이션 플랫폼.
>
> **Project**: OrcaFlow
> **Version**: 0.1.0
> **Author**: 2z
> **Date**: 2026-04-12
> **Status**: Draft

---

## 1. Overview

### 1.1 Purpose

- **사용자 PC에서 직접 실행되며 파일·앱·OS에 접근해 실제 업무를 수행하는 진짜 에이전트**를 제공한다.
- 비개발자도 자연어로 복잡한 멀티 에이전트 작업을 설계·실행할 수 있게 한다.
- 개발자는 동일한 결과물을 UI 또는 설정으로 재사용·공유·버전관리할 수 있게 한다.
- 사용자가 원하는 LLM(로컬/자체호스팅/클라우드 오픈 모델)을 자유롭게 선택·전환할 수 있다.

### 1.1.1 Core Principle: Native-First, No Sandbox Isolation

OrcaFlow는 **컨테이너/가상화 격리 없이 사용자 PC에서 네이티브로 실행**된다. 에이전트가 실제로 파일을 열고, 앱을 조작하고, 로컬 디렉토리·개발 환경·DB·IDE·브라우저 프로필 등에 직접 접근해야 "업무를 대신 수행하는 에이전트"가 성립하기 때문이다. Docker 같은 격리 환경은 네트워크·파일시스템 단절로 이 목적을 훼손하므로 채택하지 않는다.

### 1.2 Background

- 기존 멀티 에이전트 프레임워크(LangGraph, AutoGen, CrewAI 등)는 코드 작성 진입장벽이 높다.
- ComfyUI/n8n은 시각적이지만 LLM 에이전트 오케스트레이션에 특화되어 있지 않다.
- 상용 LLM에 락인되지 않고 오픈 모델을 중심으로 구성 가능한 플랫폼 수요 증가.
- 사용자는 "자기 방식대로" 에이전트 협업 규칙을 정의·커스터마이즈하기를 원한다.

### 1.3 Related Documents

- Requirements: (TBD - 본 Plan 문서에서 초안)
- References:
  - ComfyUI (노드 기반 워크플로우)
  - LangGraph / AutoGen / CrewAI (멀티 에이전트 패턴)
  - n8n (워크플로우 자동화)
  - Ollama / vLLM / Text Generation Inference (오픈 LLM 실행)

---

## 2. Scope

### 2.1 In Scope

- [ ] 오픈 LLM 공급자 통합 (Ollama, vLLM, TGI, llama.cpp, LM Studio, Together, Groq, Fireworks 등)
- [ ] 멀티 에이전트 역할(Role) 정의 및 협업 패턴 (Supervisor, Sequential, Parallel, Debate)
- [ ] 채팅형 자연어 명령 인터페이스 (사용자 지시 → 워크플로우 자동 생성)
- [ ] UI 기반 워크플로우 편집기 (에이전트/툴/분기 시각 편집)
- [ ] 워크플로우 저장/불러오기/공유 (YAML/JSON export)
- [ ] 실행 모니터링 (에이전트별 로그, 토큰/지연 시간, 중간 산출물)
- [ ] **로컬 OS 툴 통합**: 파일 시스템(읽기/쓰기/이동), 쉘 명령 실행, 프로세스 제어, 앱 자동화(AppleScript/PowerShell), 브라우저 자동화(Playwright), 키보드/마우스 이벤트, 클립보드, 알림
- [ ] 웹 툴: 검색, HTTP/API 호출, 스크래핑
- [ ] LLM 프로파일 관리 (엔드포인트·모델·파라미터 프리셋)
- [ ] **네이티브 데스크톱 설치/실행 (Docker 없음)** — Tauri 번들 또는 단일 바이너리로 배포
- [ ] 권한 기반 툴 접근 제어 (경로 화이트리스트, 명령 허용 리스트, 민감 작업 사용자 승인)

### 2.2 Out of Scope (v0.1 기준)

- 상용 LLM(OpenAI, Anthropic 등) 1차 지원 — 추후 플러그인 형태로 확장
- 자체 LLM 학습/파인튜닝 기능
- 엔터프라이즈 SSO·권한 관리 (v1.0 이후)
- 모바일 네이티브 앱 (데스크톱 우선)
- **Docker/컨테이너 기반 실행** — 격리가 에이전트의 로컬 접근을 막으므로 채택하지 않음
- 멀티 유저 서버 모드 (v0.1은 단일 사용자 로컬 실행 전용)

---

## 3. Requirements

### 3.1 Functional Requirements

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-01 | 사용자가 LLM 공급자/모델을 추가·전환할 수 있다 (Ollama, vLLM, OpenAI 호환 API 등) | High | Pending |
| FR-02 | 채팅 입력으로 "이 작업을 A 에이전트와 B 에이전트가 협업해 처리" 같은 지시를 해석해 워크플로우를 생성한다 | High | Pending |
| FR-03 | 사용자는 UI에서 에이전트 노드를 추가/편집/연결하고 YAML로 저장할 수 있다 | High | Pending |
| FR-04 | 생성된 워크플로우를 실행하고 각 에이전트의 입출력을 실시간 모니터링할 수 있다 | High | Pending |
| FR-05 | 에이전트는 사용자 PC의 파일·쉘·프로세스·앱·브라우저·클립보드 등에 직접 접근해 업무를 수행할 수 있다 | High | Pending |
| FR-06 | 민감 작업(파일 삭제, 외부 네트워크, 시스템 변경)은 사용자 승인 또는 화이트리스트 정책을 거친다 | High | Pending |
| FR-07 | 동일 워크플로우를 다른 LLM 프로파일로 재실행해 결과를 비교할 수 있다 | Medium | Pending |
| FR-08 | 워크플로우/프롬프트/툴 설정을 export/import할 수 있다 | Medium | Pending |
| FR-09 | 실행 히스토리와 중간 산출물을 기록·재현한다 | Medium | Pending |
| FR-10 | 사용자 정의 에이전트 템플릿·툴을 등록·재사용할 수 있다 | Low | Pending |
| FR-11 | 데스크톱 앱으로 설치되며 시스템 트레이에서 상주·호출 가능하다 | Medium | Pending |

### 3.2 Non-Functional Requirements

| Category | Criteria | Measurement Method |
|----------|----------|-------------------|
| Performance | 로컬 Ollama 기준 첫 토큰 응답 < 3s (7B 모델) | 실행 로그 타임스탬프 |
| Scalability | 동시 에이전트 10개 병렬 실행 가능 (단일 PC) | 부하 테스트 |
| Usability | 비개발자가 설치 후 5분 내 첫 워크플로우 실행 | 사용성 테스트 |
| Portability | 설치 파일 한 번으로 실행, 외부 클라우드 의존 없음 (macOS/Windows/Linux 네이티브 빌드) | 설치 스크립트 검증 |
| **Locality** | 에이전트가 사용자 홈/프로젝트 디렉토리에 즉시 접근 가능 | 파일 작업 E2E 테스트 |
| **Security** | 모든 파괴적 작업은 정책 엔진을 거치고 감사 로그 기록 | 정책 단위 테스트 + 감사 로그 검증 |
| Extensibility | 새 LLM 공급자/툴을 플러그인 형태로 추가 | 플러그인 샘플 작성 |
| Observability | 모든 LLM 호출·툴 호출의 프롬프트/토큰/지연/결과 기록 | 구조화 로그 (JSON) |

---

## 4. Success Criteria

### 4.1 Definition of Done (v0.1 MVP)

- [ ] 로컬 Ollama + 1개 외부 API(Groq 또는 Together)로 실행되는 데모
- [ ] 자연어 지시 → 워크플로우 자동 생성 예제 3종 이상 동작
- [ ] UI 편집기로 에이전트 연결·실행 가능
- [ ] **실제 로컬 업무 시나리오 3종 동작**: (1) 로컬 폴더 정리/이름 변경, (2) 코드베이스 읽고 리팩토링 PR 준비, (3) 브라우저 자동 탐색 후 요약 저장
- [ ] 실행 모니터링 뷰에서 에이전트별 토큰/시간/툴 호출 확인 가능
- [ ] **macOS/Windows 네이티브 데스크톱 앱 설치 파일 생성** (Tauri 빌드)
- [ ] 권한 정책 엔진 동작 (화이트리스트/승인 프롬프트)
- [ ] README 및 사용자 가이드 작성

### 4.2 Quality Criteria

- [ ] 핵심 로직(플래너, 실행기, 공급자 어댑터, 정책 엔진) 단위 테스트 커버리지 70% 이상
- [ ] Zero lint errors
- [ ] **네이티브 앱 빌드/실행 성공 (macOS dmg, Windows msi)**
- [ ] 샘플 워크플로우 5종 동작 확인
- [ ] 파괴적 작업 100%가 정책 엔진·감사 로그를 경유

---

## 5. Risks and Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| 오픈 LLM 성능 편차로 자연어 지시 해석 실패 | High | High | 플래너용 모델은 별도 지정(더 큰 모델), 실패 시 UI 수동 편집으로 폴백 |
| 공급자 API 스펙 파편화(Ollama/vLLM/OpenAI 호환) | Medium | High | OpenAI 호환 인터페이스를 기본으로 하고 어댑터 레이어 분리 |
| 에이전트 루프/무한 재귀로 비용·시스템 폭증 | High | Medium | 스텝 제한, 토큰 예산, 타임아웃, 동시 실행 제한을 기본값으로 강제 |
| **네이티브 실행으로 인한 보안 위험(파일 삭제, 명령 실행 오·남용)** | **Critical** | High | 정책 엔진(경로/명령 화이트리스트), 위험 작업 사용자 승인(Human-in-the-loop), Dry-run 모드 기본, 감사 로그, OS 레벨 권한 프롬프트 활용(Tauri permission API, macOS TCC) |
| 크로스 플랫폼 네이티브 툴 파편화(AppleScript vs PowerShell vs Linux) | Medium | High | 툴을 공통 인터페이스 뒤에 두고 OS별 구현 분리, v0.1은 macOS·Windows 우선 |
| 설치·설정 복잡도로 사용자 이탈 | Medium | Medium | Tauri 단일 인스톨러, 최초 실행 위저드, 프리셋 템플릿 제공 |
| 시각 편집기 구현 복잡도 | Medium | High | v0.1은 YAML 편집 + 읽기 전용 시각화로 시작, v0.2에서 편집 확장 |
| 에이전트가 의도와 다른 파일·계정을 건드림 | High | Medium | 드라이런 → 플랜 제시 → 사용자 확인 → 실행 기본 플로우, 모든 변경은 되돌릴 수 있도록 저널링 |

---

## 6. Architecture Considerations

### 6.1 Project Level Selection

| Level | Characteristics | Recommended For | Selected |
|-------|-----------------|-----------------|:--------:|
| Starter | 단순 구조 | 정적 사이트 | ☐ |
| **Dynamic** | Feature 모듈 + 서비스 계층 | 풀스택 웹 앱, SaaS MVP | ☑ |
| Enterprise | 엄격한 계층 분리, DI, 마이크로서비스 | 대규모 시스템 | ☐ |

**선택 근거**: 데스크톱 네이티브 앱(Tauri) + 실행 엔진(Python 사이드카) + 웹뷰 UI. 단일 사용자 로컬 실행에 최적화.

### 6.2 Key Architectural Decisions

| Decision | Options | Selected | Rationale |
|----------|---------|----------|-----------|
| **App Shell** | Electron / Tauri / Native | **Tauri** | 작은 바이너리, Rust 보안성, OS 권한 API 내장, 크로스 플랫폼 |
| Frontend | Next.js / Vite+React / SvelteKit | **Vite + React** | Tauri 웹뷰에 최적, SSR 불필요, 번들 크기 작음 |
| Backend Runtime | Node.js / Python(FastAPI) / Rust | **Python (FastAPI, Tauri sidecar)** | LLM/에이전트 생태계 활용, Tauri sidecar로 함께 번들링 |
| Agent Core | LangGraph / Custom / AutoGen | **LangGraph (경량 래퍼)** | 그래프 기반이 노드 에디터 UI 모델과 1:1 매핑 |
| LLM Adapter | OpenAI 호환 기본 + 어댑터 | **OpenAI SDK + 어댑터** | Ollama/vLLM/Together/llama.cpp/LM Studio 모두 OpenAI 호환 |
| State Management (UI) | Zustand / Redux / Jotai | **Zustand** | 경량, 노드 에디터 상태 관리에 적합 |
| Node Editor | React Flow / Rete.js | **React Flow** | 성숙도·커뮤니티·그래프 UX 표준 |
| Styling | Tailwind / CSS Modules | **Tailwind + shadcn/ui** | 빠른 UI 구축, 디자인 일관성 |
| Realtime (UI↔백엔드) | WebSocket / SSE / Tauri IPC | **Tauri IPC + SSE** | 로컬 IPC는 Tauri 네이티브 사용, 긴 스트리밍은 SSE |
| Storage | SQLite / Postgres / JSON 파일 | **SQLite (사용자 홈)** | 로컬 단일 사용자, 외부 의존 없음 |
| **Browser Automation** | Playwright / Puppeteer / Selenium | **Playwright** | 멀티 브라우저 지원, Python/JS 양쪽 바인딩 |
| **OS Automation** | AppleScript / PowerShell / xdotool | **OS별 어댑터** | 공통 인터페이스, macOS=AppleScript/JXA, Windows=PowerShell, Linux=ydotool/xdotool |
| Testing | Vitest / Pytest / Playwright | **Pytest + Vitest + Playwright** | 백/프론트/E2E 분리 |
| **Packaging** | ~~Docker~~ / Tauri bundler / PyInstaller | **Tauri bundler + Python sidecar** | dmg/msi/AppImage 단일 인스톨러, 네이티브 권한 확보 |
| **Policy Engine** | Custom rule engine / OPA / 코드 기반 | **코드 기반 정책 + YAML 룰** | 단순성 우선, YAML로 사용자 커스터마이즈 |

### 6.3 Clean Architecture Approach

```
Selected Level: Dynamic (단일 사용자 로컬 데스크톱 앱)

OrcaFlow/
├── app/                         # Tauri 데스크톱 셸 (Rust)
│   ├── src-tauri/              # Rust 메인 프로세스, 권한 API, 사이드카 실행
│   │   ├── tauri.conf.json
│   │   └── src/
│   └── tauri.conf.json
├── frontend/                    # Vite + React UI (Tauri 웹뷰)
│   ├── src/
│   │   ├── components/         # shadcn/ui 기반
│   │   ├── features/
│   │   │   ├── chat/           # 자연어 명령 인터페이스
│   │   │   ├── editor/         # React Flow 노드 에디터
│   │   │   ├── monitor/        # 실행 모니터링
│   │   │   └── settings/       # LLM 프로파일, 정책, 툴
│   │   └── stores/             # Zustand
│   └── package.json
├── sidecar/                     # Python FastAPI 실행 엔진 (Tauri sidecar로 번들)
│   ├── orca_core/
│   │   ├── orchestrator/       # 에이전트 실행 엔진, 플래너
│   │   ├── providers/          # LLM 어댑터 (Ollama, vLLM, llama.cpp, Together, Groq)
│   │   ├── tools/
│   │   │   ├── fs/             # 파일 I/O (권한 검증)
│   │   │   ├── shell/          # 쉘/명령 실행
│   │   │   ├── browser/        # Playwright 래퍼
│   │   │   ├── os/             # AppleScript/PowerShell 어댑터
│   │   │   ├── web/            # HTTP/검색/스크래핑
│   │   │   └── custom/         # 사용자 플러그인
│   │   ├── policy/             # 권한 정책 엔진
│   │   ├── journal/            # 실행/변경 저널 (되돌리기)
│   │   └── schema/             # 워크플로우 YAML 스키마
│   └── pyproject.toml
├── shared/                      # 공통 타입 (TS↔Python 스키마)
├── docs/
└── README.md
```

**데이터/상태 저장 위치**: 사용자 홈 디렉토리
```
~/.orcaflow/
├── db.sqlite                   # 히스토리, 워크플로우, 프로파일
├── workflows/                  # YAML 워크플로우 저장소
├── policies/                   # 권한 정책 파일
├── logs/                       # 구조화 로그, 감사 로그
└── config.toml                 # 앱 설정
```

---

## 7. Convention Prerequisites

### 7.1 Existing Project Conventions

- [ ] `CLAUDE.md` (신규 생성 예정)
- [ ] `docs/01-plan/conventions.md` (Phase 2에서 작성 예정)
- [ ] ESLint / Prettier / Ruff / Black
- [ ] TypeScript `tsconfig.json`
- [ ] Python `pyproject.toml`

### 7.2 Conventions to Define/Verify

| Category | Current State | To Define | Priority |
|----------|---------------|-----------|:--------:|
| Naming | missing | 컴포넌트 PascalCase, 파일 kebab-case, Python snake_case | High |
| Folder structure | missing | 위 6.3 구조 확정 | High |
| Import order | missing | ESLint import/order, isort | Medium |
| Environment variables | missing | `.env.example` 유지 강제 | High |
| Error handling | missing | 공급자 에러 정규화 타입 정의 | High |
| Logging | missing | JSON 구조화 로그 (에이전트, 토큰, latency) | High |

### 7.3 Configuration (환경변수 대신 `~/.orcaflow/config.toml` 중심)

| Key | Purpose | Scope | To Be Created |
|----------|---------|-------|:-------------:|
| `db.path` | SQLite 파일 경로 (기본 `~/.orcaflow/db.sqlite`) | Local | ☑ |
| `providers.default` | 기본 LLM 프로파일 이름 | Local | ☑ |
| `providers.ollama.base_url` | Ollama 엔드포인트 (기본 `http://localhost:11434`) | Local | ☑ |
| `providers.vllm.base_url` | 자체 호스팅 vLLM | Local | ☐ |
| `providers.together.api_key` | Together API 키 (OS 키체인 저장) | Secret | ☐ |
| `providers.groq.api_key` | Groq API 키 (OS 키체인 저장) | Secret | ☐ |
| `policy.mode` | `strict` / `ask` / `trusted` | Local | ☑ |
| `policy.paths.allow` | 파일 접근 허용 경로 리스트 | Local | ☑ |
| `policy.shell.allow` | 허용된 쉘 명령/패턴 | Local | ☑ |
| `sidecar.port` | Python 사이드카 내부 포트 (자동 할당 기본) | Local | ☐ |

**원칙**: 단일 사용자 로컬 앱이므로 `.env` 기반 서버 설정 대신 TOML 설정 파일 + OS 키체인(Tauri keychain 플러그인)을 사용. 환경변수는 개발 빌드와 디버그용으로만 유지.

### 7.4 Pipeline Integration

| Phase | Status | Document Location |
|-------|:------:|-------------------|
| Phase 1 (Schema) | ☐ | `docs/01-plan/schema.md` |
| Phase 2 (Convention) | ☐ | `docs/01-plan/conventions.md` |
| Phase 3 (Mockup) | ☐ | `docs/01-plan/mockup.md` |

---

## 8. Next Steps

1. [ ] 본 Plan 문서 검토 및 승인
2. [ ] Phase 1 Schema — 워크플로우/에이전트/툴/정책 YAML 스키마 정의
3. [ ] Phase 2 Convention — 폴더 규칙·네이밍·로깅·감사 로그 규약 문서화
4. [ ] Phase 3 Mockup — 채팅 + 노드 에디터 + 모니터링 + 정책 승인 다이얼로그 UI 목업
5. [ ] `/pdca design OrcaFlow` — 설계 문서 작성 (Tauri+FastAPI sidecar 연동, 정책 엔진, 툴 아키텍처)
6. [ ] 프로토타이핑: Tauri 껍데기 + Python sidecar IPC 최소 예제 (Ollama 호출 → 파일 작업 에이전트 한 번 실행)

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-04-12 | Initial draft (멀티 에이전트 오케스트레이션 플랫폼 초안) | 2z |
| 0.2 | 2026-04-12 | **Docker/컨테이너 격리 제거, 네이티브 데스크톱(Tauri+Python sidecar) 아키텍처로 전환.** 로컬 OS 접근·정책 엔진·감사 로그·사용자 승인 플로우 추가 | 2z |
