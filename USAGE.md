# OrcaFlow 사용 가이드

## 목차

1. [설치 및 실행](#1-설치-및-실행)
2. [Provider 설정](#2-provider-설정)
3. [LLM Profile 생성](#3-llm-profile-생성)
4. [채팅](#4-채팅)
5. [워크플로우 편집 및 실행](#5-워크플로우-편집-및-실행)
6. [정책 관리](#6-정책-관리)
7. [문제 해결](#7-문제-해결)

---

## 1. 설치 및 실행

### 사전 요구 사항

| 도구 | 최소 버전 | 설치 확인 |
|------|----------|-----------|
| Rust | 1.79+ | `rustc --version` |
| Tauri CLI | v2 | `cargo tauri --version` |
| Node.js | 20+ | `node --version` |
| pnpm | 9+ | `pnpm --version` |
| Python | 3.11+ | `python3 --version` |
| uv | latest | `uv --version` |

Tauri CLI 미설치 시:
```bash
cargo install tauri-cli --version '^2' --locked
```

### LLM 서버 준비

OrcaFlow는 로컬 또는 클라우드 LLM이 필요합니다. 가장 쉬운 방법은 **Ollama**:

```bash
# Ollama 설치 (macOS)
brew install ollama

# 모델 다운로드
ollama pull gemma4:26b    # 또는 원하는 모델

# Ollama 서버 실행
ollama serve
```

### 앱 실행

```bash
cd OrcaFlow
./scripts/dev.sh
```

앱 창이 열리면 상단 상태바에 **Ready** 배지가 표시되어야 합니다.

---

## 2. Provider 설정

Provider는 LLM 서버 연결 정보입니다. 앱 상단의 **Settings** 탭으로 이동합니다.

### Provider 추가

1. **Add Provider** 카드에서 정보를 입력합니다:
   - **Name**: 식별용 이름 (예: `My Ollama`)
   - **Kind**: 서버 종류 선택
     - `Ollama` — 로컬 Ollama 서버
     - `LM Studio` — LM Studio 앱
     - `vLLM` / `llama.cpp` / `TGI` — 기타 로컬 서버
     - `OpenAI Compatible` — OpenAI API 호환 서버
     - `Together` / `Groq` / `Fireworks` — 클라우드 API
   - **Base URL**: 서버 주소 (Kind 선택 시 기본값 자동 입력)
   - **API Key**: 클라우드 서비스 사용 시 입력 (로컬 서버는 비워둠)

2. **Add Provider** 버튼 클릭

3. Providers 목록에 추가되면 **Test** 버튼으로 연결을 확인합니다:
   - `ok` — 정상 연결, 사용 가능한 모델 수가 표시됨
   - `fail` — 연결 실패 (서버가 실행 중인지 확인)

### Provider 삭제

목록 우측의 **x** 버튼으로 삭제합니다. 연결된 LLM Profile이 있으면 삭제할 수 없습니다 — Profile을 먼저 삭제하세요.

---

## 3. LLM Profile 생성

LLM Profile은 "어떤 Provider의 어떤 모델을 어떤 파라미터로 사용할 것인가"를 정의합니다.

### Profile 생성

1. **Create LLM Profile** 카드에서:
   - **Profile Name**: 식별용 이름 (예: `gemma4-26b-creative`)
   - **Provider**: 드롭다운에서 선택 — 선택 즉시 해당 서버의 모델 목록을 자동으로 가져옵니다
   - **Model**: 드롭다운에서 선택 (자동으로 불러온 모델 목록) 또는 직접 입력
   - **Temperature**: 생성 다양성 (`0.0` = 결정적, `1.0` = 창의적, 기본 `0.7`)
   - **Max Tokens**: 최대 출력 토큰 수 (기본 `4096`)
   - **Planner**: 워크플로우 Planner 용으로 지정
   - **Default**: 기본 프로필로 지정

2. **Create Profile** 버튼 클릭

3. LLM Profiles 테이블에 추가됩니다

### 권장 설정

| 용도 | Temperature | Max Tokens | Planner | Default |
|------|------------|------------|---------|---------|
| 일반 대화 | 0.7 | 4096 | - | O |
| 코드 생성 | 0.2 | 8192 | - | - |
| 워크플로우 계획 | 0.3 | 4096 | O | - |
| 창의적 작문 | 1.0 | 4096 | - | - |

> 모든 설정은 SQLite에 저장되어 앱 재시작 후에도 유지됩니다.

---

## 4. 채팅

상단의 **Chat** 탭에서 LLM과 직접 대화합니다.

- Default로 지정된 LLM Profile이 자동 선택됩니다
- Planner 프로필이 있으면 다단계 작업을 계획하고 실행합니다
- 에이전트가 툴을 사용할 때 **승인 요청**이 표시될 수 있습니다

---

## 5. 워크플로우 편집 및 실행

### 워크플로우란?

여러 에이전트가 협력하는 작업 흐름입니다. 각 노드는 에이전트 역할(Role)을 가지며, 연결선이 실행 순서를 결정합니다.

### Editor 탭

- 노드 추가: 우클릭 → Add Node
- 노드 연결: 출력 포트 → 입력 포트 드래그
- 노드 설정: 노드 클릭 → 우측 인스펙터에서 Role, LLM Profile 지정

### 워크플로우 실행

1. Editor에서 워크플로우 작성 또는 YAML 로드
2. **Run** 버튼 클릭
3. **Monitor** 탭에서 실행 상태 확인
   - 각 단계별 진행 상황
   - 에이전트의 도구 호출 내역
   - 승인 필요 시 알림

### 샘플 워크플로우

`shared/fixtures/workflows/` 에 5종의 예제가 포함되어 있습니다:

| 이름 | 구성 | 설명 |
|------|------|------|
| `simple-chat.yaml` | Planner 1개 | 단순 대화 |
| `file-organizer.yaml` | Planner + Worker | 파일 자동 정리 |
| `code-reviewer.yaml` | Planner + Reviewer + Summarizer | 코드 리뷰 |
| `web-researcher.yaml` | Planner + Researcher + Summarizer | 웹 리서치 |
| `multi-agent-debate.yaml` | Supervisor + Worker 2개 | 다중 관점 토론 |

---

## 6. 정책 관리

**Policy** 탭에서 에이전트의 도구 사용 규칙을 관리합니다.

### 정책 모드

| 모드 | 동작 |
|------|------|
| `auto` | 모든 도구 호출 자동 허용 (주의 필요) |
| `ask` | 규칙에 따라 허용/승인/차단 판단 |
| `strict` | 명시적 허용 외 모두 승인 필요 |

### 규칙 예시

```
fs.read_file → allow      # 파일 읽기는 자동 허용
fs.write_file → ask        # 파일 쓰기는 승인 필요
shell.exec → deny          # 쉘 실행은 차단
```

### 승인 처리

에이전트가 승인 필요한 작업을 요청하면:
1. 상단 바에 승인 알림이 표시됩니다
2. 요청 내용을 확인하고 **Approve** 또는 **Reject** 선택
3. 모든 승인/거부 기록은 감사 로그에 남습니다

---

## 7. 문제 해결

### 앱이 시작되지 않음

```bash
# Tauri CLI 설치 확인
cargo tauri --version

# 수동 실행으로 에러 확인
cd sidecar && uv sync
cd frontend && pnpm install
cd app/src-tauri && ORCA_DEV=1 cargo tauri dev
```

### Sidecar "Failed" 상태

- Python 3.11+ 설치 확인: `python3 --version`
- uv 설치 확인: `uv --version`
- 의존성 동기화: `cd sidecar && uv sync`

### Provider 연결 실패 (Health: fail)

- LLM 서버가 실행 중인지 확인 (예: `ollama serve`)
- Base URL이 올바른지 확인 (기본: `http://127.0.0.1:11434`)
- 클라우드 API의 경우 API Key가 올바른지 확인

### 모델 목록이 비어 있음

- Provider의 Health가 `ok`인지 먼저 확인
- Ollama의 경우 최소 하나의 모델이 설치되어 있어야 함: `ollama list`
- 모델 설치: `ollama pull <model-name>`

### DB 초기화 (설정 완전 리셋)

```bash
rm ~/.orcaflow/db.sqlite
# 앱 재시작 시 빈 DB가 자동 생성됩니다
```

---

## 지원되는 LLM Provider

| Provider | Kind | 기본 URL | API Key |
|----------|------|----------|---------|
| Ollama | `ollama` | `http://127.0.0.1:11434` | 불필요 |
| LM Studio | `lm_studio` | `http://127.0.0.1:1234` | 불필요 |
| vLLM | `vllm` | `http://127.0.0.1:8000` | 불필요 |
| llama.cpp | `llama_cpp` | `http://127.0.0.1:8080` | 불필요 |
| TGI | `tgi` | `http://127.0.0.1:8080` | 불필요 |
| Together AI | `together` | `https://api.together.xyz` | 필요 |
| Groq | `groq` | `https://api.groq.com` | 필요 |
| Fireworks | `fireworks` | `https://api.fireworks.ai` | 필요 |
| 기타 OpenAI 호환 | `openai_compatible` | (서버에 따라 다름) | 선택 |
