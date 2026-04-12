---
name: OrcaFlow - Docker/컨테이너 격리 금지
description: OrcaFlow는 사용자 PC에 직접 접근해 업무를 수행하는 네이티브 에이전트이므로 Docker/컨테이너/가상화 격리를 제안하거나 채택하지 말 것
type: feedback
---

# Docker/컨테이너 격리 금지

OrcaFlow 아키텍처·배포·실행 제안에서 Docker, docker-compose, 컨테이너, VM 격리 기반 실행 방식을 제안하지 말 것. 네이티브(Tauri + Python sidecar, 또는 그에 준하는 OS 네이티브 실행) 방식을 기본으로 전제한다.

**Why:**
- OrcaFlow의 정체성은 "사용자 PC에 직접 접근해서 실제 업무를 수행하는 진짜 에이전트"다.
- 컨테이너/가상화 환경에서는 호스트 파일시스템·네트워크·앱·IDE·브라우저 프로필·OS API 접근이 차단되거나 우회가 필요해진다. 이는 에이전트의 효용 자체를 무력화한다.
- 사용자가 2026-04-12 Plan 리뷰에서 명시적으로 "도커 안에 들어가면 독립적인 서버라 로컬에 접근할 수 없다"고 지적하며 전체 아키텍처를 네이티브로 전환했다.

**How to apply:**
- 배포/패키징 제안 시: Tauri bundler(dmg/msi/AppImage), PyInstaller, 단일 바이너리, OS 네이티브 인스톨러만 제안한다. `docker`, `compose`, `Dockerfile`, `kubernetes`, `helm` 등은 OrcaFlow 맥락에서 제안 금지.
- 보안/샌드박스를 고민할 때는 컨테이너 격리 대신 **정책 엔진(경로/명령 화이트리스트) + 사용자 승인(HITL) + Dry-run + 감사 로그 + OS 권한 프롬프트(Tauri permission API, macOS TCC 등)** 조합으로 해결한다.
- 개발 환경 재현성은 `pyproject.toml`, `package.json`, `asdf`/`mise`, 또는 `devenv`/`nix` 같은 네이티브 재현 도구로 해결한다.
- 단, 사용자 워크플로우의 "결과물"이 Docker 이미지를 빌드·배포해야 하는 경우(= 에이전트가 툴로 docker 명령을 호출하는 것)는 예외로 허용한다. 금지되는 것은 "OrcaFlow 자체를 Docker로 실행"하는 것이다.
