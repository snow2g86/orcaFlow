# OrcaFlow Schema Definition

> Phase 1 Deliverable — 데이터 구조 및 엔티티 정의
>
> **Project**: OrcaFlow
> **Date**: 2026-04-12
> **Version**: 1.0
> **Level**: Dynamic (Tauri 데스크톱 앱 + Python FastAPI sidecar + SQLite)

본 문서는 OrcaFlow의 핵심 엔티티·관계·저장 형태를 정의한다. 용어는 `glossary.md`와 1:1 대응하며, YAML 스키마·DB 스키마·API 스키마는 모두 본 정의를 단일 출처(SSoT)로 삼는다.

---

## 1. Terminology Definition

> 전체 용어는 [glossary.md](./glossary.md) 참조. 본 절은 스키마 이해에 필요한 핵심만 발췌.

| Term | Definition | Notes |
|------|------------|-------|
| Workflow | 에이전트 노드와 엣지로 구성된 실행 가능한 DAG | YAML 직렬화 |
| AgentRole | 재사용 가능한 에이전트 역할 템플릿 | system prompt + tools + llm_profile |
| AgentNode | Workflow 그래프상의 에이전트 인스턴스 | role 참조 + override |
| Tool | 에이전트가 호출 가능한 기능 (fs/shell/browser/os/web/custom) | 스키마·권한 포함 |
| LLMProfile | 공급자 + 모델 + 파라미터 프리셋 | Provider 참조 |
| Provider | LLM 공급자 (Ollama/vLLM/Together/Groq…) | OpenAI 호환 엔드포인트 |
| Policy | 툴 호출 허용/승인/차단 규칙 집합 | 경로·명령·네트워크 범위 |
| Run | Workflow 1회 실행 인스턴스 | 상태·시작/종료·리소스 사용량 |
| RunStep | Run 내 단일 단계 | LLM / Tool / Routing |
| ApprovalRequest | 민감 작업에 대한 사용자 승인 단위 | HITL |
| AuditLog | 파괴적/민감 작업의 불변 기록 | append-only |
| JournalEntry | 되돌리기 가능한 변경 이력 | 파일/쉘 부작용 기록 |

---

## 2. Entity List

| Entity | Description | Key Attributes | Storage |
|--------|-------------|----------------|---------|
| Workflow | 에이전트 그래프 정의 | id, name, version, nodes, edges | SQLite + YAML export |
| AgentRole | 재사용 가능한 에이전트 역할 | id, name, system_prompt, tools, llm_profile_id, role_type | SQLite |
| AgentNode | 워크플로우 내 에이전트 인스턴스 | id, workflow_id, role_id, position, overrides | SQLite (embedded in Workflow) |
| Edge | 노드 간 연결 | from_node_id, to_node_id, condition | SQLite (embedded) |
| Tool | 툴 정의 (내장 + 사용자 플러그인) | id, name, namespace, input_schema, permissions | SQLite + 코드 레지스트리 |
| LLMProfile | LLM 프로파일 | id, name, provider_id, model, params | SQLite |
| Provider | LLM 공급자 정의 | id, name, kind, base_url, auth_ref | SQLite (+ keychain for secret) |
| Policy | 정책 집합 | id, name, mode, rules | SQLite + YAML |
| PolicyRule | 개별 규칙 | id, policy_id, scope, effect, matcher | SQLite |
| Run | 워크플로우 실행 인스턴스 | id, workflow_id, status, started_at, ended_at, stats | SQLite |
| RunStep | 실행 단계 | id, run_id, parent_step_id, kind, payload, result | SQLite |
| ToolCall | 툴 호출 기록 | id, run_step_id, tool_id, args, result, duration_ms | SQLite |
| Message | 에이전트/사용자 메시지 | id, run_id, role, content, tokens | SQLite |
| ApprovalRequest | 승인 요청 | id, run_step_id, reason, state, decided_at | SQLite |
| AuditLog | 감사 로그 | id, actor, action, target, status, at | SQLite (append-only view) |
| JournalEntry | 변경 저널 | id, run_step_id, kind, before, after, reversible | SQLite |
| ConversationTurn | 채팅 턴 (플래너 입력) | id, session_id, user_text, resolved_workflow_id | SQLite |
| WorkflowTemplate | 공유용 템플릿 | id, name, author, yaml, tags | SQLite + `~/.orcaflow/workflows/` |
| Plugin | 외부 툴·공급자 플러그인 | id, name, version, kind, entrypoint | SQLite + 파일시스템 |

---

## 3. Entity Details

### 3.1 Workflow

**Description**: 사용자가 구성·저장·공유·실행할 수 있는 멀티 에이전트 그래프. YAML 직렬화를 1차 포맷으로 삼고 DB에는 정규화된 형태로 저장한다.

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| id | string (uuid v7) | Y | 고유 식별자 |
| name | string | Y | 사용자 지정 이름 |
| description | string | N | 설명 |
| version | int | Y | 스키마 버전 (현재 1) |
| created_at | datetime | Y | 생성 시각 |
| updated_at | datetime | Y | 수정 시각 |
| author | string | N | 작성자 |
| tags | string[] | N | 검색/분류용 태그 |
| nodes | AgentNode[] | Y | 에이전트 노드 리스트 |
| edges | Edge[] | Y | 노드 간 연결 |
| entrypoint_node_id | string | Y | 실행 시작 노드 |
| policy_id | string | N | 연결된 정책 (없으면 전역 정책) |
| default_llm_profile_id | string | N | 노드별 override가 없을 때의 기본 LLM |

**Relationships**:
- 1 : N → AgentNode
- 1 : N → Edge
- 1 : N → Run
- N : 1 → Policy
- N : 1 → LLMProfile

**YAML 예시**:
```yaml
version: 1
name: "문서 정리 플로우"
author: "2z"
policy: "default"
default_llm_profile: "ollama-qwen2.5-14b"
nodes:
  - id: planner
    role: "planner"
    position: { x: 0, y: 0 }
  - id: file_worker
    role: "file-organizer"
    position: { x: 240, y: 0 }
    overrides:
      llm_profile: "ollama-qwen2.5-7b"
edges:
  - from: planner
    to: file_worker
    condition: "state.plan != null"
entrypoint: planner
```

---

### 3.2 AgentRole

**Description**: 에이전트의 "직무 설명서". 시스템 프롬프트, 사용 가능한 툴, LLM 프로파일, 행동 패턴(role_type)을 포함하는 재사용 가능한 정의. 사용자는 역할만 정의하고 워크플로우에서는 역할 참조만 한다.

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| id | string | Y | 고유 식별자 |
| name | string | Y | 예: "file-organizer" |
| display_name | string | N | UI 표시명 |
| role_type | enum | Y | `worker` / `planner` / `supervisor` / `critic` |
| system_prompt | string | Y | 기본 시스템 프롬프트 |
| goal | string | N | 목표 요약 (플래너가 참고) |
| tools | string[] | Y | 허용 툴 ID 리스트 |
| llm_profile_id | string | Y | 기본 LLM 프로파일 |
| max_steps | int | N | 단일 호출당 최대 스텝 (기본 10) |
| temperature_override | float | N | 파라미터 오버라이드 |
| tags | string[] | N | 분류 |

**Relationships**:
- N : 1 → LLMProfile
- N : M → Tool
- 1 : N → AgentNode

---

### 3.3 AgentNode

**Description**: Workflow 그래프에 배치된 에이전트 인스턴스. 역할(Role)을 참조하고, 노드 수준에서 프롬프트/LLM/툴을 override 할 수 있다.

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| id | string | Y | 워크플로우 내 고유 ID |
| workflow_id | string | Y | 소속 워크플로우 |
| role_id | string | Y | 참조하는 AgentRole |
| label | string | N | UI 라벨 |
| position | {x:int,y:int} | Y | 노드 에디터 좌표 |
| overrides | object | N | role 값 덮어쓰기 (prompt, llm_profile, tools, params) |
| input_schema | JSONSchema | N | 입력 계약 |
| output_schema | JSONSchema | N | 출력 계약 |

**Relationships**:
- N : 1 → Workflow
- N : 1 → AgentRole

---

### 3.4 Edge

**Description**: 워크플로우 그래프의 유향 간선. 조건(condition)에 따라 라우팅.

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| from_node_id | string | Y | 시작 노드 |
| to_node_id | string | Y | 도착 노드 |
| condition | string (JSONLogic or JS-expr subset) | N | 라우팅 조건 (기본: 무조건 전이) |
| label | string | N | UI 라벨 |

**Relationships**:
- N : 1 → Workflow
- N : 1 → AgentNode (from/to)

---

### 3.5 Tool

**Description**: 에이전트가 호출 가능한 능력. 내장 툴(파일/쉘/브라우저/OS/웹)과 사용자 플러그인 툴을 공통 스키마로 관리. 모든 Tool은 `permissions` 메타를 갖고 Policy 엔진이 이를 검증한다.

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| id | string | Y | `namespace.name` (예: `fs.read_file`) |
| namespace | enum | Y | `fs` / `shell` / `browser` / `os` / `web` / `custom` |
| name | string | Y | 툴 이름 |
| display_name | string | N | UI 표시명 |
| description | string | Y | LLM 함수 호출용 설명 |
| input_schema | JSONSchema | Y | 인자 스키마 |
| output_schema | JSONSchema | N | 결과 스키마 |
| permissions | Permission[] | Y | 요구 권한 목록 |
| side_effect | enum | Y | `none` / `read` / `write` / `destructive` / `network` |
| reversible | bool | Y | 저널 기반 되돌리기 가능 여부 |
| default_dry_run | bool | Y | 기본 드라이런 여부 |
| plugin_id | string | N | 플러그인 제공 툴인 경우 소스 |

**Permission 구조**:
```yaml
permissions:
  - kind: fs_path          # fs_path | shell_command | network_host | os_api | clipboard
    scope: "~/Documents/**"
    action: read           # read | write | delete | execute
```

**Relationships**:
- N : 1 → Plugin
- 1 : N → ToolCall
- N : M → AgentRole (via AgentRole.tools)

**v0.1 내장 툴 목록**:

| ID | Side Effect | Reversible | 설명 |
|----|:-----------:|:----------:|-----|
| `fs.read_file` | read | - | 파일 읽기 |
| `fs.write_file` | write | Y | 파일 쓰기 (저널 기록) |
| `fs.move` | write | Y | 이동/이름 변경 |
| `fs.delete` | destructive | Y (휴지통 경유) | 삭제 |
| `fs.list` | read | - | 디렉토리 나열 |
| `shell.exec` | write/destructive | N | 명령 실행 (정책 검증 필수) |
| `browser.open` | network | - | 브라우저 세션 시작 |
| `browser.navigate` | network | - | URL 이동 |
| `browser.scrape` | network+read | - | DOM/텍스트 추출 |
| `browser.click` | network+write | N | 클릭 |
| `os.notify` | write | - | OS 알림 |
| `os.clipboard_read` | read | - | 클립보드 읽기 |
| `os.clipboard_write` | write | Y | 클립보드 쓰기 |
| `os.applescript` (macOS) | destructive | N | AppleScript/JXA 실행 |
| `os.powershell` (Windows) | destructive | N | PowerShell 실행 |
| `web.http_request` | network | - | HTTP 요청 |
| `web.search` | network | - | 검색 API |

---

### 3.6 LLMProfile

**Description**: "이 모델을 이런 파라미터로 호출한다"는 재사용 설정. AgentRole은 LLMProfile을 참조한다.

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| id | string | Y | 고유 식별자 |
| name | string | Y | 예: "ollama-qwen2.5-14b" |
| provider_id | string | Y | Provider 참조 |
| model | string | Y | 모델 식별자 (예: "qwen2.5:14b") |
| params | object | Y | temperature, top_p, max_tokens, stop 등 |
| context_window | int | N | 컨텍스트 한계 (토큰) |
| is_tool_capable | bool | Y | 함수 호출 지원 여부 |
| is_planner | bool | N | 플래너 전용 프로파일 여부 |
| is_default | bool | N | 기본 프로파일 여부 |

**Relationships**:
- N : 1 → Provider
- 1 : N → AgentRole

---

### 3.7 Provider

**Description**: LLM 공급자. OpenAI 호환 인터페이스를 기본 가정으로 하고, 필요 시 어댑터 레이어를 통해 네이티브 API에 연결.

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| id | string | Y | 고유 식별자 |
| name | string | Y | 사용자 표시명 |
| kind | enum | Y | `ollama` / `vllm` / `llama_cpp` / `lm_studio` / `tgi` / `openai_compatible` / `together` / `groq` / `fireworks` |
| base_url | string | Y | 엔드포인트 |
| api_key_ref | string | N | OS 키체인 참조 키 (원문 저장 금지) |
| headers | object | N | 추가 헤더 |
| timeout_ms | int | N | 기본 30000 |
| health_url | string | N | 헬스체크 |

**Relationships**:
- 1 : N → LLMProfile

---

### 3.8 Policy

**Description**: 툴 호출·파일 접근·네트워크 호출에 대한 허용/차단/승인 규칙 집합. 워크플로우·역할·툴 단위로 바인딩 가능하며, 모드에 따라 기본 동작이 달라진다.

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| id | string | Y | 고유 식별자 |
| name | string | Y | 예: `default`, `strict`, `coding-assistant` |
| mode | enum | Y | `strict` (기본 차단) / `ask` (기본 승인 프롬프트) / `trusted` (기본 허용) |
| rules | PolicyRule[] | Y | 규칙 리스트 (우선순위 순서) |
| require_dry_run_for | enum[] | N | `destructive`, `write`, `network` 등 드라이런 강제 대상 |
| auto_approve_reversible | bool | N | 되돌릴 수 있는 작업 자동 승인 여부 |

**Relationships**:
- 1 : N → PolicyRule
- 1 : N → Workflow

---

### 3.9 PolicyRule

**Description**: 개별 정책 규칙. 스코프(대상)·매처(조건)·효과(결과)로 구성.

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| id | string | Y | 고유 식별자 |
| policy_id | string | Y | 소속 정책 |
| priority | int | Y | 낮을수록 우선 적용 |
| scope | enum | Y | `fs_path` / `shell_command` / `network_host` / `os_api` / `tool_id` |
| matcher | string | Y | 글롭/정규식/리터럴 (scope별 해석) |
| effect | enum | Y | `allow` / `deny` / `ask` / `dry_run_only` |
| reason | string | N | 사용자 표시용 설명 |

**예시**:
```yaml
policy: default
mode: ask
rules:
  - priority: 10
    scope: fs_path
    matcher: "~/Desktop/**"
    effect: allow
  - priority: 20
    scope: fs_path
    matcher: "~/**/.ssh/**"
    effect: deny
    reason: "SSH 키 보호"
  - priority: 30
    scope: shell_command
    matcher: "^(rm\\s+-rf\\s+/).*"
    effect: deny
    reason: "루트 재귀 삭제 차단"
  - priority: 100
    scope: tool_id
    matcher: "os.applescript"
    effect: ask
```

**Relationships**:
- N : 1 → Policy

---

### 3.10 Run

**Description**: 워크플로우 1회 실행 인스턴스.

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| id | string | Y | 고유 식별자 |
| workflow_id | string | Y | 대상 워크플로우 |
| workflow_snapshot | json | Y | 실행 시점 YAML 스냅샷 (재현성) |
| trigger | enum | Y | `chat` / `manual` / `scheduled` / `api` |
| status | enum | Y | `pending` / `running` / `awaiting_approval` / `succeeded` / `failed` / `cancelled` |
| started_at | datetime | Y | 시작 시각 |
| ended_at | datetime | N | 종료 시각 |
| stats | object | N | 토큰/지연/툴콜 수 집계 |
| error | object | N | 실패 시 스택/원인 |
| parent_run_id | string | N | 재실행/비교 연결 |

**Relationships**:
- N : 1 → Workflow
- 1 : N → RunStep
- 1 : N → Message
- 1 : N → ApprovalRequest

---

### 3.11 RunStep

**Description**: 실행 중 발생한 단일 단계. LLM 호출, 툴 호출, 라우팅 결정, 분기, 승인 대기 등.

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| id | string | Y | 고유 식별자 |
| run_id | string | Y | 소속 Run |
| parent_step_id | string | N | 트리 구조 |
| node_id | string | N | 현재 노드 |
| kind | enum | Y | `llm_call` / `tool_call` / `route` / `approval` / `dry_run` |
| payload | json | Y | 입력 |
| result | json | N | 출력 |
| status | enum | Y | `queued` / `running` / `succeeded` / `failed` / `blocked` |
| started_at | datetime | Y | 시작 |
| ended_at | datetime | N | 종료 |
| duration_ms | int | N | 계측 |
| tokens_in | int | N | 입력 토큰 |
| tokens_out | int | N | 출력 토큰 |

**Relationships**:
- N : 1 → Run
- 1 : N → ToolCall
- 1 : 0..1 → ApprovalRequest
- 1 : 0..N → JournalEntry

---

### 3.12 ToolCall

**Description**: 툴 호출 1건의 전·후 기록.

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| id | string | Y | 고유 식별자 |
| run_step_id | string | Y | 소속 스텝 |
| tool_id | string | Y | 호출된 툴 |
| args | json | Y | 입력 인자 |
| result | json | N | 결과 |
| error | json | N | 실패 시 |
| dry_run | bool | Y | 드라이런 여부 |
| policy_decision | enum | Y | `allow` / `denied` / `approved` / `dry_run_only` |
| audit_log_id | string | N | AuditLog 참조 (side_effect ≠ none일 때) |
| duration_ms | int | N | 소요 |

**Relationships**:
- N : 1 → RunStep
- N : 1 → Tool
- 1 : 0..1 → AuditLog
- 1 : 0..N → JournalEntry

---

### 3.13 Message

**Description**: 에이전트·사용자 간 메시지. LLM 컨텍스트 재구성과 히스토리 뷰에 사용.

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| id | string | Y | 고유 식별자 |
| run_id | string | Y | 소속 Run |
| node_id | string | N | 발화한 에이전트 노드 |
| role | enum | Y | `system` / `user` / `assistant` / `tool` |
| content | string | Y | 텍스트 |
| tool_call_id | string | N | role=tool인 경우 |
| tokens | int | N | 토큰 수 |
| created_at | datetime | Y | 생성 시각 |

**Relationships**:
- N : 1 → Run
- N : 0..1 → ToolCall

---

### 3.14 ApprovalRequest

**Description**: 민감/파괴적 작업에 대한 사용자 승인 요청. UI에서 실시간 프롬프트로 노출된다.

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| id | string | Y | 고유 식별자 |
| run_step_id | string | Y | 원인 스텝 |
| tool_call_id | string | N | 관련 툴 콜 |
| reason | string | Y | 요구 사유 |
| diff_preview | json | N | 드라이런 결과 미리보기 |
| state | enum | Y | `pending` / `approved` / `rejected` / `expired` |
| decided_at | datetime | N | 결정 시각 |
| decided_by | string | N | 사용자 식별자 |
| ttl_seconds | int | N | 기본 300 |

**Relationships**:
- N : 1 → Run
- N : 1 → RunStep
- N : 0..1 → ToolCall

---

### 3.15 AuditLog

**Description**: 파괴적/민감 작업의 불변 감사 기록. append-only 뷰로 관리.

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| id | string | Y | 고유 식별자 |
| at | datetime | Y | 발생 시각 |
| actor | string | Y | 에이전트 노드 또는 `user` |
| action | string | Y | 예: `fs.delete`, `shell.exec` |
| target | string | Y | 대상 경로/명령/URL |
| status | enum | Y | `success` / `failed` / `blocked` / `approved` |
| policy_decision | enum | Y | 정책 결정 |
| run_id | string | Y | 연결 Run |
| run_step_id | string | Y | 연결 Step |
| hash_prev | string | N | 체인 무결성용 해시 (옵션) |
| hash_self | string | N | 현재 레코드 해시 |

**Relationships**:
- N : 1 → Run
- N : 1 → RunStep
- N : 0..1 → ToolCall

---

### 3.16 JournalEntry

**Description**: 되돌리기 가능한 변경 이력. `fs.write_file`, `fs.move`, `clipboard_write` 등 reversible 툴이 기록.

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| id | string | Y | 고유 식별자 |
| run_step_id | string | Y | 원인 스텝 |
| tool_call_id | string | Y | 원인 툴 콜 |
| kind | enum | Y | `fs_write` / `fs_move` / `fs_delete_to_trash` / `clipboard_write` / `custom` |
| before | json | N | 변경 전 스냅샷/경로 |
| after | json | N | 변경 후 스냅샷/경로 |
| before_storage_ref | string | N | before 페이로드 spill 파일 경로 (>256KB 시 별도 저장) |
| after_storage_ref | string | N | after 페이로드 spill 파일 경로 (before 와 **별도**) |
| reversible | bool | Y | 실제 복구 가능 여부 |
| restored_at | datetime | N | 복구된 경우 시각 |
| created_at | datetime | Y | 기록 시각 |

**Note (v1.1)**: 기존 단일 `storage_ref` 필드는 before/after 를 별도 파일에 저장하도록 분리되었다. 과거 구현에서 record_after 가 before 경로를 덮어써 복구 시점에 파괴적 변경이 재적용되는 버그가 있었다.

**Relationships**:
- N : 1 → RunStep
- N : 1 → ToolCall

---

### 3.17 ConversationTurn

**Description**: 채팅형 자연어 명령 인터페이스의 단일 턴. 플래너가 이 입력을 받아 Workflow를 생성하거나 기존 Workflow를 변형한다.

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| id | string | Y | 고유 식별자 |
| session_id | string | Y | 대화 세션 |
| user_text | string | Y | 사용자 입력 |
| planner_trace | json | N | 플래너 내부 reasoning |
| resolved_workflow_id | string | N | 생성/선택된 워크플로우 |
| run_id | string | N | 실제 실행된 Run |
| created_at | datetime | Y | 시각 |

**Relationships**:
- N : 0..1 → Workflow
- N : 0..1 → Run

---

### 3.18 WorkflowTemplate

**Description**: 공유·재사용을 위한 워크플로우 템플릿. YAML 파일로 export/import.

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| id | string | Y | 고유 식별자 |
| name | string | Y | 이름 |
| description | string | N | 설명 |
| author | string | N | 작성자 |
| yaml | string | Y | 워크플로우 YAML 원문 |
| tags | string[] | N | 분류 |
| created_at | datetime | Y | 시각 |

---

### 3.19 Plugin

**Description**: 사용자 정의 툴·공급자·역할 템플릿을 담은 외부 플러그인. v0.1은 로컬 디렉토리 기반.

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| id | string | Y | 고유 식별자 |
| name | string | Y | 플러그인 이름 |
| version | string | Y | SemVer |
| kind | enum | Y | `tool` / `provider` / `role` / `policy` |
| entrypoint | string | Y | Python 모듈 또는 파일 경로 |
| manifest_path | string | Y | `plugin.yaml` 경로 |
| enabled | bool | Y | 활성화 여부 |

---

## 4. Entity Relationship Diagram

```
                        ┌────────────────┐
                        │   Workflow     │
                        └───────┬────────┘
                                │ 1
               ┌────────────────┼────────────────┬──────────────┐
               │ N              │ N              │ N            │ 0..1
         ┌─────▼─────┐   ┌──────▼─────┐    ┌─────▼────┐   ┌────▼────┐
         │ AgentNode │   │   Edge     │    │   Run    │   │ Policy  │
         └─────┬─────┘   └────────────┘    └─────┬────┘   └────┬────┘
               │ N                               │ 1            │ 1
               │ 1                               │              │ N
         ┌─────▼─────┐                     ┌─────▼────┐   ┌────▼──────┐
         │ AgentRole │                     │ RunStep  │   │ PolicyRule│
         └─────┬─────┘                     └─────┬────┘   └───────────┘
               │ N                               │ 1
               │ 1                               │ N
         ┌─────▼─────┐                     ┌─────▼────┐
         │LLMProfile │                     │ ToolCall │◄──────┐
         └─────┬─────┘                     └─────┬────┘       │
               │ N                               │ 1          │ N
               │ 1                         ┌─────┴─────┐      │ 1
         ┌─────▼─────┐                     │           │   ┌──▼────┐
         │ Provider  │               ┌─────▼──┐  ┌─────▼─┐ │ Tool  │
         └───────────┘               │AuditLog│  │Journal│ └───────┘
                                     └────────┘  │ Entry │
                                                 └───────┘

         ┌──────────────────┐       ┌──────────────────┐
         │ConversationTurn  │──────▶│    Workflow      │
         └──────────────────┘       └──────────────────┘
                 │
                 └──────────▶ Run

         ┌──────────────────┐       ┌──────────────────┐
         │ ApprovalRequest  │◀──────│    RunStep       │
         └──────────────────┘       └──────────────────┘
```

---

## 5. Core Invariants (불변 규칙)

1. **모든 파괴적/민감 툴 콜은 Policy 검증을 경유**하며, 결과는 `AuditLog`에 반드시 기록된다.
2. **reversible=true 인 툴 콜은 실행 전 JournalEntry.before 를 기록**한다. 기록 실패 시 실행 중단.
3. **Run.workflow_snapshot** 은 실행 시점 YAML을 그대로 보관해 이후 워크플로우 수정이 있어도 재현 가능해야 한다.
4. **LLMProfile은 provider 삭제를 FK로 차단**한다 (ON DELETE RESTRICT).
5. **ApprovalRequest가 pending 인 동안 Run.status == `awaiting_approval`**.
6. **Policy.mode=strict 에서 매칭되는 rule 이 없으면 기본 `deny`**. `trusted` 는 기본 `allow`. `ask` 는 기본 `ask`.
7. **Tool.side_effect 는 쓰기일 때 dry_run 지원 필수** (plan 단계 미리보기).
8. **AuditLog 는 UPDATE/DELETE 금지**. 애플리케이션 레이어에서 append-only 보장.

---

## 6. Storage Layout

```
~/.orcaflow/
├── db.sqlite                      # 모든 엔티티의 정규화된 저장
├── config.toml                    # 앱 설정 (providers, policy mode 등)
├── workflows/
│   ├── templates/                 # WorkflowTemplate YAML
│   └── exports/                   # 사용자 export 출력
├── policies/
│   ├── default.yaml
│   └── strict.yaml
├── plugins/
│   └── <plugin-id>/
│       ├── plugin.yaml
│       └── src/
├── journal/
│   └── <run-id>/                  # 큰 before/after 스냅샷 저장
├── logs/
│   ├── audit.log                  # AuditLog append-only 미러 (JSONL)
│   └── app.log
└── cache/
```

**키/시크릿**: OS 키체인(Tauri keychain 플러그인) 사용. DB·설정 파일에는 `api_key_ref` (키체인 엔트리 ID)만 저장하고 원문은 저장하지 않는다.

---

## 7. Key Schemas (초기 정의)

### 7.1 Workflow YAML JSON Schema (요약)

```yaml
$schema: https://json-schema.org/draft/2020-12/schema
$id: orcaflow.workflow.v1
type: object
required: [version, name, nodes, edges, entrypoint]
properties:
  version: { const: 1 }
  name: { type: string, minLength: 1 }
  description: { type: string }
  author: { type: string }
  tags:
    type: array
    items: { type: string }
  policy: { type: string }
  default_llm_profile: { type: string }
  nodes:
    type: array
    items:
      type: object
      required: [id, role, position]
      properties:
        id: { type: string }
        role: { type: string }
        label: { type: string }
        position:
          type: object
          required: [x, y]
          properties:
            x: { type: integer }
            y: { type: integer }
        overrides: { type: object }
  edges:
    type: array
    items:
      type: object
      required: [from, to]
      properties:
        from: { type: string }
        to: { type: string }
        condition: { type: string }
        label: { type: string }
  entrypoint: { type: string }
```

### 7.2 Tool Manifest (플러그인 등록용)

```yaml
id: custom.my_tool
namespace: custom
name: my_tool
description: "설명 (LLM 함수 호출에 사용)"
input_schema:
  type: object
  properties:
    path: { type: string }
  required: [path]
permissions:
  - kind: fs_path
    scope: "~/Documents/**"
    action: read
side_effect: read
reversible: false
default_dry_run: false
entrypoint: "python:custom_plugin.tools.my_tool:run"
```

### 7.3 SQLite 주요 테이블 (요약)

```sql
-- 정책·감사·저널·런 관련 핵심 테이블
CREATE TABLE workflows (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  version INTEGER NOT NULL,
  yaml TEXT NOT NULL,       -- 원본 YAML 스냅샷
  policy_id TEXT REFERENCES policies(id),
  default_llm_profile_id TEXT REFERENCES llm_profiles(id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE agent_roles (
  id TEXT PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  role_type TEXT NOT NULL CHECK(role_type IN ('worker','planner','supervisor','critic')),
  system_prompt TEXT NOT NULL,
  tools_json TEXT NOT NULL,
  llm_profile_id TEXT NOT NULL REFERENCES llm_profiles(id) ON DELETE RESTRICT,
  max_steps INTEGER DEFAULT 10
);

CREATE TABLE providers (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  kind TEXT NOT NULL,
  base_url TEXT NOT NULL,
  api_key_ref TEXT,          -- 키체인 참조만 저장
  headers_json TEXT,
  timeout_ms INTEGER DEFAULT 30000
);

CREATE TABLE llm_profiles (
  id TEXT PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  provider_id TEXT NOT NULL REFERENCES providers(id) ON DELETE RESTRICT,
  model TEXT NOT NULL,
  params_json TEXT NOT NULL,
  is_tool_capable INTEGER NOT NULL DEFAULT 1,
  is_planner INTEGER NOT NULL DEFAULT 0,
  is_default INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE policies (
  id TEXT PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  mode TEXT NOT NULL CHECK(mode IN ('strict','ask','trusted')),
  yaml TEXT NOT NULL
);

CREATE TABLE policy_rules (
  id TEXT PRIMARY KEY,
  policy_id TEXT NOT NULL REFERENCES policies(id) ON DELETE CASCADE,
  priority INTEGER NOT NULL,
  scope TEXT NOT NULL,
  matcher TEXT NOT NULL,
  effect TEXT NOT NULL CHECK(effect IN ('allow','deny','ask','dry_run_only')),
  reason TEXT
);

CREATE TABLE runs (
  id TEXT PRIMARY KEY,
  workflow_id TEXT NOT NULL REFERENCES workflows(id),
  workflow_snapshot TEXT NOT NULL,
  trigger TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  stats_json TEXT,
  error_json TEXT,
  parent_run_id TEXT REFERENCES runs(id)
);

CREATE TABLE run_steps (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  parent_step_id TEXT REFERENCES run_steps(id),
  node_id TEXT,
  kind TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  result_json TEXT,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  duration_ms INTEGER,
  tokens_in INTEGER,
  tokens_out INTEGER
);

CREATE TABLE tool_calls (
  id TEXT PRIMARY KEY,
  run_step_id TEXT NOT NULL REFERENCES run_steps(id) ON DELETE CASCADE,
  tool_id TEXT NOT NULL,
  args_json TEXT NOT NULL,
  result_json TEXT,
  error_json TEXT,
  dry_run INTEGER NOT NULL DEFAULT 0,
  policy_decision TEXT NOT NULL,
  audit_log_id TEXT,
  duration_ms INTEGER
);

CREATE TABLE approval_requests (
  id TEXT PRIMARY KEY,
  run_step_id TEXT NOT NULL REFERENCES run_steps(id) ON DELETE CASCADE,
  tool_call_id TEXT REFERENCES tool_calls(id),
  reason TEXT NOT NULL,
  diff_preview_json TEXT,
  state TEXT NOT NULL,
  decided_at TEXT,
  decided_by TEXT,
  ttl_seconds INTEGER DEFAULT 300
);

CREATE TABLE audit_logs (
  id TEXT PRIMARY KEY,
  at TEXT NOT NULL,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  target TEXT NOT NULL,
  status TEXT NOT NULL,
  policy_decision TEXT NOT NULL,
  run_id TEXT NOT NULL,
  run_step_id TEXT NOT NULL,
  hash_prev TEXT,
  hash_self TEXT
);
-- 쓰기 경로는 오직 insert, 애플리케이션 레벨에서 UPDATE/DELETE 차단

CREATE TABLE journal_entries (
  id TEXT PRIMARY KEY,
  run_step_id TEXT NOT NULL REFERENCES run_steps(id) ON DELETE CASCADE,
  tool_call_id TEXT NOT NULL REFERENCES tool_calls(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,
  before_json TEXT,
  after_json TEXT,
  before_storage_ref TEXT,
  after_storage_ref TEXT,
  reversible INTEGER NOT NULL,
  restored_at TEXT,
  created_at TEXT NOT NULL
);
```

---

## 8. Validation Checklist

- [x] 핵심 엔티티 정의 (Workflow, AgentRole, AgentNode, Tool, LLMProfile, Provider, Policy, Run, RunStep, ToolCall, AuditLog, JournalEntry)
- [x] 용어 일관성 (glossary.md 와 1:1)
- [x] 엔티티 관계 명시
- [x] 보안/정책 관련 필드 포함 (policy_decision, audit_log_id, dry_run)
- [x] 되돌리기(JournalEntry)·감사(AuditLog) 분리
- [x] 플러그인/커스텀 툴 확장 지점 정의
- [x] YAML/JSON/SQLite 3층 구조 일관성
- [ ] 채팅 턴과 플래너 상태(ConversationTurn) 세부 필드 설계 검토 (Phase 2 대상)
- [ ] 멀티 세션/대화 컨텍스트 관리 상세화 (Design 단계)
- [ ] 플러그인 sandbox/격리 정책 (정책 엔진의 일부로 확장 예정)

---

## 9. Next Steps

1. 본 스키마 검토 및 승인
2. Phase 2 (Convention) — 네이밍/폴더/로깅 규칙 문서화, 본 엔티티명·필드명을 고정
3. `/pdca design OrcaFlow` — Tauri↔Python IPC, 정책 엔진 런타임, 플래너 파이프라인 상세 설계
4. 프로토타이핑 — 본 스키마에서 `Workflow`, `AgentRole`, `LLMProfile`, `Run`, `RunStep`, `ToolCall`, `AuditLog` 7개 테이블만으로 Ollama + 파일 툴 최소 실행 예제 만들기

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-04-12 | 초안 — 핵심 19개 엔티티, 용어·관계·DB 스키마·SQL·JSON Schema 포함 | 2z |
| 1.1 | 2026-04-12 | JournalEntry `storage_ref` 를 `before_storage_ref`/`after_storage_ref` 로 분리 (M2 리뷰 H1 수정) | 2z |
