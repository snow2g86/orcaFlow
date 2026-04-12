# OrcaFlow Glossary

> Phase 1 Deliverable — 프로젝트 전반에서 사용되는 용어 정의
>
> **Project**: OrcaFlow
> **Date**: 2026-04-12
> **Version**: 1.0

OrcaFlow는 "오픈 LLM 기반으로 사용자 PC에 직접 접근해 업무를 수행하는 멀티 에이전트 오케스트레이션 플랫폼"이다. 따라서 용어는 (1) 오케스트레이션·그래프, (2) 에이전트·툴, (3) 권한·감사, (4) LLM 공급자 영역으로 나뉜다.

---

## 1. Business Terms (OrcaFlow 고유 용어)

| Term | English | Definition | Global Standard Mapping |
|------|---------|------------|------------------------|
| 오르카 | Orca | OrcaFlow의 마스코트 겸 최상위 개념. 여러 에이전트(무리, pod)를 이끄는 지휘자 은유 | - |
| 플로우 | Flow / Workflow | 한 개 이상의 에이전트 노드와 엣지로 구성된 실행 가능한 그래프 | DAG, Pipeline, Workflow |
| 포드 | Pod | 동일 목적을 공유하는 에이전트 묶음 (Flow 내 논리적 그룹) | Agent Group, Team |
| 에이전트 노드 | Agent Node | Flow 그래프에 배치된 에이전트 인스턴스 (위치·설정 override 포함) | Graph Node |
| 에이전트 역할 | Agent Role | 시스템 프롬프트·툴·LLM 프로파일·목표가 정의된 재사용 가능한 역할 템플릿 | Agent Persona, Role |
| 플래너 | Planner | 사용자 자연어 지시를 해석해 Flow를 자동 생성하는 메타 에이전트 | Planning Agent |
| 수퍼바이저 | Supervisor | 하위 에이전트들의 작업을 감독·라우팅하는 상위 에이전트 | Orchestrator Agent |
| 런 | Run | 한 번의 Flow 실행 인스턴스 (시작시각·종료시각·상태 포함) | Execution, Invocation |
| 런 스텝 | Run Step | Run 내 단일 단계 (LLM 호출, 툴 호출, 라우팅 결정 등) | Step, Span |
| 툴 콜 | Tool Call | 에이전트가 특정 툴을 호출한 단위 기록 | Function Call, Action |
| LLM 프로파일 | LLM Profile | 공급자·모델·파라미터·엔드포인트를 묶은 재사용 설정 | Model Config |
| 프로바이더 | Provider | LLM 공급자 (Ollama, vLLM, llama.cpp, LM Studio, Together, Groq 등) | LLM Provider |
| 정책 | Policy | 에이전트/툴 호출에 대한 허용·차단·승인 규칙 집합 | Authorization Policy |
| 정책 룰 | Policy Rule | Policy를 구성하는 개별 규칙 (경로/명령/네트워크 범위 등) | ACL Rule |
| 승인 요청 | Approval Request | 사용자에게 민감 작업 승인을 요청하는 HITL 단위 | Human-in-the-Loop (HITL) |
| 감사 로그 | Audit Log | 파괴적·민감 작업의 사후 추적을 위한 불변 로그 | Audit Trail |
| 저널 | Journal | 파일 변경·쉘 실행 등 되돌리기 가능한 변경 이력 | Changelog, Undo Log |
| 드라이런 | Dry Run | 실제 실행 없이 결과를 시뮬레이션하는 모드 | Dry Run, Plan Mode |
| 사이드카 | Sidecar | Tauri 앱이 구동하는 Python 실행 엔진 프로세스 | Sidecar Process |
| 브리지 | Bridge (IPC) | Tauri(Rust) ↔ Python 사이드카 간 호출/이벤트 채널 | IPC Bridge |

---

## 2. Global Standards (업계/기술 표준)

| Term | Definition | Reference |
|------|------------|-----------|
| LLM | Large Language Model | - |
| Multi-Agent System | 여러 에이전트가 협업하는 AI 시스템 | - |
| ReAct | Reasoning + Acting 에이전트 패턴 | Yao et al., 2022 |
| Tool Use / Function Calling | LLM이 외부 함수를 호출하는 메커니즘 | OpenAI Function Calling, Anthropic Tool Use |
| DAG | Directed Acyclic Graph | - |
| IPC | Inter-Process Communication | - |
| SSE | Server-Sent Events | W3C |
| UUID (v7) | 시간 순 정렬 가능한 UUID | RFC 9562 |
| YAML | 워크플로우 직렬화 포맷 | yaml.org |
| JSON Schema | 구조 검증 스키마 | json-schema.org |
| OpenAI-compatible API | Chat Completions 엔드포인트 호환 인터페이스 | - |
| HITL | Human-in-the-Loop 승인 플로우 | - |
| RBAC / ABAC | 권한 부여 모델 | NIST |
| Audit Log | 보안 감사 기록 | NIST SP 800-92 |
| MCP | Model Context Protocol (외부 툴/리소스 통합 표준) | Anthropic 2024 |
| TCC | macOS Transparency, Consent, and Control (권한 프롬프트) | Apple |

---

## 3. Business ↔ Global Mapping

| Business Term | Code Identifier | API/Storage Field | UI Label (ko) |
|---------------|------------------|--------------------|----------------|
| 플로우 | `Workflow` | `workflow` | 플로우 |
| 에이전트 역할 | `AgentRole` | `agent_role` | 에이전트 역할 |
| 에이전트 노드 | `AgentNode` | `agent_node` | 에이전트 노드 |
| 플래너 | `Planner` (AgentRole 특수 유형) | `role_type: "planner"` | 플래너 |
| 수퍼바이저 | `Supervisor` (AgentRole 특수 유형) | `role_type: "supervisor"` | 수퍼바이저 |
| 런 | `Run` | `run` | 실행 |
| 런 스텝 | `RunStep` | `run_step` | 단계 |
| 툴 콜 | `ToolCall` | `tool_call` | 툴 호출 |
| LLM 프로파일 | `LLMProfile` | `llm_profile` | LLM 프로파일 |
| 프로바이더 | `Provider` | `provider` | 공급자 |
| 정책 | `Policy` | `policy` | 정책 |
| 정책 룰 | `PolicyRule` | `policy_rule` | 정책 룰 |
| 승인 요청 | `ApprovalRequest` | `approval_request` | 승인 요청 |
| 감사 로그 | `AuditLog` | `audit_log` | 감사 로그 |
| 저널 | `JournalEntry` | `journal_entry` | 변경 저널 |

---

## 4. Term Usage Rules

1. **코드(TypeScript/Python/Rust)**: `PascalCase` 영문 고정 (`Workflow`, `AgentRole`, `ToolCall`).
2. **YAML 워크플로우 파일**: `snake_case` (`agent_nodes`, `llm_profile`, `policy_rule`).
3. **DB 컬럼**: `snake_case`.
4. **REST/IPC API**: `snake_case` JSON 필드.
5. **UI/문서(한글)**: 본 용어집의 "UI Label" 열을 사용.
6. **정책·감사 관련 용어**: 반드시 본 용어집과 일치해야 함 (보안 일관성).
7. **"도커/컨테이너/샌드박스" 용어**: OrcaFlow 자체 실행 방식 맥락에서 사용 금지. 에이전트가 툴로 `docker` 명령을 호출하는 경우에만 외부 참조로 허용.

---

## 5. Claude Code / AI 참조 규약

- `CLAUDE.md` 에 본 파일 위치를 명시: *"OrcaFlow 용어는 `docs/01-plan/glossary.md`를 우선 참조한다."*
- 새 비즈니스 용어를 도입할 때는 반드시 본 파일에 먼저 등록 후 사용한다.
- 용어 변경은 PR 설명란에 "glossary 변경 포함" 명시.
