---
name: OrcaFlow 프로젝트 개요
description: OrcaFlow의 정체성, 핵심 원칙, 타깃 사용자, v0.1 범위 요약
type: project
---

# OrcaFlow - 네이티브 멀티 에이전트 오케스트레이션 플랫폼

오픈 LLM 기반 멀티 에이전트 오케스트레이션 플랫폼. 사용자가 채팅형 자연어 + 노드 에디터 UI로 에이전트 협업 워크플로우를 구성하고, 에이전트가 사용자 PC의 파일·앱·OS·브라우저에 직접 접근해 실제 업무를 수행하도록 한다.

**Why (프로젝트 동기):**
- 2026-04-12 신규 프로젝트로 시작. 사용자가 직접 명명·스택 결정.
- 기존 LangGraph/AutoGen은 코드 진입장벽이 높고, ComfyUI/n8n은 LLM 에이전트 특화가 아니며, 상용 LLM 플랫폼은 락인·로컬 접근 부재 문제가 있다.
- 사용자 요구: "사용자가 원하는 방식으로 명령을 내리고, 에이전트가 PC에서 실제 업무를 수행해야 한다." (= 격리 환경 금지)

**How to apply (판단 가이드):**
- **아키텍처 결정의 제1원칙**: "에이전트가 로컬 리소스에 직접 접근할 수 있는가?" 이 질문을 통과 못 하면 후보에서 탈락.
- **기본 스택 (Plan v0.2)**: Tauri(Rust shell) + Vite+React UI + Python FastAPI sidecar + LangGraph 경량 래퍼 + SQLite (`~/.orcaflow/`) + React Flow 노드 에디터 + shadcn/ui.
- **LLM 전략**: OpenAI 호환 인터페이스를 기본으로 Ollama/vLLM/llama.cpp/LM Studio/Together/Groq/Fireworks 등 오픈 모델 중심. 상용 LLM은 v0.1 Out of Scope(플러그인으로 후속).
- **v0.1 MVP DoD**: 로컬 폴더 정리, 코드베이스 읽고 리팩토링 PR 준비, 브라우저 자동 탐색+요약 — 이 3종이 실제로 동작해야 한다.
- **보안 기본선**: 파괴적 작업은 정책 엔진 → 사용자 승인 → 저널링 → 감사 로그 순서로 처리. Dry-run 기본.
- 문서 위치: `docs/01-plan/features/OrcaFlow.plan.md` (v0.2 현재). Phase 진행은 bkit PDCA 스킬 사용.
