# OrcaFlow Conventions (Summary)

본 파일은 요약본이다. 전체 규약은 [`docs/01-plan/conventions.md`](./docs/01-plan/conventions.md) 를 참조한다.

## 핵심 원칙

1. **폴리글랏 규약**: Rust는 snake_case, Python은 snake_case (Pydantic v2), TypeScript 컴포넌트는 PascalCase · 훅/유틸은 kebab-case 파일명.
2. **경계 케이싱**: YAML·SQLite·JSON 페이로드는 snake_case. 프론트엔드 `lib/api/` 어댑터에서 camelCase로 1회 변환.
3. **Tool ID 포맷**: `<namespace>.<verb>_<noun>` (예: `fs.read_file`, `os.applescript`). namespace는 `fs|shell|browser|os|web|custom` 고정 enum.
4. **의존 방향**: Presentation → App Shell → Application → Domain ← Infrastructure. Domain(`schema`, `policy`, `audit`, `journal`)은 순수하게 유지.
5. **Config**: `.env`가 아니라 `~/.orcaflow/config.toml` + OS 키체인. 시크릿을 환경변수에 저장 금지.
6. **파괴적 작업 7단계**: dry_run 계획 → Policy 검증 → Approval → Journal.before → 실행 → AuditLog → (실패 시) 복구. 이 순서 우회 불가.
7. **로그**: JSON 구조화(JSONL). 이벤트 코드는 `<domain>.<action>.<result>`. PII/시크릿 로깅 절대 금지.
8. **테스트**: Domain/Policy/Audit/Journal 커버리지 80% 이상, 실제 LLM 호출 금지(FakeProvider).
9. **Docker 금지**: OrcaFlow 자체를 컨테이너로 실행 금지. 에이전트가 도구로 `docker` 명령을 호출하는 것은 허용.
10. **용어 SSoT**: [`docs/01-plan/glossary.md`](./docs/01-plan/glossary.md) 와 [`docs/01-plan/schema.md`](./docs/01-plan/schema.md) 가 단일 출처.

## 포맷터 / 린터 (필수)

| 언어 | 포맷터 | 린터 | 타입 체크 |
|------|--------|------|-----------|
| Rust | rustfmt | clippy (deny warnings) | cargo check |
| Python | ruff format | ruff check | mypy (schema/policy/audit strict) |
| TypeScript | prettier (semi: false, single quotes) | eslint + boundaries | tsc --noEmit |

## 브랜치 / 커밋

- Conventional Commits. scope는 도메인: `workflow|agent|tool|llm|provider|policy|audit|journal|ui|ipc|sidecar|shell|build|docs`
- 브랜치: `feat/`, `fix/`, `refactor/`, `docs/`, `chore/`, `spike/`
