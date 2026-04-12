---
template: design
version: 1.2
feature: OrcaFlow
date: 2026-04-12
author: 2z
project: OrcaFlow
version_no: 0.1.0
---

# OrcaFlow Design Document

> **Summary**: 사용자 자연어 + 노드 에디터로 구성한 멀티 에이전트 워크플로우가, 정책 엔진과 저널·감사 레이어를 거쳐 사용자 PC 리소스에 직접 접근해 업무를 수행하는 네이티브 데스크톱 앱의 설계.
>
> **Project**: OrcaFlow
> **Version**: 0.1.0
> **Author**: 2z
> **Date**: 2026-04-12
> **Status**: Draft
> **Planning Doc**: [OrcaFlow.plan.md](../../01-plan/features/OrcaFlow.plan.md)

### Pipeline References

| Phase | Document | Status |
|-------|----------|--------|
| Phase 1 | [Schema Definition](../../01-plan/schema.md) | ✅ |
| Phase 1 | [Glossary](../../01-plan/glossary.md) | ✅ |
| Phase 2 | [Coding Conventions](../../01-plan/conventions.md) | ✅ |
| Phase 2 | [Root Conventions](../../../CONVENTIONS.md) | ✅ |
| Phase 2 | [CLAUDE.md](../../../CLAUDE.md) | ✅ |
| Phase 3 | Mockup | ⏭ (pending) |
| Phase 4 | API Spec | 본 문서 §4 |

> 본 문서는 Plan/Schema/Conventions 를 전제로 하며 중복 정의하지 않는다. 변경이 필요하면 원본을 먼저 수정한다.

---

## 1. Overview

### 1.1 Design Goals

1. **"진짜" 로컬 에이전트**: OrcaFlow 프로세스가 사용자 PC의 파일/쉘/브라우저/OS API에 직접 접근해 업무를 수행한다.
2. **오픈 LLM 자유도**: Ollama/vLLM/llama.cpp/LM Studio/Together/Groq/Fireworks 등 OpenAI 호환 공급자를 탈부착한다.
3. **안전 기본값**: 파괴적 작업은 정책 → 승인 → 저널 → 감사 순서를 강제하고 되돌릴 수 있다.
4. **자연어 ↔ 그래프 왕복**: 채팅형 지시와 노드 에디터가 같은 워크플로우 YAML을 편집한다.
5. **재현성**: 모든 Run은 워크플로우 YAML 스냅샷과 함께 저장되어 재실행·비교 가능하다.
6. **확장성**: Tool·Provider·AgentRole·Policy 를 플러그인으로 추가할 수 있다.
7. **단일 사용자 로컬 앱**: 멀티 유저·서버 모드를 v0.1에서 설계상 배제한다.

### 1.2 Design Principles

- **Native-first, no container isolation** — Docker/VM을 통한 OrcaFlow 자체 격리는 금지 (Plan §1.1.1).
- **Domain Purity** — `schema / policy / audit / journal` 은 외부 I/O 의존이 없는 순수 계층 (Conventions §6.3).
- **Policy Before Action** — 모든 쓰기·네트워크·파괴적 작업은 정책 엔진을 선형적으로 통과해야 한다.
- **Journal Before Side-Effect** — reversible 작업은 변경 기록 후에만 실행한다.
- **Append-only Audit** — 감사 로그는 UPDATE/DELETE 경로가 없다.
- **Snapshot over Reference** — Run은 Workflow YAML 스냅샷을 보관해 시간에 견딘다.
- **Stream by Default** — 에이전트 산출물·LLM 토큰·툴 로그는 스트리밍으로 UI에 흘려보낸다.
- **Fail Loud, Fail Safe** — 정책/감사/저널 레이어 오류는 조용히 무시하지 않고 Run을 즉시 `blocked/failed`.

---

## 2. Architecture

### 2.1 Component Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                         User's macOS/Windows/Linux                   │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                    OrcaFlow Desktop App                         │  │
│  │                                                                │  │
│  │  ┌──────────────────────┐       ┌─────────────────────────┐   │  │
│  │  │  Frontend (WebView)  │◀─IPC─▶│   Tauri Shell (Rust)    │   │  │
│  │  │  Vite + React +      │       │   commands/, bridge/,   │   │  │
│  │  │  React Flow          │       │   permission/           │   │  │
│  │  └──────────────────────┘       └──────────┬──────────────┘   │  │
│  │                                             │ sidecar IPC      │  │
│  │                                             │ (HTTP + SSE on   │  │
│  │                                             │  127.0.0.1:<p>)  │  │
│  │                                  ┌──────────▼──────────────┐   │  │
│  │                                  │  Python Sidecar         │   │  │
│  │                                  │  FastAPI + orca_core    │   │  │
│  │                                  │                         │   │  │
│  │                                  │  ┌───────────────────┐  │   │  │
│  │                                  │  │  ipc / HTTP API   │  │   │  │
│  │                                  │  └─────────┬─────────┘  │   │  │
│  │                                  │            │            │   │  │
│  │                                  │  ┌─────────▼─────────┐  │   │  │
│  │                                  │  │   Orchestrator     │  │   │  │
│  │                                  │  │  (Planner + Graph  │  │   │  │
│  │                                  │  │   Runner)          │  │   │  │
│  │                                  │  └─────────┬─────────┘  │   │  │
│  │                                  │            │            │   │  │
│  │                                  │  ┌───┬───┬─┴──┬───┬───┐ │   │  │
│  │                                  │  │Pol│Aud│Jrn │Prv│Tol│ │   │  │
│  │                                  │  │icy│it │l   │dr │s  │ │   │  │
│  │                                  │  └───┴───┴────┴───┴───┘ │   │  │
│  │                                  │            │            │   │  │
│  │                                  │  ┌─────────▼─────────┐  │   │  │
│  │                                  │  │   Persistence     │  │   │  │
│  │                                  │  │   (SQLite)        │  │   │  │
│  │                                  │  └───────────────────┘  │   │  │
│  │                                  └─────────────────────────┘   │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐    │
│  │ ~/.orcaflow/     │  │  Local LLM       │  │  User Files /   │    │
│  │ db, logs, ...    │  │  (Ollama/vLLM)   │  │  Apps / Browser │    │
│  └──────────────────┘  └──────────────────┘  └─────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
                                │
                                ▼ (optional outbound, 정책 허용 시)
            External LLM APIs (Together/Groq/Fireworks)
```

### 2.2 3-Process Model

OrcaFlow는 한 앱 안에서 3개의 프로세스가 협업한다.

| # | Process | Runtime | Responsibility | Lifecycle |
|---|---------|---------|----------------|-----------|
| 1 | **Frontend WebView** | WKWebView (macOS), WebView2 (Windows), WebKitGTK (Linux) | UI 렌더링, 사용자 입력, 실시간 스트림 구독 | Tauri가 기동/종료 |
| 2 | **Tauri Shell** | Rust (main 프로세스) | OS 권한 프롬프트, 앱 수명주기, sidecar 프로세스 관리, IPC 라우팅, 파일 다이얼로그/트레이 | 앱 기동 시 시작, 종료 시 정리 |
| 3 | **Python Sidecar** | Python 3.11 + FastAPI + uvicorn (Tauri sidecar로 번들) | 에이전트 실행, 정책 엔진, 툴 실행, DB, LLM 어댑터 | Tauri가 자식 프로세스로 spawn, 종료 시 graceful shutdown |

**왜 3-process?**
- Frontend는 webview 샌드박스라 직접 FS/OS API 호출 불가 → Rust/Python이 필요.
- Rust는 Tauri 셸·권한 API·크로스 플랫폼 패키징에 최적. 그러나 LLM·에이전트 생태계 거의 Python.
- Python은 LangGraph·LlamaIndex·Playwright-python·pydantic 등 재사용 자산이 풍부.
- Rust와 Python 사이에 HTTP 기반 프로토콜을 둬서 언어 경계를 명확히.

### 2.3 Data Flow — Natural Language → Run

```
┌─ 1. User ────────────────────────────────────────────────┐
│ "내 Downloads의 최근 30일 PDF 파일을                      │
│  Projects 폴더의 하위로 정리하고 요약 노트를 남겨"          │
└──────────────────────┬───────────────────────────────────┘
                       │ (ChatInput — frontend)
                       ▼
┌─ 2. Frontend (features/chat) ────────────────────────────┐
│  invoke("chat_send_turn", {session_id, text})            │
└──────────────────────┬───────────────────────────────────┘
                       │ (Tauri IPC)
                       ▼
┌─ 3. Tauri Shell (commands::chat) ────────────────────────┐
│  bridge.post("/chat/turn") → sidecar                     │
└──────────────────────┬───────────────────────────────────┘
                       │ HTTP POST 127.0.0.1:<port>
                       ▼
┌─ 4. Sidecar ipc/chat ────────────────────────────────────┐
│  - ConversationTurn 저장                                  │
│  - Planner(Agent) 호출                                    │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
┌─ 5. Planner (orchestrator/planner) ──────────────────────┐
│  LLMProfile(is_planner=1) → 구조화 출력                    │
│  - 의도 파악 → AgentRole 후보 선택                          │
│  - Workflow YAML 생성 (draft)                              │
│  - Dry-run 이펙트 요약                                      │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
┌─ 6. Workflow Validation (schema/validator) ──────────────┐
│  - JSON Schema 검증                                       │
│  - 참조 무결성 (role/tool/provider 존재 여부)             │
│  - 정책 정적 검증 (툴들이 현재 Policy에서 허용 가능한가)   │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
┌─ 7. Run Creation ────────────────────────────────────────┐
│  - Workflow snapshot 저장                                 │
│  - Run(status=pending) 생성                                │
│  - Frontend 에 run_id 와 플랜 미리보기 반환               │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
┌─ 8. User Confirms "Run" ─────────────────────────────────┐
│  (자동 실행 옵션이 꺼져 있으면 사용자 클릭 대기)             │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
┌─ 9. Graph Runner (orchestrator/runner) ──────────────────┐
│  토폴로지 순서로 RunStep 생성·실행                         │
│  매 스텝: LLM call → tool call(s) → routing              │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
┌─10. Tool Execution (tools/<ns>) via ToolRuntime ─────────┐
│  ┌────── Policy Engine ───────┐                          │
│  │  allow | deny | ask | dry_run_only                    │
│  └───────┬────────────────────┘                          │
│          │                                                │
│  ┌───────▼──────────┐                                    │
│  │ ApprovalRequest  │ (ask 이면 UI 프롬프트 대기)          │
│  └───────┬──────────┘                                    │
│          │                                                │
│  ┌───────▼──────────┐                                    │
│  │ JournalEntry.before │ (reversible=true 이면)           │
│  └───────┬──────────┘                                    │
│          │                                                │
│  ┌───────▼──────────┐                                    │
│  │  실제 실행         │                                   │
│  └───────┬──────────┘                                    │
│          │                                                │
│  ┌───────▼──────────┐                                    │
│  │  AuditLog 기록    │                                   │
│  └──────────────────┘                                    │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
┌─11. Streaming Events → UI (SSE `/runs/{id}/events`) ─────┐
│  run_step.started, tool_call.*, approval.requested,      │
│  message.delta, run.succeeded …                          │
└──────────────────────────────────────────────────────────┘
```

### 2.4 Dependencies (컴포넌트 간)

| From | Depends On | Purpose |
|------|------------|---------|
| Frontend | Tauri Shell | UI ↔ 네이티브 기능 호출 |
| Tauri Shell | Python Sidecar (HTTP 127.0.0.1) | 에이전트 실행 / 상태 조회 |
| Tauri Shell | OS Permission API | 파일·접근성·자동화 권한 프롬프트 |
| Python Sidecar | SQLite (`~/.orcaflow/db.sqlite`) | 영구 저장 |
| Python Sidecar | LLM Providers | 추론 |
| Python Sidecar | Local OS / User Files | 툴 실행 (정책 검증 후) |
| Python Sidecar | OS Keychain | 시크릿 조회 (Rust 측 Tauri keychain 플러그인 경유) |

---

## 3. Data Model

> **Single Source of Truth**: [schema.md](../../01-plan/schema.md). 본 절은 Design 관점의 강조·추가 세부만 다룬다.

### 3.1 Entity Highlights

Schema 의 19개 엔티티 중 Design 단계에서 결정이 필요한 부분을 정리한다.

#### 3.1.1 Workflow YAML ↔ DB 매핑

- **YAML이 1차 표현**이다. DB의 `workflows.yaml` 컬럼에 원문을 보관하고, 나머지 정규화 테이블은 인덱싱·조회·통계 용도.
- 저장 파이프라인: YAML 파싱 → JSON Schema 검증 → Pydantic `Workflow` → DB upsert (원본 YAML + 정규화 레코드 둘 다 저장).
- 불러오기: DB에서 원본 YAML 우선 로드 → 해시 비교 → 필요 시 정규화 재생성.

#### 3.1.2 Run Snapshot

- `runs.workflow_snapshot` 은 실행 시점 YAML 원문을 저장한다.
- 실행 중 Workflow가 수정돼도 해당 Run은 스냅샷 기준으로 계속 진행.
- 재실행(replay) 시 스냅샷을 그대로 불러와 동일 LLMProfile / Policy 로 수행 (Profile/Policy 참조가 사라졌으면 실패).

#### 3.1.3 RunStep Tree

- `run_steps.parent_step_id` 로 트리 구조를 만든다. Supervisor 에이전트가 여러 하위 스텝을 생성하는 경우 트리로 표현.
- 플래너가 만든 meta-step, 사용자 승인 대기 step, 그룹 실행 step 을 동일 트리에 포함.

#### 3.1.4 AuditLog Hash Chain (v0.1 옵션)

- `hash_self = sha256(id || at || actor || action || target || status || hash_prev)`
- v0.1은 옵션으로 기록(감사만 확실하면 충분), v0.2에서 의무화 검토.
- 체인 검증 CLI 제공: `orcaflow audit verify`.

### 3.2 Pydantic Model 표현 규칙 (Python)

```python
# sidecar/orca_core/schema/workflow.py
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field

class Position(BaseModel):
    x: int
    y: int

class AgentNode(BaseModel):
    id: str
    role: str               # AgentRole.name 참조
    label: str | None = None
    position: Position
    overrides: dict = Field(default_factory=dict)

class Edge(BaseModel):
    from_: str = Field(alias="from")
    to: str
    condition: str | None = None
    label: str | None = None
    model_config = {"populate_by_name": True}

class Workflow(BaseModel):
    version: Literal[1] = 1
    name: str
    description: str | None = None
    author: str | None = None
    tags: list[str] = Field(default_factory=list)
    policy: str | None = None
    default_llm_profile: str | None = None
    nodes: list[AgentNode]
    edges: list[Edge]
    entrypoint: str
```

**규칙**:
- 필드명은 schema.md 와 정확히 일치 (snake_case).
- alias 가 필요한 경우(`from` 예약어)는 `Field(alias=...)`.
- validator 는 `model_validator(mode="after")` 로 참조 무결성 검증 (예: `entrypoint` 가 `nodes` 에 존재하는가).

### 3.3 DB Migration 전략

- v0.1: **Alembic 비사용**. 단일 `schema_v1.sql` 파일로 초기화.
- 첫 배포 후 스키마 변경이 생기면 Alembic 도입 (v0.2).
- 앱 기동 시 `PRAGMA user_version` 을 읽어 자동 마이그레이션 분기.
- SQLite 옵션:
  - `journal_mode=WAL` (동시 읽기)
  - `synchronous=NORMAL` (성능)
  - `foreign_keys=ON` (제약 강제)

---

## 4. API Specification

OrcaFlow의 API는 3층으로 구성된다:

1. **Tauri IPC Commands** — Frontend(TS) ↔ Tauri Shell(Rust)
2. **Sidecar HTTP API** — Tauri Shell(Rust) ↔ Python Sidecar
3. **SSE Event Stream** — Sidecar → Tauri Shell → Frontend (단방향 푸시)

### 4.1 Tauri IPC Commands (Rust)

모든 커맨드는 `Result<T, OrcaError>` 반환. 내부적으로는 대부분 sidecar HTTP 호출의 래퍼.

| Command | Input | Output | 설명 |
|---------|-------|--------|------|
| `app_ready` | - | `AppStatus` | 앱 초기화 상태(설정·DB·sidecar health) |
| `config_get` | - | `Config` | 현재 설정(`config.toml`) |
| `config_update` | `ConfigPatch` | `Config` | 설정 업데이트 |
| `provider_list` | - | `Provider[]` | LLM 공급자 목록 |
| `provider_add` | `ProviderCreate` | `Provider` | 공급자 추가 (API key → 키체인) |
| `provider_test` | `{id}` | `ProviderHealth` | 헬스 체크 |
| `llm_profile_list` | - | `LLMProfile[]` | 프로파일 목록 |
| `llm_profile_upsert` | `LLMProfile` | `LLMProfile` | 프로파일 생성/수정 |
| `workflow_list` | `{query?}` | `WorkflowSummary[]` | 워크플로우 목록 |
| `workflow_get` | `{id}` | `{yaml, parsed}` | 단일 조회 |
| `workflow_upsert` | `{yaml}` | `Workflow` | 생성/수정(YAML 파싱·검증) |
| `workflow_delete` | `{id}` | `{ok}` | 삭제 |
| `workflow_export` | `{id}` | `{path}` | 파일로 export (OS 다이얼로그) |
| `workflow_import` | `{path}` | `Workflow` | 파일 import |
| `chat_session_new` | - | `ChatSession` | 새 세션 |
| `chat_send_turn` | `{session_id, text}` | `ConversationTurn` | 자연어 지시 전송 (플래너 호출) |
| `run_start` | `{workflow_id, input?, dry_run?}` | `{run_id}` | 실행 시작 |
| `run_get` | `{run_id}` | `Run` | 상태 조회 |
| `run_cancel` | `{run_id}` | `{ok}` | 취소 |
| `run_list` | `{query?}` | `RunSummary[]` | 히스토리 |
| `approval_list_pending` | - | `ApprovalRequest[]` | 대기 중 승인 요청 |
| `approval_decide` | `{id, decision: "approve"\|"reject", note?}` | `{ok}` | 승인/거부 |
| `policy_list` | - | `Policy[]` | 정책 목록 |
| `policy_upsert` | `{yaml}` | `Policy` | 정책 생성/수정 |
| `policy_simulate` | `{policy_id, scenarios}` | `SimulationResult[]` | 정책 dry-run (룰 적용 결과) |
| `audit_query` | `{run_id?, from?, to?, limit?}` | `AuditLog[]` | 감사 로그 조회 |
| `journal_list` | `{run_id?}` | `JournalEntry[]` | 저널 목록 |
| `journal_restore` | `{entry_id}` | `{ok}` | 되돌리기 |
| `tool_list` | - | `Tool[]` | 등록된 툴 |
| `plugin_list` | - | `Plugin[]` | 플러그인 |
| `plugin_enable` | `{id, enabled}` | `Plugin` | 활성/비활성 |

**권한이 필요한 커맨드**는 `permission/` 모듈에서 사전 검사:
- `workflow_import/export` → 파일 다이얼로그 권한
- `provider_add` → 키체인 쓰기 권한
- 네트워크 호출이 포함되는 커맨드는 sidecar 측에서 일괄 검증

### 4.2 Sidecar HTTP API (REST)

- Base: `http://127.0.0.1:<port>` (127.0.0.1 고정, 외부 바인딩 금지)
- Auth: 기동 시 랜덤 토큰 생성 → Tauri Shell 이 보관 → 모든 요청의 `X-Orca-Token` 헤더로 검증
- 포맷: JSON snake_case, UTF-8
- 에러: `{"error": {"code": "...", "message": "...", "details": {...}}}`

**Endpoints**:

| Method | Path | 설명 |
|--------|------|------|
| GET | `/health` | 헬스 체크 |
| GET | `/version` | 버전·빌드 정보 |
| GET | `/config` | 런타임 설정 조회 |
| PATCH | `/config` | 설정 업데이트 |
| GET | `/providers` | 공급자 목록 |
| POST | `/providers` | 추가 |
| GET | `/providers/{id}/health` | 헬스 체크 |
| GET | `/llm-profiles` | 프로파일 목록 |
| PUT | `/llm-profiles/{id}` | upsert |
| GET | `/workflows` | 목록 |
| POST | `/workflows` | 생성 (YAML) |
| GET | `/workflows/{id}` | 단일 조회 |
| PUT | `/workflows/{id}` | 수정 |
| DELETE | `/workflows/{id}` | 삭제 |
| POST | `/workflows/validate` | YAML 유효성만 검증 (저장 안함) |
| POST | `/chat/sessions` | 세션 생성 |
| POST | `/chat/sessions/{id}/turns` | 자연어 입력 (플래너 호출) |
| POST | `/runs` | 실행 시작 |
| GET | `/runs/{id}` | 조회 |
| POST | `/runs/{id}/cancel` | 취소 |
| **GET** | **`/runs/{id}/events`** | **SSE 스트림 — 모든 Run 이벤트** |
| POST | `/approvals/{id}/decide` | 승인/거부 |
| GET | `/policies` | 목록 |
| PUT | `/policies/{id}` | upsert (YAML) |
| POST | `/policies/simulate` | 시뮬레이션 |
| GET | `/audit` | 감사 로그 쿼리 |
| GET | `/journal` | 저널 목록 |
| POST | `/journal/{id}/restore` | 되돌리기 |
| GET | `/tools` | 툴 레지스트리 |
| GET | `/plugins` | 플러그인 목록 |
| POST | `/plugins/{id}/enable` | 활성/비활성 |

### 4.3 Detailed Spec — 핵심 엔드포인트

#### `POST /runs`

**Request**:
```json
{
  "workflow_id": "019587a1-...",
  "input": { "prompt": "..." },
  "dry_run": false,
  "override_policy_id": null
}
```

**Response (202 Accepted)**:
```json
{
  "run_id": "019587a2-...",
  "status": "pending",
  "started_at": "2026-04-12T11:34:00Z",
  "workflow_snapshot_hash": "sha256:..."
}
```

**Errors**:
- `400` workflow 없음 / 스키마 무효
- `409` 정책 정적 검증 실패 (예: 사용 툴 중 `deny`)
- `503` sidecar 초기화 미완

#### `GET /runs/{id}/events` (SSE)

**Stream events** (각 라인은 `event: <name>` + `data: <json>`):

```
event: run.started
data: {"run_id":"...","at":"..."}

event: run_step.started
data: {"run_step_id":"...","node_id":"planner","kind":"llm_call"}

event: message.delta
data: {"run_step_id":"...","delta":"...","tokens":3}

event: tool_call.started
data: {"tool_call_id":"...","tool_id":"fs.read_file","args":{"path":"~/Desktop/..."}}

event: approval.requested
data: {"approval_id":"...","run_step_id":"...","reason":"...","diff_preview":{...}}

event: policy.denied
data: {"tool_call_id":"...","rule_id":"...","reason":"..."}

event: tool_call.succeeded
data: {"tool_call_id":"...","duration_ms":42,"result":{...}}

event: run.succeeded
data: {"run_id":"...","stats":{...}}
```

- keep-alive: 15초마다 `: ping` 주석 전송
- 재연결: SSE `Last-Event-ID` 로 누락 이벤트 재전송 지원 (sidecar 가 이벤트 리플레이 버퍼 유지, 최대 5분)

#### `POST /approvals/{id}/decide`

**Request**:
```json
{ "decision": "approve", "note": "모든 파일 정리 승인" }
```

**Response**:
```json
{ "ok": true, "state": "approved", "resumes_run": "019587a2-..." }
```

### 4.4 Error Handling

에러 코드는 도메인-카테고리-번호 형식: `<domain>.<category>.<n>`

| Code | Message | Cause | Handling |
|------|---------|-------|----------|
| `workflow.invalid.schema` | Workflow YAML이 유효하지 않습니다 | JSON Schema 위반 | 필드 하이라이트 |
| `workflow.invalid.reference` | 참조된 role/tool/provider 가 없습니다 | FK 위반 | 누락 항목 리스트 |
| `policy.denied` | 정책에 의해 차단됨 | PolicyRule effect=deny | rule 표시 |
| `policy.ask_required` | 사용자 승인 필요 | effect=ask | ApprovalRequest 생성 |
| `tool.invalid_args` | 툴 인자 스키마 위반 | JSON Schema 위반 | 재시도 |
| `tool.runtime_error` | 툴 실행 실패 | 시스템 오류 | 로그 확인 |
| `provider.unavailable` | LLM 공급자에 연결할 수 없음 | 네트워크/서비스 | 재시도/전환 |
| `run.cancelled` | 사용자가 취소함 | 취소 | - |
| `run.blocked` | 정책·승인 대기로 차단 | - | UI에서 승인 |
| `auth.invalid_token` | IPC 토큰 불일치 | 설정 꼬임 | 앱 재시작 |

---

## 5. UI/UX Design

> Phase 3 Mockup 에서 화면별 상세 목업을 별도 문서화. 본 절은 구조·상태·데이터 흐름만 정의.

### 5.1 Screen Layout (High-level)

```
┌────────────────────────────────────────────────────────────────┐
│  Title Bar (OS native)                              ⚙ 👤  _ □ ✕│
├────────────┬───────────────────────────────────────────────────┤
│            │                                                    │
│  Sidebar   │                   Main Area                        │
│            │                                                    │
│  [🏠 Home] │   (탭에 따라 다름)                                  │
│  [💬 Chat] │                                                    │
│  [🧩 Editor]                                                    │
│  [📊 Runs] │                                                    │
│  [🛡 Policy]                                                    │
│  [🔌 Prov] │                                                    │
│  [🗃 Audit]│                                                    │
│            │                                                    │
├────────────┴───────────────────────────────────────────────────┤
│  Status bar: sidecar status · active run · approval badge · …   │
└────────────────────────────────────────────────────────────────┘
```

### 5.2 Main Screens

| Screen | Feature slice | 주요 상태 | 핵심 상호작용 |
|--------|---------------|-----------|---------------|
| Home/Chat | `features/chat` | chat session, turns, active plan | 자연어 입력 → 플래너 실행 → 실행 확인 |
| Workflow Editor | `features/editor` | current workflow, dirty flag, validation errors | 노드 드래그, 역할 변경, YAML 모드 토글 |
| Run Monitor | `features/monitor` | run summaries, live events | 트리 탐색, 로그/툴콜 필터, 취소 |
| Approval Prompt | `features/approval` | pending approvals | 승인/거부, diff 프리뷰 보기 |
| Policy Manager | `features/policy` | policies, rules, simulation | 룰 추가, 시뮬레이션 |
| Providers/Profiles | `features/settings/providers` | providers, profiles | 공급자 추가, 헬스 체크 |
| Audit Viewer | `features/audit` | audit logs | 필터·검색·무결성 체크 |

### 5.3 State Management (Zustand)

**전역 store**는 `src/stores/` 에 도메인별 slice로 분리.

```ts
// src/stores/run-store.ts
type RunStore = {
  runs: Record<string, RunSummary>
  liveRunId: string | null
  events: RunEvent[]                // live tail (최대 500)
  startRun: (wfId: string, opts: RunStartOptions) => Promise<string>
  cancelRun: (id: string) => Promise<void>
  subscribe: (runId: string) => void   // SSE 구독 시작
  unsubscribe: () => void
}
```

slice 목록:
- `app-store` — sidecar 상태, 초기화, config 요약
- `chat-store` — 대화 세션과 턴
- `editor-store` — 현재 편집 중 workflow (React Flow 의 nodes/edges 와 동기)
- `run-store` — run + live event tail
- `approval-store` — pending approvals
- `policy-store` — 정책·시뮬레이션 결과
- `provider-store` — 공급자·프로파일
- `audit-store` — 감사 로그

### 5.4 Event 구독 (SSE 래퍼)

```ts
// src/lib/ipc/run-stream.ts
export function subscribeRun(runId: string, onEvent: (e: RunEvent) => void) {
  // Tauri에서는 `plugin-http` + `fetch` 를 이용한 SSE 파서를 씀.
  // Run 이벤트는 'message.delta' 등 고빈도 이벤트가 있어 프레임 드로틀링 필요.
  const ac = new AbortController()
  fetchEventStream(`/runs/${runId}/events`, { signal: ac.signal }, onEvent)
  return () => ac.abort()
}
```

컴포넌트는 `useRunStream(runId)` 훅만 사용 (직접 `fetch` 금지 — Conventions §6.4).

### 5.5 React Flow 바인딩

- `nodes/edges` 는 React Flow 내부 타입으로 보존하되, 변환 레이어(`features/editor/lib/rf-to-schema.ts`, `schema-to-rf.ts`)에서 OrcaFlow `Workflow` 스키마와 1:1 매핑.
- 노드 종류(`AgentNode`, `RouterNode`, `ApprovalNode`, `PlannerNode`)별로 `features/editor/nodes/` 하위에 배치.
- 저장 시 YAML 직렬화 → `POST /workflows/validate` → 에러 시 해당 node/edge 하이라이트.

---

## 6. Core Runtime Design

### 6.1 Orchestrator

#### 6.1.1 Graph Runner

- 기본 실행 모델: **Step-by-step 이벤트 루프**. LangGraph의 경량 래퍼 또는 우리 자체 구현 사용.
- 실행 단위는 `RunStep`. 각 스텝은 `(node_id, state_in) → (state_out, next_node_ids)` 를 계산.
- 상태(`state`)는 step 간 JSON 객체. `messages`, `artifacts`, `plan`, `scratchpad` 키를 표준화.
- 라우팅: `Edge.condition` 이 있으면 JS-expr subset(`expr-eval`) 평가, 없으면 무조건 전이.
- 병렬화: 동일 엣지에서 나가는 edge가 여러 개면 병렬 분기. join 노드는 명시적 `router` 노드로 설정.
- 취소: `asyncio.CancelledError` 전파. 실행 중 툴 호출은 `asyncio.wait_for` 로 타임아웃.

```python
# sidecar/orca_core/orchestrator/runner.py (발췌)
async def run(workflow: Workflow, run: Run, ctx: RunContext) -> None:
    await ctx.events.emit("run.started", run.id)
    queue: deque[str] = deque([workflow.entrypoint])
    state: dict = ctx.initial_state or {}

    while queue:
        node_id = queue.popleft()
        step = await ctx.persistence.create_step(run.id, node_id, parent=ctx.current_step_id)
        try:
            result = await execute_node(workflow, node_id, state, step, ctx)
            state = merge_state(state, result.state_patch)
            for next_id in route_next(workflow, node_id, state, ctx):
                queue.append(next_id)
        except PolicyViolationError as e:
            await ctx.persistence.fail_step(step.id, e)
            await ctx.events.emit("policy.denied", {"rule_id": e.rule_id})
            raise
        except asyncio.CancelledError:
            await ctx.persistence.cancel_step(step.id)
            raise

    await ctx.events.emit("run.succeeded", run.id)
```

#### 6.1.2 Planner

- 전용 `AgentRole` 하나 (`role_type=planner`, `is_planner=true` 인 LLMProfile 사용).
- 입력: 자연어 턴, 사용자 컨텍스트(열린 워크플로우/파일), 사용 가능한 역할/툴 목록, 현재 정책 요약.
- 출력: `PlannerOutput` (Pydantic 구조화 응답).
  ```python
  class PlannerOutput(BaseModel):
      intent: str
      reasoning: str
      workflow_yaml: str              # 생성된 Workflow YAML
      expected_effects: list[str]     # 요약(UI 노출용)
      confidence: Literal["low","medium","high"]
      questions: list[str]            # 사용자 확인 필요 사항
  ```
- 구현: 툴 호출(`submit_workflow(yaml)`)을 강제해 항상 YAML 문자열을 받는다. 파서 오류 시 1회 재시도(피드백 주입).
- 사용 LLM: `LLMProfile` 에서 `is_planner=true` 인 첫 번째를 기본 선택 (없으면 `is_default=true`).
- 실패 폴백: 노드 에디터로 전환 권장 + 부분 생성 결과를 YAML 초안으로 제공.

### 6.2 Tool Runtime

툴 실행은 **항상 `ToolRuntime.invoke()`** 를 경유한다. 아래 순서를 건너뛰는 경로는 존재하지 않는다.

```
ToolRuntime.invoke(tool, args, ctx):
    1. JSONSchema 검증 (input_schema)
    2. PolicyEngine.evaluate(tool, args, ctx.policy)
       → allow | deny | ask | dry_run_only
       (deny → PolicyViolationError)
       (ask  → ApprovalRequest 생성 → 이벤트 emit → 대기)
       (dry_run_only → 아래 7로 분기 후 종료)
    3. dry_run 이면 tool.dry_run(args, ctx)
       (destructive/write 타입은 기본 dry_run 먼저 실행해 diff_preview 생성)
    4. reversible 이면 Journal.record_before(tool, args, ctx)
    5. tool.run(args, ctx) 실행 (타임아웃·출력 제한 적용)
    6. AuditLog.record(ctx, tool, args, result, decision)
    7. 이벤트 emit: tool_call.{started|succeeded|failed|denied}
```

**주요 제약**:
- 모든 툴은 `ToolContext` 주입 (I/O 래퍼, ctx.journal, ctx.audit, ctx.policy, ctx.events, cancel token).
- 툴은 `ctx.io` 외의 직접 I/O 금지. 파일/프로세스/네트워크 접근은 전부 래퍼 경유.
- 시간 제한: 기본 30초, Tool 메타에서 override 가능.
- 출력 크기 제한: 기본 1MB, 초과 시 storage 파일로 스필 + 요약만 메모리.

### 6.3 Policy Engine

#### 6.3.1 평가 알고리즘

```
evaluate(tool, args, policy):
    # 1. 컨텍스트 정규화
    path   = normalize_path(args)             # fs_path scope 용
    cmd    = extract_command(args)            # shell_command scope 용
    hosts  = extract_hosts(args)              # network_host scope 용

    # 2. 적용 가능한 룰 필터링 (scope/tool_id 매칭)
    candidates = [r for r in policy.rules if matches(r, tool, path, cmd, hosts)]

    # 3. 우선순위 오름차순 정렬 후 첫 매칭 룰 선택
    for r in sorted(candidates, key=lambda r: r.priority):
        return decide(r.effect, r)

    # 4. 기본값
    return default_effect(policy.mode)   # strict=deny, ask=ask, trusted=allow
```

- `scope` 는 `fs_path | shell_command | network_host | os_api | tool_id` 중 하나.
- `matcher` 는 scope 별 의미:
  - `fs_path`: glob (`~/**`, `**/.ssh/**`) — `pathspec` 사용
  - `shell_command`: 정규식 (앵커 `^$` 권장)
  - `network_host`: 호스트 패턴 (`*.example.com`)
  - `os_api`: 자유 문자열 (AppleScript/PowerShell 액션 이름)
  - `tool_id`: 정확 일치 또는 접두(`fs.*`)
- `effect`:
  - `allow` — 그대로 실행
  - `deny` — `PolicyViolationError`
  - `ask` — `ApprovalRequest` 생성
  - `dry_run_only` — 실제 실행 금지, dry_run 결과만 반환

#### 6.3.2 정책 정적 검증 (Run 시작 전)

Run 시작 시 Workflow에 등장하는 모든 Tool ID 집합과 현재 Policy를 대조해 "이 워크플로우는 어떤 승인이 필요해 보인다"를 사전 계산한다. UI는 이것을 **Plan preview** 로 노출.

#### 6.3.3 정책 시뮬레이션 (UI 시뮬레이터)

`POST /policies/simulate` 는 임의의 시나리오 리스트를 받아 효과를 미리 계산한다.

```json
{
  "policy_id": "default",
  "scenarios": [
    { "tool_id": "fs.delete", "args": { "path": "~/Documents/old.txt" } },
    { "tool_id": "shell.exec", "args": { "cmd": "rm -rf /" } }
  ]
}
```

응답은 각 시나리오에 대해 `effect`, 매칭 룰 ID, 이유.

### 6.4 Journal (Undo System)

- `JournalEntry` 는 SQLite 메타 + 대용량 페이로드 파일 하이브리드:
  - 메타: `journal_entries` 테이블
  - `storage_ref` 경로: `~/.orcaflow/journal/<run-id>/<entry-id>.{json,bin}`
  - 파일 콘텐츠는 원본을 그대로 저장(작으면 json, 크면 gzip bin)
- **복구 가능성 판정**: 엔트리 생성 시 `reversible` 필드 확정. 파일이 다른 프로세스에서 수정되면 복구 시도에서 충돌 감지 후 실패(체크섬 비교).
- **GC**: 14일 후 또는 최대 500MB 초과 시 오래된 엔트리 삭제 (설정 가능).
- **취소 순서**: 동일 run 내에서는 역순 복구. cross-run 복구는 단건 기반.

### 6.5 Audit Log

- 메타는 `audit_logs` 테이블 + 파일 미러(`~/.orcaflow/logs/audit.log` JSONL).
- 애플리케이션 레이어(`orca_core/audit/sink.py`)가 유일한 쓰기 경로. **DB 쓰기 + 파일 append** 가 원자적 실패하면 Run이 blocked.
- 쓰기 실패 시 정책: `fail_run` (기본) / `fail_step` / `degraded`(파일만) — config 로 선택.
- 무결성: 옵션으로 해시 체인, `orca_core/audit/verify.py` 가 CLI 제공.

### 6.6 Provider Adapters

- 공통 인터페이스 `ProviderAdapter`:
  ```python
  class ProviderAdapter(Protocol):
      kind: ProviderKind
      async def chat(self, req: ChatRequest) -> ChatResponse: ...
      async def stream_chat(self, req: ChatRequest) -> AsyncIterator[ChatChunk]: ...
      async def health(self) -> ProviderHealth: ...
  ```
- **기본 어댑터**: `OpenAICompatibleAdapter` — 대다수 공급자(Ollama, vLLM, llama.cpp, LM Studio, Together, Groq, Fireworks, TGI)가 이 어댑터 하나로 커버.
- **네이티브 예외**: Ollama의 고유 엔드포인트(`/api/tags`, 헬스), 일부 파라미터는 Ollama 서브클래스가 override.
- **Tool calling**: 공급자 지원 여부(`is_tool_capable`)에 따라:
  - 지원 → OpenAI tool-call 포맷 사용
  - 미지원 → 구조화 JSON 출력 프롬프트 + 파서 폴백 (플래너에도 동일 규칙)
- **시크릿 조회**: 어댑터는 `ProviderSecretStore.get(api_key_ref)` 만 사용. 직접 `os.environ` 읽기 금지.

### 6.7 Tauri ↔ Sidecar Bridge

- **기동 순서**:
  1. Tauri 메인 프로세스 시작
  2. 포트 0으로 sidecar spawn (OS가 포트 할당 → stdout로 `{"port": 54321, "token": "..."}` JSON 라인 리턴)
  3. Tauri가 토큰을 메모리에 저장(`AppState`), `Client` 생성
  4. `/health` 확인 후 Frontend에 `app_ready` 이벤트
- **프로세스 감시**: sidecar 크래시 감지 시 1회 자동 재시작(rate-limited). 재시작 중 UI는 `sidecar.unavailable` 상태.
- **종료**: Tauri 셧다운 시 `/shutdown` 호출 → 5초 grace → SIGTERM → SIGKILL.
- **로그 수집**: sidecar stdout/stderr 는 Rust 쪽에서 capture → 구조화 JSON 파싱 → `~/.orcaflow/logs/sidecar.log` 로 기록.

---

## 7. Security Considerations

- [x] **입력 검증**: 모든 API 입력은 Pydantic + JSON Schema 로 검증. path traversal/injection 방지.
- [x] **네트워크**: sidecar `127.0.0.1` 고정. 로컬 방화벽에서 차단돼도 동작.
- [x] **IPC 인증**: 기동 시 랜덤 토큰, 프로세스 간 전달 후 모든 요청에 헤더 필수.
- [x] **시크릿 저장**: OS 키체인(Keychain/Credential Manager/libsecret). DB/설정에 평문 금지.
- [x] **경로 정규화**: `Path.expanduser().resolve()` + 심볼릭 링크 기본 차단 + 시스템 디렉토리 기본 거부.
- [x] **쉘 실행**: `subprocess.run(shell=False)` + `shlex.split`. 타임아웃·출력 제한 필수. 기본 `mode=ask`.
- [x] **사용자 승인**: 모든 `destructive` 툴은 기본 `ask`. 사용자가 명시적으로 `trusted` 로 승격한 경우에만 자동 실행.
- [x] **감사 불변성**: AuditLog UPDATE/DELETE 경로 없음, 파일 미러 append-only.
- [x] **되돌리기**: reversible 작업은 journal 기록 후 실행. 체크섬 검증.
- [x] **플러그인 권한**: plugin.yaml 의 permissions 합집합을 설치 시 사용자 승인. 서명 검증은 v0.2에서 강화.
- [x] **네트워크 정책**: outbound HTTP는 `web.http_request` 툴 경유. 호스트 기반 화이트/블랙리스트.
- [x] **클립보드/키보드/마우스**: 기본 `ask`. 화면 캡처·키로거 용도로 악용되지 않도록 `os.*` 툴은 제한 목록.
- [x] **로그에서 시크릿 스크럽**: Pydantic `SecretStr`, 구조화 로거에서 `scrub_secrets()` 필터 고정.

---

## 8. Test Plan

### 8.1 Test Scope

| Type | Target | Tool |
|------|--------|------|
| Unit (Domain) | schema, policy, audit, journal | pytest (cover ≥ 80%) |
| Unit (Orchestrator) | runner, planner, tool-runtime | pytest + FakeProvider + FakeTool |
| Unit (Tools) | fs/shell/browser/os/web 각각 | pytest + tmp_path/tmp 파일시스템 |
| Integration | sidecar HTTP API | pytest + httpx.AsyncClient |
| Integration (Rust) | commands + bridge | `cargo test` |
| Frontend Unit | stores, hooks, components | vitest + @testing-library/react |
| E2E | 데스크톱 앱 시나리오 | Playwright (Tauri webview) |

### 8.2 Test Cases (Key)

**Domain**
- [ ] PolicyEngine: priority 순서, scope 매칭, 기본값(strict/ask/trusted) 동작
- [ ] PolicyRule matcher: glob/regex/host 케이스
- [ ] AuditLog: hash chain (옵션 활성 시) 무결성
- [ ] JournalEntry: before 기록 실패 시 실행 차단

**Orchestrator**
- [ ] Runner: 선형 워크플로우 성공/실패/취소
- [ ] Runner: 병렬 분기 + join
- [ ] Runner: 정책 위반 시 step 차단, run 상태 전이
- [ ] Planner: 자연어 → 유효 YAML (구조화 출력 강제)
- [ ] Planner: 파서 실패 → 1회 재시도 후 실패 폴백

**Tools**
- [ ] fs.delete: 휴지통 경유 + journal 기록 + 복구
- [ ] shell.exec: 타임아웃, 출력 제한, 정책 매칭
- [ ] browser.navigate: Playwright fake / headless
- [ ] os.applescript / powershell: mocked subprocess

**Integration**
- [ ] `POST /runs` → SSE 이벤트 시퀀스 검증
- [ ] `POST /approvals/{id}/decide` → Run 재개
- [ ] `POST /policies/simulate` → 결정 테이블 일치

**Frontend**
- [ ] run-store SSE 구독/해제
- [ ] features/editor YAML ↔ ReactFlow 왕복 변환
- [ ] approval dialog 표시/승인 플로우

**E2E**
- [ ] "Downloads PDF 정리" 시나리오 전체
- [ ] 코드베이스 읽고 요약 저장
- [ ] 브라우저 탐색 + 요약 노트

---

## 9. Clean Architecture

### 9.1 Layer Structure (OrcaFlow)

| Layer | Responsibility | Location |
|-------|----------------|----------|
| **Presentation** | UI 컴포넌트, 훅, 스토어, 이벤트 구독 | `frontend/src/components`, `frontend/src/features`, `frontend/src/stores`, `frontend/src/hooks` |
| **App Shell** | OS 권한, Tauri IPC commands, sidecar bridge | `app/src-tauri/src/commands`, `src/bridge`, `src/permission` |
| **Application** | 유스케이스, 실행 엔진, 플래너, API 라우팅 | `sidecar/orca_core/ipc`, `sidecar/orca_core/orchestrator` |
| **Domain** | 엔티티, 정책, 감사, 저널 (순수) | `sidecar/orca_core/schema`, `policy`, `audit`, `journal` |
| **Infrastructure** | LLM 공급자, 툴 구현, 퍼시스턴스, OS 인터페이스 | `sidecar/orca_core/providers`, `tools`, `persistence`, `ipc/http` |

### 9.2 Dependency Direction

```
Presentation ─▶ App Shell ─▶ Application ─▶ Domain ◀─ Infrastructure
                                      └─▶ Infrastructure
```

- Domain은 외부 아무것도 import 하지 않는다 (Conventions §6.3).
- Application은 Domain 타입과 Infrastructure 프로토콜을 조립만 한다 (의존성 역전).
- Infrastructure는 Domain 이외 상위 레이어에 의존하지 않는다.
- Presentation은 App Shell(Tauri IPC)만 호출하고 Python/Infra 에 직접 닿지 않는다.

### 9.3 Import Rules Summary

| From | Can Import | Cannot Import |
|------|------------|---------------|
| Presentation | App Shell (via lib/api), Types | Python sidecar 직접, Infrastructure 구현 |
| App Shell | sidecar HTTP (via bridge), Permission API | Infrastructure 내부 구현 |
| Application | Domain, Infrastructure Protocol | Presentation |
| Domain | std / pydantic 만 | 다른 모든 레이어, DB, HTTP, 파일 I/O |
| Infrastructure | Domain | Application, Presentation |

### 9.4 OrcaFlow Component Layer Assignment

| Component | Layer | Location |
|-----------|-------|----------|
| `ChatPanel`, `NodeEditor`, `RunMonitor`, `ApprovalDialog` | Presentation | `frontend/src/features/*` |
| `use-run-stream`, `useRunStore`, `lib/api/run.ts` | Presentation (hooks/store/adapter) | `frontend/src/stores`, `frontend/src/lib/api` |
| `run_start`, `approval_decide` (Tauri commands) | App Shell | `app/src-tauri/src/commands/run.rs` |
| `SidecarBridge` | App Shell | `app/src-tauri/src/bridge/sidecar.rs` |
| `GraphRunner`, `Planner`, `ToolRuntime` | Application | `sidecar/orca_core/orchestrator/*` |
| `Workflow`, `PolicyRule`, `AuditLog`, `JournalEntry` | Domain | `sidecar/orca_core/schema/*`, `policy/*`, `audit/*`, `journal/*` |
| `OllamaProvider`, `FsReadFile`, `ShellExec`, `SqliteRepo` | Infrastructure | `sidecar/orca_core/providers/*`, `tools/*`, `persistence/*` |

---

## 10. Coding Convention Reference

> Source of truth: [conventions.md](../../01-plan/conventions.md). 본 절은 OrcaFlow 특수 적용만 정리.

### 10.1 Naming (발췌)

| Target | Rule | Example |
|--------|------|---------|
| Tool ID | `<namespace>.<verb>_<noun>` | `fs.read_file`, `browser.navigate` |
| Event code | `<domain>.<action>[.<result>]` | `tool_call.started`, `run.succeeded` |
| AgentRole name | kebab-case | `file-organizer` |
| LLMProfile name | `<provider>-<model>[-<variant>]` | `ollama-qwen2.5-14b` |
| Policy name | kebab-case | `default`, `coding-assistant` |
| Tauri IPC event | `orca:<domain>:<event>` | `orca:run:step_started` |

### 10.2 Import Order

- TypeScript / Python / Rust 모두 conventions §3.5 참조 규칙을 그대로 적용.

### 10.3 Config & Secrets

- OrcaFlow는 `.env` 대신 `~/.orcaflow/config.toml` + OS 키체인. `.env.example` 은 개발/CI 전용.

### 10.4 This Feature's Conventions

| Item | Convention Applied |
|------|-------------------|
| 네이밍 | 언어 관용 + schema.md 엔티티 고정 |
| 상태 관리 | Zustand 도메인 슬라이스, SSE 구독은 `features/<slice>/hooks` 에서만 |
| 에러 처리 | 도메인 예외 타입 (PolicyViolation, ProviderUnavailable, ToolRuntimeError…) + HTTP 에러 매핑 |
| 로그 | JSONL + `component/event/run_id/actor` 필수 |
| 시크릿 | `SecretStr` + `scrub_secrets()` 필터 |

---

## 11. Implementation Guide

### 11.1 File Structure (target for v0.1)

```
OrcaFlow/
├── app/src-tauri/
│   ├── src/
│   │   ├── main.rs
│   │   ├── commands/
│   │   │   ├── run.rs
│   │   │   ├── workflow.rs
│   │   │   ├── approval.rs
│   │   │   ├── policy.rs
│   │   │   ├── provider.rs
│   │   │   ├── config.rs
│   │   │   └── mod.rs
│   │   ├── bridge/
│   │   │   ├── sidecar.rs      # 프로세스 기동/헬스/재시작
│   │   │   ├── client.rs       # HTTP client + token
│   │   │   ├── sse.rs          # SSE 파이프
│   │   │   └── mod.rs
│   │   ├── permission/
│   │   │   ├── tcc.rs          # macOS
│   │   │   ├── win.rs          # Windows
│   │   │   └── mod.rs
│   │   ├── config/
│   │   │   └── mod.rs
│   │   └── errors.rs
│   ├── Cargo.toml
│   └── tauri.conf.json
├── frontend/
│   └── src/
│       ├── components/ui/
│       ├── features/
│       │   ├── chat/{components,hooks,api.ts,store.ts,index.ts}
│       │   ├── editor/
│       │   │   ├── components/
│       │   │   ├── nodes/{agent-node,router-node,approval-node,planner-node,registry.ts}
│       │   │   ├── lib/{rf-to-schema.ts, schema-to-rf.ts}
│       │   │   ├── store.ts
│       │   │   └── index.ts
│       │   ├── monitor/
│       │   ├── approval/
│       │   ├── policy/
│       │   ├── settings/providers/
│       │   └── audit/
│       ├── stores/{app-store, chat-store, run-store, approval-store, policy-store, provider-store, audit-store}.ts
│       ├── hooks/
│       ├── lib/
│       │   ├── api/{workflow, run, approval, policy, provider, audit, config}.ts
│       │   ├── ipc/{run-stream, events}.ts
│       │   └── utils/
│       ├── types/{workflow, run, policy, approval, provider, audit}.types.ts
│       └── styles/
├── sidecar/
│   └── orca_core/
│       ├── app.py
│       ├── config.py
│       ├── errors.py
│       ├── schema/
│       │   ├── workflow.py
│       │   ├── agent.py
│       │   ├── tool.py
│       │   ├── llm.py
│       │   ├── policy.py
│       │   ├── run.py
│       │   ├── audit.py
│       │   └── journal.py
│       ├── policy/
│       │   ├── engine.py
│       │   ├── matcher.py
│       │   └── simulator.py
│       ├── audit/
│       │   ├── sink.py
│       │   └── verify.py
│       ├── journal/
│       │   ├── store.py
│       │   └── restore.py
│       ├── persistence/
│       │   ├── db.py
│       │   ├── migrations.py
│       │   └── repo/
│       ├── providers/
│       │   ├── _base.py
│       │   ├── openai_compatible.py
│       │   ├── ollama.py
│       │   ├── vllm.py
│       │   ├── together.py
│       │   ├── groq.py
│       │   └── secret_store.py
│       ├── tools/
│       │   ├── _base.py
│       │   ├── registry.py
│       │   ├── runtime.py
│       │   ├── fs/{read_file,write_file,move,delete,list}.py
│       │   ├── shell/exec.py
│       │   ├── browser/{open,navigate,scrape,click}.py
│       │   ├── os/{notify,clipboard,applescript,powershell}.py
│       │   └── web/{http_request,search}.py
│       ├── orchestrator/
│       │   ├── runner.py
│       │   ├── planner.py
│       │   ├── context.py
│       │   └── state.py
│       └── ipc/
│           ├── http/
│           │   ├── app.py
│           │   ├── routes/{runs,workflows,approvals,policies,providers,config,audit}.py
│           │   └── sse.py
│           └── auth.py
├── shared/
│   ├── schemas/{workflow.schema.json, tool-manifest.schema.json}
│   └── ipc/{events.yaml}
└── scripts/
    ├── dev.sh
    ├── bundle-sidecar.sh
    └── release.sh
```

### 11.2 Implementation Order (v0.1 → MVP)

**Milestone M1 — 뼈대 & 브릿지 (Week 1)**
1. [ ] Tauri 프로젝트 스캐폴딩 (`app/src-tauri`)
2. [ ] Vite React 프로젝트 스캐폴딩 (`frontend`)
3. [ ] Python sidecar 기본 FastAPI 앱 + `/health`, `/version`
4. [ ] Tauri ↔ sidecar 기동 프로토콜(토큰·포트)
5. [ ] 기본 Tauri command: `app_ready`, `config_get`

**Milestone M2 — 도메인 & 퍼시스턴스 (Week 1-2)**
6. [ ] `orca_core/schema/*` Pydantic 모델 전체
7. [ ] `persistence/db.py` SQLite 초기화 + v1 스키마
8. [ ] `policy/engine.py` + 단위 테스트
9. [ ] `audit/sink.py` + 파일 미러
10. [ ] `journal/store.py` + 복구

**Milestone M3 — 공급자 & 툴 최소 (Week 2)**
11. [ ] `providers/openai_compatible.py` + `ollama.py`
12. [ ] `tools/fs/{read_file, write_file, list}`
13. [ ] `tools/runtime.py` (Policy → Journal → Audit 흐름)
14. [ ] FakeProviderAdapter, FakeTool

**Milestone M4 — 오케스트레이터 + 플래너 (Week 3)**
15. [ ] `orchestrator/runner.py` 선형 워크플로우 지원
16. [ ] `orchestrator/planner.py` 구조화 출력
17. [ ] `ipc/http/routes/runs.py` + SSE 이벤트
18. [ ] Run 히스토리 조회

**Milestone M5 — UI 핵심 (Week 3-4)**
19. [ ] Chat 화면 + ConversationTurn 전송
20. [ ] Run Monitor + SSE 구독
21. [ ] Approval Dialog
22. [ ] 기본 Workflow YAML 뷰 (노드 에디터는 M6)

**Milestone M6 — 노드 에디터 & 정책 UI (Week 4-5)**
23. [ ] React Flow 편집 + schema 변환
24. [ ] Policy Manager + Simulator
25. [ ] Provider/LLMProfile 설정 화면

**Milestone M7 — 고급 툴 & 시나리오 (Week 5-6)**
26. [ ] `tools/shell/exec` + `browser/playwright`
27. [ ] `tools/os/{applescript, powershell}` (플랫폼별)
28. [ ] 3종 데모 시나리오 (Plan DoD 항목) E2E 통과

**Milestone M8 — 번들/배포 (Week 6)**
29. [ ] Tauri sidecar 번들링 (PyInstaller or equivalent)
30. [ ] macOS dmg / Windows msi 빌드 스크립트
31. [ ] README / 사용자 가이드 / 샘플 플로우

### 11.3 Key Technical Risks & Spikes

| Risk | Spike | 기한 |
|------|-------|------|
| Python sidecar를 Tauri로 번들링 (PyInstaller onefile vs onedir vs native) | `spike/bundle-sidecar` | M1 |
| SSE over Tauri webview의 안정성 / 프레임 throttling | `spike/sse-stability` | M4 |
| LangGraph vs 자체 얇은 러너 복잡도 | `spike/runner-decision` | M4 |
| Playwright 설치/실행(사용자 PC에 브라우저 내려받기) UX | `spike/playwright-bootstrap` | M7 |
| macOS permission (접근성·자동화) 승인 UX | `spike/macos-tcc` | M2 |

---

## 12. Validation Checklist (Design Review)

- [ ] Plan §1.1.1 (native-first, no container) 원칙이 아키텍처·번들링·테스트에 반영됐는가
- [ ] schema.md 엔티티와 본 문서 §3의 Pydantic 모델 필드가 정확히 일치
- [ ] conventions.md 의 의존 방향·경계 규칙이 설계의 레이어 매핑과 일치
- [ ] 모든 파괴적 툴 호출이 §6.2 ToolRuntime 흐름을 경유
- [ ] 모든 API 응답이 §4.4 에러 코드 체계를 따름
- [ ] SSE 재연결(Last-Event-ID)·토큰 인증·127.0.0.1 바인딩 명시
- [ ] 시크릿은 OS 키체인만 사용 (`api_key_ref` 만 DB)
- [ ] Journal·Audit 실패 시 Run 차단 정책 명시
- [ ] 플래너의 구조화 출력 강제 + 실패 폴백 경로 정의
- [ ] 3종 MVP 데모 시나리오가 M1~M8 구현 순서에서 가능
- [ ] Phase 3 Mockup 에서 다루어야 할 화면 항목 식별

---

## 13. Next Steps

1. Design 문서 리뷰·승인
2. `/phase-3-mockup` — 화면별 상세 목업 (Chat / Editor / Monitor / Approval / Policy)
3. `/phase-4-api` — API 스펙 상세 + JSON Schema 확정
4. `/pdca do OrcaFlow` — 구현 착수 (M1 뼈대부터)
5. 병행: 3개 Spike 실행 (`bundle-sidecar`, `sse-stability`, `runner-decision`)

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-04-12 | Initial draft — 3-process 아키텍처, IPC/HTTP/SSE 프로토콜, 정책 엔진 런타임, 플래너 파이프라인, 레이어 매핑, v0.1 MVP 8 마일스톤 | 2z |
