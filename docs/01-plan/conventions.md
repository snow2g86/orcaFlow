# OrcaFlow Coding Conventions

> Phase 2 Deliverable — 코드 작성 규칙 정의
>
> **Project**: OrcaFlow
> **Date**: 2026-04-12
> **Version**: 1.0
> **Level**: Dynamic (Tauri 데스크톱 앱 + Python FastAPI sidecar + SQLite)

OrcaFlow는 **Rust(Tauri 셸) + Python(FastAPI sidecar) + TypeScript(Vite+React 프론트엔드)** 로 구성된 폴리글랏 프로젝트다. 본 문서는 세 언어의 일관된 코드 작성 규칙과, 전반적으로 지켜야 할 로깅·감사·보안·재사용 원칙을 정의한다.

관련 문서:
- 용어·엔티티: [glossary.md](./glossary.md), [schema.md](./schema.md)
- 프로젝트 원칙: [OrcaFlow.plan.md](./features/OrcaFlow.plan.md) (특히 "1.1.1 Core Principle: Native-First, No Sandbox Isolation")

---

## 1. Naming Conventions

### 1.1 Files / Folders

| Target | Rule | Example |
|--------|------|---------|
| Rust 모듈 파일 | snake_case | `policy_engine.rs` |
| Rust 폴더 | snake_case | `src-tauri/src/bridge/` |
| Python 모듈 파일 | snake_case | `tool_runner.py` |
| Python 패키지 폴더 | snake_case | `orca_core/tools/browser/` |
| TypeScript 컴포넌트 파일 | PascalCase | `NodeEditor.tsx` |
| TypeScript 훅/유틸/스토어 파일 | kebab-case | `use-run-stream.ts`, `policy-utils.ts`, `run-store.ts` |
| TypeScript 타입 파일 | kebab-case with `.types.ts` | `workflow.types.ts` |
| 상수 파일 | kebab-case with `.constants.ts` | `tool-namespaces.constants.ts` |
| YAML 스키마 파일 | kebab-case `.yaml` | `workflow.schema.yaml` |
| 문서 | kebab-case `.md` | `conventions.md` |

> **원칙**: 언어 커뮤니티 관용을 우선한다. Rust·Python은 snake_case, TypeScript 컴포넌트는 PascalCase.

### 1.2 Code Identifiers

공통 원칙: **schema.md의 엔티티명과 필드명은 SSoT**. 언어별 관용 케이스로 변환하되 어원은 그대로 유지한다.

| Target | Rust | Python | TypeScript |
|--------|------|--------|------------|
| 엔티티/타입 | `Workflow`, `AgentRole` (PascalCase) | `Workflow`, `AgentRole` (PascalCase, pydantic BaseModel) | `Workflow`, `AgentRole` (PascalCase interface/type) |
| 함수 | `run_step` (snake_case) | `run_step` (snake_case) | `runStep` (camelCase) |
| 상수 | `MAX_STEPS` (SCREAMING_SNAKE) | `MAX_STEPS` (SCREAMING_SNAKE) | `MAX_STEPS` (SCREAMING_SNAKE) |
| 변수 | `workflow_id` (snake_case) | `workflow_id` (snake_case) | `workflowId` (camelCase) |
| Enum 멤버 | `Status::AwaitingApproval` | `Status.AWAITING_APPROVAL` | `"awaiting_approval"` (문자열 리터럴 유니온 선호) |
| 컴포넌트 | — | — | `<NodeEditor />` (PascalCase) |
| React 훅 | — | — | `useRunStream` (camelCase, `use` 접두) |
| Zustand store | — | — | `useRunStore` (camelCase, `use` 접두) |

### 1.3 Cross-Language Field Naming

외부 경계(YAML 워크플로우, REST/IPC JSON, DB 컬럼)는 **snake_case**로 고정한다. 프론트엔드에서는 경계에서 camelCase로 1회 변환한다.

| Boundary | Case | Example |
|----------|------|---------|
| YAML (사용자 편집) | snake_case | `agent_nodes`, `llm_profile` |
| SQLite 컬럼 | snake_case | `run_step_id` |
| REST JSON / Tauri IPC 페이로드 | snake_case | `{"policy_decision": "allow"}` |
| TypeScript 내부 모델 | camelCase | `policyDecision` |

**변환 지점**: 프론트엔드 `src/lib/api/` 어댑터 레이어에서만 변환한다. 컴포넌트/스토어는 camelCase만 본다.

### 1.4 OrcaFlow-Specific Name Rules

| Pattern | Rule | Example |
|---------|------|---------|
| Tool ID | `<namespace>.<verb>_<noun>` | `fs.read_file`, `browser.navigate`, `os.applescript` |
| Tool namespace | 고정 enum: `fs`, `shell`, `browser`, `os`, `web`, `custom` | - |
| AgentRole 이름 | kebab-case | `file-organizer`, `code-reviewer` |
| LLM Profile 이름 | `<provider>-<model>[-<variant>]` (kebab-case) | `ollama-qwen2.5-14b`, `groq-llama3.1-70b` |
| Policy 이름 | kebab-case, 용도 명시 | `default`, `strict`, `coding-assistant` |
| Run ID / UUID | UUID v7 문자열 | `019587a1-...` |
| 이벤트 이름 (Tauri IPC) | `orca:<domain>:<event>` | `orca:run:step_started`, `orca:policy:approval_required` |
| 로그 이벤트 코드 | `<domain>.<action>[.<result>]` (snake_case) | `tool_call.started`, `policy.denied`, `run.succeeded` |

---

## 2. Folder Structure

상세 구조는 [OrcaFlow.plan.md §6.3](./features/OrcaFlow.plan.md) 참조. 본 절은 폴더별 책임과 의존 방향을 고정한다.

```
OrcaFlow/
├── app/                         # Tauri 셸 (Rust)
│   └── src-tauri/
│       ├── src/
│       │   ├── main.rs
│       │   ├── commands/        # Tauri command (IPC 진입점)
│       │   ├── bridge/          # Python sidecar 통신
│       │   ├── permission/      # Tauri permission API 래퍼
│       │   └── config/          # 앱 설정 로딩
│       ├── Cargo.toml
│       └── tauri.conf.json
├── frontend/                    # Vite + React
│   ├── src/
│   │   ├── components/          # 재사용 UI (shadcn/ui 기반)
│   │   │   └── ui/
│   │   ├── features/            # 기능 모듈 (수직 slice)
│   │   │   ├── chat/
│   │   │   ├── editor/          # React Flow 노드 에디터
│   │   │   ├── monitor/         # Run / RunStep 모니터링
│   │   │   ├── settings/        # Provider/LLMProfile/Policy 관리
│   │   │   └── approval/        # Approval Request 프롬프트
│   │   ├── stores/              # Zustand 전역 상태
│   │   ├── hooks/               # 공용 훅
│   │   ├── lib/
│   │   │   ├── api/             # Tauri IPC 클라이언트 + case 변환
│   │   │   ├── ipc/             # 이벤트 구독
│   │   │   └── utils/
│   │   ├── types/               # 공유 타입 (schema.md 와 동기)
│   │   └── styles/
│   ├── index.html
│   ├── vite.config.ts
│   └── package.json
├── sidecar/                     # Python FastAPI
│   ├── orca_core/
│   │   ├── __init__.py
│   │   ├── app.py               # FastAPI entrypoint
│   │   ├── schema/              # Pydantic 모델 (schema.md 매핑)
│   │   ├── orchestrator/        # 실행 엔진, 플래너, 그래프 런너
│   │   ├── providers/           # LLM 어댑터 (ollama, vllm, together...)
│   │   ├── tools/
│   │   │   ├── fs/
│   │   │   ├── shell/
│   │   │   ├── browser/
│   │   │   ├── os/
│   │   │   ├── web/
│   │   │   └── registry.py      # Tool 레지스트리
│   │   ├── policy/              # 정책 엔진
│   │   ├── journal/             # 변경 저널
│   │   ├── audit/               # 감사 로그
│   │   ├── persistence/         # SQLite 레이어
│   │   ├── ipc/                 # Tauri↔sidecar 프로토콜
│   │   └── config.py
│   ├── tests/
│   └── pyproject.toml
├── shared/                      # 언어 간 공유 정의
│   ├── schemas/                 # JSON Schema (YAML 워크플로우, Tool manifest)
│   ├── ipc/                     # IPC 메시지 프로토콜 정의
│   └── fixtures/                # 샘플 워크플로우/정책
├── docs/
│   ├── 01-plan/
│   ├── 02-design/
│   ├── 03-analysis/
│   └── 04-report/
├── scripts/                     # 빌드/개발/배포 스크립트
├── .bkit-memory/                # 프로젝트 내부 메모리 (PDCA feedback)
├── CONVENTIONS.md               # 루트 요약 (본 문서 링크)
├── CLAUDE.md                    # AI 협업 가이드 (glossary/conventions 참조)
└── README.md
```

### 2.1 Feature-Slice 규칙 (frontend/src/features/)

한 feature 폴더는 독립적으로 이동·삭제 가능해야 한다.

```
features/editor/
├── components/         # 이 feature 전용 컴포넌트
├── hooks/              # 이 feature 전용 훅
├── store.ts            # Zustand slice (전역 store에서 import)
├── types.ts            # feature 전용 타입
├── api.ts              # 이 feature의 Tauri IPC 호출
└── index.ts            # public API export (배럴)
```

**외부에서는 `features/editor` 폴더 내부 파일을 직접 import 금지**. 반드시 `import { NodeEditor } from '@/features/editor'` 형태로 배럴만 사용한다.

### 2.2 Python 패키지 규칙 (sidecar/orca_core/)

- 각 하위 패키지는 `__init__.py`에서 공개 API를 명시 export.
- `schema/`는 외부 의존을 가지지 않는 순수 모델 계층(= Domain). DB·IO 코드 금지.
- `tools/<namespace>/`는 동일 인터페이스(`Tool` protocol)를 구현한다.
- 상위 레이어는 하위 레이어만 import 가능 (§6 의존 규칙 참조).

---

## 3. Code Style

### 3.1 포맷터·린터 (필수 설치)

| Language | Formatter | Linter | Type Check |
|----------|-----------|--------|------------|
| Rust | `rustfmt` (기본) | `clippy` (denies warnings) | `cargo check` |
| Python | `ruff format` (≈ black) | `ruff check` | `mypy` (strict on `orca_core/schema/`, `orca_core/policy/`, `orca_core/audit/`) |
| TypeScript | `prettier` | `eslint` | `tsc --noEmit` |

### 3.2 Rust (Tauri 셸)

- 인덴트: 4 spaces (rustfmt 기본)
- Edition: 2021 이상
- `unsafe` 블록은 주석으로 안전 근거 필수
- 에러 타입: `thiserror` + `anyhow` (경계에서만 `anyhow::Result`)
- Tauri command는 `Result<T, OrcaError>` 반환, `OrcaError`는 JSON 직렬화 가능

```rust
// 좋은 예: Tauri command
#[tauri::command]
pub async fn run_workflow(
    workflow_id: String,
    state: tauri::State<'_, AppState>,
) -> Result<RunId, OrcaError> {
    state.bridge.start_run(workflow_id).await
}
```

### 3.3 Python (FastAPI sidecar)

- 인덴트: 4 spaces
- 타입 힌트 **필수** (`from __future__ import annotations`)
- Pydantic v2 모델 사용, `schema/` 계층에서만 정의
- 예외: 도메인별 예외 클래스 (`PolicyViolationError`, `ToolExecutionError`, `ProviderTimeoutError` 등), `orca_core/errors.py`에 정의
- async/await 기본. 동기 I/O는 `anyio.to_thread.run_sync`로 감싼다.
- Pydantic 모델 필드명은 **schema.md와 정확히 일치** (snake_case 유지)

```python
# 좋은 예
from __future__ import annotations
from pydantic import BaseModel, Field

class ToolCall(BaseModel):
    id: str
    run_step_id: str
    tool_id: str
    args: dict
    dry_run: bool = False
    policy_decision: Literal["allow", "denied", "approved", "dry_run_only"]
```

### 3.4 TypeScript (frontend)

- 인덴트: 2 spaces
- Quotes: **single quotes** (`'`)
- Semicolons: **없음** (prettier `semi: false`)
- Trailing comma: `all`
- `any` 금지. 어쩔 수 없을 때 `unknown` + 타입가드
- React: 함수 컴포넌트 선언문, 훅은 화살표 함수, 이벤트 핸들러는 `handleXxx`
- Props 타입: `type` 선호 (`interface`는 확장 가능성이 명확할 때만)

```tsx
// 좋은 예
type NodeEditorProps = {
  workflowId: string
  onChange?: (workflow: Workflow) => void
}

export function NodeEditor({ workflowId, onChange }: NodeEditorProps) {
  const nodes = useEditorStore((s) => s.nodes)

  const handleAddNode = () => {
    // ...
  }

  return <div>{/* ... */}</div>
}
```

### 3.5 Import Order

**TypeScript**:
```typescript
// 1. Node/외부 라이브러리
import { useEffect } from 'react'
import { invoke } from '@tauri-apps/api/core'

// 2. 내부 절대 경로 (@/)
import { Button } from '@/components/ui/button'
import { useRunStore } from '@/stores/run-store'

// 3. 상대 경로
import { EdgeRenderer } from './edge-renderer'

// 4. 타입 전용 import
import type { Workflow } from '@/types/workflow.types'

// 5. 스타일
import './node-editor.css'
```

**Python**:
```python
# 1. 표준 라이브러리
from __future__ import annotations
import asyncio
from pathlib import Path

# 2. 외부 라이브러리
from fastapi import FastAPI
from pydantic import BaseModel

# 3. 내부 패키지 (절대)
from orca_core.schema import Workflow, Run
from orca_core.policy import PolicyEngine

# 4. 상대 경로 (같은 패키지 내부만)
from .registry import ToolRegistry
```

**Rust**:
```rust
// 1. std
use std::sync::Arc;

// 2. 외부 crate
use serde::{Deserialize, Serialize};
use tauri::State;

// 3. 내부 crate (crate::)
use crate::bridge::SidecarBridge;
use crate::config::AppConfig;
```

---

## 4. Component / Module Rules

### 4.1 React 컴포넌트 구조

```tsx
// 1. import
// 2. 타입 정의
// 3. 상수
// 4. 컴포넌트
// 5. 하위 헬퍼 (같은 파일에서만 사용)
```

- 한 파일에 1 public 컴포넌트 (동일 파일 내 private 서브 컴포넌트는 허용).
- JSX가 80줄을 넘으면 분할 검토.
- Props 기본값은 구조분해에서 지정 (`function X({ a = 10 }: P)`).

### 4.2 React Flow 노드 타입 등록

노드 에디터의 각 노드 타입은 `features/editor/nodes/<kind>/`에 배치:

```
features/editor/nodes/
├── agent-node/
│   ├── AgentNodeView.tsx
│   ├── AgentNodeInspector.tsx
│   └── index.ts
├── router-node/
└── approval-node/
```

등록은 `features/editor/nodes/registry.ts`에서 1곳에 모은다.

### 4.3 Tool 구현 규칙 (Python)

모든 툴은 동일한 인터페이스를 따른다.

```python
# sidecar/orca_core/tools/_base.py
from typing import Protocol, runtime_checkable

@runtime_checkable
class Tool(Protocol):
    id: str                    # e.g. "fs.read_file"
    namespace: ToolNamespace   # Literal["fs","shell","browser","os","web","custom"]
    side_effect: SideEffect
    reversible: bool
    default_dry_run: bool

    def input_schema(self) -> dict: ...
    def output_schema(self) -> dict: ...
    def permissions(self) -> list[Permission]: ...
    async def run(self, args: dict, ctx: ToolContext) -> ToolResult: ...
    async def dry_run(self, args: dict, ctx: ToolContext) -> ToolResult: ...
```

**필수 규칙**:
1. `run()` 진입 시 반드시 `ctx.policy.check(...)`를 호출해 정책 결정을 받는다.
2. `side_effect ∈ {write, destructive, network}` 이면 `dry_run()` 구현 필수.
3. `reversible=True` 이면 `run()` 내부에서 `ctx.journal.record(before=..., after=...)`를 호출한다.
4. 파괴적·민감 작업은 `ctx.audit.record(...)` 호출 (정책 엔진이 대부분 자동화).
5. 툴은 자체 I/O를 직접 수행하지 않고 `ctx.io`(감사/저널/권한 래퍼)를 거친다.

### 4.4 Provider 어댑터 규칙 (Python)

```python
class ProviderAdapter(Protocol):
    kind: ProviderKind

    async def chat(self, req: ChatRequest) -> ChatResponse: ...
    async def stream_chat(self, req: ChatRequest) -> AsyncIterator[ChatChunk]: ...
    async def health(self) -> ProviderHealth: ...
```

- OpenAI 호환 엔드포인트가 있으면 `openai_compatible` 어댑터를 상속/위임한다.
- 네이티브 API(예: Ollama 고유 엔드포인트)는 별도 구현하되 결과는 공통 `ChatResponse`로 정규화.
- API 키는 반드시 `ProviderSecretStore`(OS 키체인 래퍼)에서 조회. 코드·로그·Pydantic dump 어디에도 평문 저장 금지.

---

## 5. Environment Variables & Configuration

OrcaFlow는 **단일 사용자 로컬 데스크톱 앱**이므로 전통적 `.env` 기반 서버 설정 대신 **`~/.orcaflow/config.toml` + OS 키체인**을 1차로 사용한다. 환경변수는 개발 빌드·디버그·CI용으로만 유지한다.

### 5.1 Config 계층

| Source | 우선순위 | 용도 |
|--------|:--------:|------|
| CLI 인자 / 앱 런치 옵션 | 1 (최우선) | 디버그, 임시 override |
| 환경변수 (`ORCA_*`) | 2 | 개발 빌드, CI |
| `~/.orcaflow/config.toml` | 3 | 사용자 영구 설정 |
| 내장 기본값 (`default_config.rs` / `defaults.py`) | 4 | 팩토리 기본 |

### 5.2 환경변수 네이밍 규칙

| Prefix | Purpose | Scope |
|--------|---------|-------|
| `ORCA_` | 앱 전역 설정 | 공용 |
| `ORCA_DEV_` | 개발 전용 | 개발 빌드 |
| `ORCA_TEST_` | 테스트 전용 | 테스트 러너 |
| `ORCA_DEBUG_` | 디버그 토글 | 문제 해결 |

- **모두 UPPER_SNAKE_CASE**
- **시크릿은 환경변수 금지**. API 키/토큰은 키체인만 사용. 예외: CI 머신의 `ORCA_TEST_OLLAMA_URL` 같은 비밀 아닌 값은 허용.

### 5.3 예시 (.env.example — 개발용만)

```bash
# .env.example — 개발/디버깅 용도 한정. 실제 사용자 설정은 ~/.orcaflow/config.toml 사용.

# 앱
ORCA_DEV_LOG_LEVEL=debug
ORCA_DEV_SIDECAR_PORT=0          # 0 = 자동 할당
ORCA_DEV_WORKSPACE=~/.orcaflow-dev

# 테스트
ORCA_TEST_OLLAMA_URL=http://localhost:11434
ORCA_TEST_DISABLE_KEYCHAIN=1     # 통합 테스트 시 키체인 우회
```

### 5.4 config.toml 예시

```toml
# ~/.orcaflow/config.toml
[app]
log_level = "info"
telemetry = false                 # 기본 비활성 (로컬 우선)

[db]
path = "~/.orcaflow/db.sqlite"

[sidecar]
port = 0                          # 자동 할당 권장
host = "127.0.0.1"                # 외부 바인딩 절대 금지

[providers.default]
name = "ollama-qwen2.5-14b"

[providers.ollama]
base_url = "http://localhost:11434"

[policy]
mode = "ask"                      # strict | ask | trusted
auto_approve_reversible = true
require_dry_run_for = ["destructive", "write"]
```

### 5.5 검증

앱 기동 시 Pydantic Settings(Python) / serde(Rust) 로 전체 설정을 1회 검증한다. 실패 시 fail-fast.

---

## 6. Clean Architecture & Dependency Rules

OrcaFlow는 Dynamic 레벨로 시작하되, 보안이 핵심이므로 **Policy / Audit / Journal 계층은 Domain 순수성(외부 I/O 비의존)을 유지**하고, Tool·Provider는 Infrastructure 취급한다.

### 6.1 레이어 맵

```
┌──────────────────────────────────────────────────────────────┐
│  Presentation (frontend/src)                                 │
│    components/, features/, hooks/, stores/                   │
└──────────────────────────────┬───────────────────────────────┘
                               │ (Tauri IPC, SSE)
┌──────────────────────────────▼───────────────────────────────┐
│  App Shell (app/src-tauri/src)                               │
│    commands/, bridge/, permission/                           │
└──────────────────────────────┬───────────────────────────────┘
                               │ (HTTP / stdin IPC)
┌──────────────────────────────▼───────────────────────────────┐
│  Application (sidecar/orca_core/orchestrator, ipc)           │
│    유스케이스·실행엔진·플래너                                    │
└──────────────────────────────┬───────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────┐
│  Domain (sidecar/orca_core/schema, policy, audit, journal)   │
│    순수 모델·정책 규칙·감사 정책·저널 정책                         │
└──────────────────────────────┬───────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────┐
│  Infrastructure                                              │
│   sidecar/orca_core/providers, tools, persistence            │
│   app/src-tauri/src/bridge                                   │
└──────────────────────────────────────────────────────────────┘
```

### 6.2 의존 방향 규칙

| Layer | 허용 의존 | 금지 의존 |
|-------|-----------|-----------|
| **Presentation** | App Shell, Domain 타입 (`frontend/src/types`) | Infrastructure 직접 호출, Python sidecar 직접 |
| **App Shell (Rust)** | Application (sidecar IPC), Domain 타입 | Infrastructure 내부 구현 직접 참조 |
| **Application** | Domain, Infrastructure (의존성 역전 via Protocol) | Presentation |
| **Domain** | (없음, 순수) | 모든 외부 레이어 |
| **Infrastructure** | Domain | Application, Presentation |

### 6.3 Python 내부 의존 규칙

- `orca_core/schema/` 는 **외부 의존 금지**. `pydantic`·표준 라이브러리만.
- `orca_core/policy/` 는 schema 만 의존. DB·네트워크 I/O 금지.
- `orca_core/audit/`, `orca_core/journal/` 은 policy·schema 만 의존.
- `orca_core/tools/*` 는 Infrastructure → Domain·Policy만 참조. **tools ↔ tools 간 횡단 import 금지**.
- `orca_core/orchestrator/` 는 schema·policy·journal·audit·providers·tools 조립만.

### 6.4 Frontend 의존 규칙

- `components/ui/` 는 순수 UI. 비즈니스 로직·Tauri API·스토어 import 금지.
- `features/*/` 는 다른 feature 내부 직접 import 금지. 필요 시 상위 `stores/` 경유.
- `lib/api/` 만 Tauri IPC 호출 허용. 컴포넌트에서 `invoke`/`listen` 직접 호출 금지.
- `types/` 는 schema.md에서 파생된 읽기 전용 타입. runtime 로직 금지.

### 6.5 의존 위반 감지

- Frontend: ESLint `import/no-restricted-paths` + `eslint-plugin-boundaries`
- Python: `import-linter` 로 레이어 규칙 선언
- Rust: `cargo-deps` + 크레이트 분할
- CI 필수 단계로 실행

---

## 7. Logging, Audit & Observability Conventions

### 7.1 로그 포맷 (구조화 JSON 필수)

모든 로그는 JSON 1줄 형식(JSONL)으로 stdout 및 `~/.orcaflow/logs/app.log`에 기록한다.

**필수 필드**:
```json
{
  "ts": "2026-04-12T11:34:00.123Z",
  "level": "info",
  "component": "orchestrator",
  "event": "tool_call.started",
  "run_id": "019587a1-...",
  "run_step_id": "019587a1-...",
  "actor": "file_organizer",
  "message": "fs.read_file invoked",
  "context": { "tool_id": "fs.read_file", "path": "~/Desktop/..." }
}
```

### 7.2 로그 레벨

| Level | 용도 |
|-------|------|
| `trace` | 상세 추론·IPC 프레임 덤프 (기본 비활성) |
| `debug` | 개발 디버깅 |
| `info` | 정상 상태 이벤트 (run.started, tool_call.started) |
| `warn` | 복구 가능한 이상 (타임아웃 재시도 등) |
| `error` | 사용자 개입 필요 (공급자 오류, 정책 위반) |
| `audit` | 감사 로그 전용 레벨 (다른 레벨과 섞지 말 것) |

### 7.3 이벤트 코드 (schema.md 와 일치)

`<domain>.<action>[.<result>]` 형식:
- `run.started`, `run.succeeded`, `run.failed`
- `run_step.started`, `run_step.succeeded`, `run_step.failed`
- `tool_call.started`, `tool_call.succeeded`, `tool_call.denied`
- `policy.checked`, `policy.denied`, `policy.ask`
- `approval.requested`, `approval.approved`, `approval.rejected`, `approval.expired`
- `journal.recorded`, `journal.restored`
- `provider.request`, `provider.error`, `provider.timeout`

### 7.4 금지 사항 (PII·시크릿 보호)

- API 키·비밀번호·토큰을 로그·에러 메시지·Pydantic 덤프에 **절대** 포함 금지.
- Pydantic 모델에 시크릿 필드가 있으면 `SecretStr` 사용 + `model_dump(exclude_secrets=True)`.
- 경로 로깅은 허용하되 사용자 홈은 `~` 로 마스킹 (보안 + 가독성).
- 로그 저장소는 `~/.orcaflow/logs/`. 순환(rotation): 일 단위 + 최대 14일 보관 (기본).

### 7.5 Audit Log (append-only)

- `schema.md §3.15 AuditLog` 불변 규칙을 따른다.
- 애플리케이션 레이어(audit 계층)에서만 insert 가능. UPDATE/DELETE 경로 없음.
- 파일 미러(`audit.log` JSONL)에도 동일 레코드 기록.
- 레벨 `audit` 사용 시 일반 로그와 파일 분리 권장.

### 7.6 에러 메시지 규약

- 사용자 표시용: 한국어, 1문장 사유 + 수정 힌트.
- 개발자용(stack/trace): 영문, 내부 코드 포함.
- 정책 거부 메시지는 반드시 어떤 rule이 차단했는지 rule ID와 함께 기록.

---

## 8. Security Conventions

### 8.1 파괴적 작업 기본 플로우

1. 에이전트가 툴 호출 계획(`dry_run`) 요청
2. Policy 엔진 검증 → `allow | ask | deny | dry_run_only`
3. `ask` 이면 `ApprovalRequest` 생성, UI 프롬프트
4. 승인 시 `JournalEntry.before` 기록
5. 실행
6. `AuditLog` 기록
7. 실패 시 `JournalEntry` 를 통해 복구 (가능한 경우)

**이 순서를 건너뛰는 툴은 리뷰·머지 금지.**

### 8.2 파일 경로 처리

- 사용자 경로 입력은 **반드시 정규화**(`Path.expanduser().resolve()`).
- 심볼릭 링크 추적은 정책 기본값으로 차단, 경로 화이트리스트 밖 타깃이면 거부.
- `..` 포함 경로는 정규화 후 재검증.
- 시스템 디렉토리(`/System`, `/Library`, `C:\Windows` 등)는 기본 거부 리스트 내장.

### 8.3 쉘 실행

- `shell.exec` 는 기본 `mode=ask`. `shell.exec` 를 `trusted` 로 승격하는 정책은 전체 덮어쓰기가 아니라 화이트리스트(정규식) 기반.
- 파이프·리다이렉트 해석은 Python 레이어에서 **shlex.split + subprocess.run(shell=False)** 기본.
- 타임아웃·출력 길이 제한 필수.

### 8.4 네트워크

- sidecar는 `127.0.0.1` 외부 바인딩 금지.
- 사용자 프록시 설정은 config.toml 의 `[network]` 섹션.
- 에이전트 툴의 outbound HTTP는 `web.http_request` 경유만. `requests` 직접 사용 금지.

### 8.5 플러그인

- 플러그인 매니페스트(`plugin.yaml`)의 `permissions` 합집합을 플러그인 설치 시 사용자에게 명시하고 승인 받는다.
- 플러그인 서명·해시 검증은 v0.1에서 optional, v0.2에서 필수화 검토.

---

## 9. Reusability & Duplication Prevention

### 9.1 추출 기준

| 기준 | 조치 |
|------|------|
| 같은 로직 2회 이상 등장 | 함수/훅/유틸로 추출 |
| 네임이 필요한 복잡한 로직 | 함수로 분리 |
| 같은 UI 패턴 반복 | 컴포넌트로 추출 |
| JSX 80줄 초과 | 분할 검토 |
| 하드코딩 값 | 상수 파일로 |

### 9.2 Config 기반 확장

새 상태·옵션 추가 시 조건문 나열 대신 config 객체를 선호한다 (phase-2-convention 스킬 §7.1 참고).

### 9.3 Strategy / Plugin 구조 준수

Tool·Provider는 이미 Strategy + 레지스트리 패턴을 쓴다. 새 툴·공급자는 레지스트리에 등록만 하면 되도록 유지한다. 특수 조건 분기가 필요한 순간 = 설계 오류 신호.

---

## 10. Testing Conventions

| Layer | Framework | 위치 |
|-------|-----------|------|
| Rust | `cargo test` | `app/src-tauri/src/**` 내부 `#[cfg(test)]` |
| Python (unit) | `pytest` | `sidecar/tests/unit/` |
| Python (integration) | `pytest` + `httpx.AsyncClient` | `sidecar/tests/integration/` |
| TypeScript (unit) | `vitest` | `frontend/src/**/*.test.ts(x)` |
| E2E | `playwright` (Tauri 앱 직접) | `e2e/` |

**규칙**:
- Domain·Policy·Audit·Journal 계층은 **커버리지 80% 이상 필수**.
- 모든 툴은 `dry_run`·`run`·`policy.denied` 3가지 경로 테스트.
- 테스트에서 실제 LLM 호출은 금지. 공급자 fake(`FakeProviderAdapter`)를 사용.
- 파일 시스템 테스트는 `tmp_path`(pytest) / `tempfile` 사용. 홈 디렉토리 변경 금지.

---

## 11. Git & Commit Conventions

### 11.1 Branch 네이밍

| Prefix | 용도 | 예시 |
|--------|------|------|
| `feat/` | 신규 기능 | `feat/policy-engine` |
| `fix/` | 버그 수정 | `fix/audit-insert-race` |
| `refactor/` | 리팩토링 | `refactor/tool-registry` |
| `docs/` | 문서 | `docs/update-glossary` |
| `chore/` | 빌드·설정 | `chore/rust-toolchain` |
| `spike/` | 실험 | `spike/langgraph-runner` |

### 11.2 Commit 메시지

Conventional Commits를 쓰되, 범위는 폴더가 아닌 **도메인**으로 표기한다.

```
feat(policy): add path whitelist rule type

- PolicyRule.scope 에 fs_path 스코프 추가
- strict 모드에서 매칭 없을 때 deny 반환

Refs: schema.md §3.9
```

허용 scope: `workflow`, `agent`, `tool`, `llm`, `provider`, `policy`, `audit`, `journal`, `ui`, `ipc`, `sidecar`, `shell`, `build`, `docs`.

---

## 12. Validation Checklist

### Naming / Structure
- [ ] 언어별 네이밍 규칙 고정 (§1)
- [ ] 경계 케이싱(snake_case ↔ camelCase) 변환 지점 명시 (§1.3)
- [ ] Feature-slice 배럴 규칙 정의 (§2.1)
- [ ] Tool ID / 이벤트 코드 규약 정의 (§1.4, §7.3)

### Config / Env
- [ ] config.toml + 키체인 기반 설계 확정 (§5)
- [ ] 환경변수는 개발/CI로 한정 (§5.2)
- [ ] 시크릿 환경변수 금지 규칙 명시

### Architecture
- [ ] 4레이어 의존 맵 정의 (§6)
- [ ] Python 내부 의존 규칙 (schema 순수성) (§6.3)
- [ ] 의존 위반 CI 감지 도입 (§6.5)

### Logging / Audit / Security
- [ ] JSON 구조화 로그 + 필수 필드 확정 (§7.1)
- [ ] 이벤트 코드 네임스페이스 확정 (§7.3)
- [ ] PII/시크릿 로그 금지 규칙 (§7.4)
- [ ] 파괴적 작업 7단계 기본 플로우 (§8.1)
- [ ] 쉘/파일/네트워크 세부 제약 (§8.2~§8.4)

### Testing
- [ ] 계층별 테스트 프레임워크 고정 (§10)
- [ ] Domain/Policy/Audit/Journal 80% 커버리지 규칙
- [ ] Fake Provider 사용 강제

---

## 13. Next Steps

1. 본 컨벤션 검토 및 승인
2. 루트 `CONVENTIONS.md` 요약본 + `CLAUDE.md` 에 본 문서 위치 반영
3. 포맷터/린터/CI 설정 파일 템플릿 작성 (`.editorconfig`, `rustfmt.toml`, `pyproject.toml [tool.ruff]`, `.eslintrc`, `.prettierrc`)
4. `/phase-3-mockup` — 채팅 + 노드 에디터 + Run Monitor + Approval Dialog UI 목업
5. 또는 `/pdca design OrcaFlow` — Tauri↔sidecar IPC 프로토콜, 정책 엔진 런타임, 플래너 파이프라인 상세 설계

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-04-12 | 초안 — 폴리글랏(Rust/Python/TS) 네이밍·폴더·로깅·감사·보안·테스트 규약 | 2z |
