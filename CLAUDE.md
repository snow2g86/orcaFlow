# CLAUDE.md — OrcaFlow AI Collaboration Guide

이 파일은 Claude Code 및 다른 AI 협업자를 위한 프로젝트 가이드다. OrcaFlow 코드/문서 작업 전에 반드시 아래 문서를 먼저 참조한다.

## 프로젝트 정체성

OrcaFlow는 **오픈 LLM 기반 멀티 에이전트 오케스트레이션 플랫폼**으로, **사용자 PC에 직접 접근해 실제 업무를 수행하는 네이티브 에이전트**를 제공한다. Tauri(Rust 셸) + Python FastAPI sidecar + Vite+React 프론트엔드 구조의 단일 사용자 로컬 데스크톱 앱이다.

**절대 원칙**: Docker/컨테이너/VM 격리로 OrcaFlow 자체를 실행하지 않는다. 격리는 에이전트의 로컬 접근을 막아 제품 정체성을 훼손한다. (에이전트가 툴로 `docker` 명령을 호출하는 것은 별개로 허용.)

## 우선 참조 문서

| 목적 | 문서 |
|------|------|
| 프로젝트 계획·원칙·아키텍처 | [`docs/01-plan/features/OrcaFlow.plan.md`](./docs/01-plan/features/OrcaFlow.plan.md) |
| 용어 정의 (SSoT) | [`docs/01-plan/glossary.md`](./docs/01-plan/glossary.md) |
| 엔티티·DB·YAML 스키마 (SSoT) | [`docs/01-plan/schema.md`](./docs/01-plan/schema.md) |
| 코딩 규약 (언어별) | [`docs/01-plan/conventions.md`](./docs/01-plan/conventions.md) |
| 요약 규약 | [`CONVENTIONS.md`](./CONVENTIONS.md) |
| 프로젝트 메모리 | [`.bkit-memory/MEMORY.md`](./.bkit-memory/MEMORY.md) |

## 프로젝트 구조 (M8 완성)

```
OrcaFlow/
├── app/src-tauri/              # Tauri 데스크톱 셸 (Rust)
│   ├── src/
│   │   ├── main.rs             # 앱 진입점, sidecar 기동 (dev/prod 분기)
│   │   ├── bridge/             # SidecarBridge, SidecarClient
│   │   ├── commands/           # Tauri IPC 커맨드
│   │   ├── config/             # AppState, 경로 관리
│   │   └── errors.rs
│   ├── tauri.conf.json         # Tauri 빌드 설정 (externalBin 포함)
│   └── Cargo.toml
├── frontend/                   # Vite + React UI
│   ├── src/
│   │   ├── components/         # Chat, Monitor, Approval, Editor, PolicyManager, Settings
│   │   ├── lib/api/            # Tauri IPC 래퍼 (invoke/listen 경유)
│   │   └── stores/             # Zustand 상태 관리
│   └── package.json
├── sidecar/                    # Python FastAPI + orca_core
│   ├── orca_core/
│   │   ├── schema/             # Domain: 엔티티 정의
│   │   ├── policy/             # Domain: 정책 엔진
│   │   ├── audit/              # Domain: 감사 로그
│   │   ├── journal/            # Domain: 변경 저널
│   │   ├── tools/              # Infrastructure: 내장 툴 17종 (fs/shell/browser/os/web)
│   │   ├── providers/          # Infrastructure: LLM 어댑터
│   │   ├── persistence/        # Infrastructure: SQLite
│   │   ├── orchestrator/       # Application: GraphRunner + Planner
│   │   ├── ipc/                # Presentation: FastAPI 라우트 + SSE
│   │   ├── config.py           # Settings
│   │   └── __main__.py         # Sidecar 진입점 (handshake → uvicorn)
│   ├── pyproject.toml
│   └── orca-sidecar.spec       # PyInstaller 재현성 spec
├── shared/fixtures/            # 샘플 워크플로우(5종), 정책(3종), 역할(4종)
├── scripts/
│   ├── dev.sh                  # 개발 서버 기동
│   ├── bundle-sidecar.sh       # PyInstaller 번들링
│   ├── release.sh              # 릴리스 빌드 (전체 파이프라인)
│   ├── clean.sh                # 빌드 아티팩트 정리
│   └── install-deps.sh         # 사전 요구 설치 도우미
├── .github/workflows/ci.yml   # GitHub Actions CI (3 OS matrix)
├── docs/
│   ├── 01-plan/                # Plan, glossary, schema, conventions
│   └── 02-design/              # Design, Do guide
├── CLAUDE.md                   # (이 파일)
├── CONVENTIONS.md              # 요약 코딩 규약
└── README.md                   # 프로젝트 소개 + 사용법
```

## 빌드 명령

```bash
# 개발 모드
./scripts/dev.sh                     # 또는 ORCA_DEV=1 cargo tauri dev

# 릴리스 빌드
./scripts/release.sh                 # sidecar 번들 → frontend 빌드 → Tauri 패키징

# 테스트
cd sidecar && uv run pytest          # Python 345 tests, 88.37% coverage
cd frontend && pnpm test             # Frontend 62 tests
cd app/src-tauri && cargo check      # Rust 타입 체크

# 정리
./scripts/clean.sh                   # 빌드 아티팩트만
./scripts/clean.sh --all             # target, node_modules 포함 전체
```

## 작업 규칙

1. **용어 사용**: 비즈니스 용어는 `glossary.md`에 없으면 먼저 등록한 후 사용한다.
2. **엔티티 필드**: `schema.md` S3 정의와 필드명/타입이 일치해야 한다. 변경 시 schema.md 먼저 수정.
3. **네이밍 경계**: YAML/DB/JSON 페이로드는 snake_case. 프론트엔드 내부는 camelCase. 변환은 `frontend/src/lib/api/` 에서만.
4. **의존 방향**: Domain(`schema`, `policy`, `audit`, `journal`) 은 외부 I/O 의존 금지. Presentation은 Infrastructure 직접 호출 금지.
5. **파괴적 툴 호출**: 항상 `dry_run -> policy.check -> approval -> journal.before -> run -> audit.record` 순서. 이 플로우를 건너뛰는 코드는 머지 금지.
6. **시크릿**: API 키/토큰은 OS 키체인만 사용. `config.toml`, 코드, 로그, Pydantic dump에 평문 저장 금지.
7. **로그**: JSONL 구조화. 이벤트 코드는 `<domain>.<action>.<result>`. `tool_call.started`, `policy.denied`, `run.succeeded` 등.
8. **테스트 시 LLM 호출**: 실제 모델 호출 금지. `FakeProviderAdapter` 사용.
9. **sidecar 바인딩**: 반드시 `127.0.0.1`. 외부 바인딩 금지.
10. **PDCA**: 새 기능은 bkit `/pdca` 스킬 흐름을 따른다. Plan -> Design -> Do -> Check -> Act.
11. **pyproject.toml 수정 금지**: PyInstaller 등 빌드 전용 의존성은 scripts/ 에서 임시 설치.
12. **sidecar dev/prod 분기**: `ORCA_DEV` 환경변수 유무로 판단. dev = `uv run python -m orca_core`, prod = 번들된 `orca-sidecar` 바이너리.

## 금지 제안 목록 (OrcaFlow 맥락)

- Docker / docker-compose / Kubernetes로 OrcaFlow 실행
- 샌드박스 격리를 "네이티브 접근 불가능한 형태"로 도입
- 시크릿을 `.env` / 코드 / 로그 / DB 평문 저장
- Domain 레이어에서 `requests`, `sqlite3`, `subprocess` 등 외부 I/O 직접 사용
- 파괴적 툴 호출에서 Policy / Approval / Journal / Audit 우회
- `tools/<namespace>/` 간 횡단 import
- Frontend 컴포넌트에서 `invoke`/`listen` 직접 호출 (반드시 `lib/api/` 경유)

## 언어/톤

- 사용자 대화는 한국어 기본. 기술 식별자/코드는 원문 유지.
- 문서는 명확/간결 우선. 불필요한 장식 금지.
