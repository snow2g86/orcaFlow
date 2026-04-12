"""Sidecar 설정 로딩.

우선순위 (conventions.md §5.1):
    1. CLI / 환경변수 (`ORCA_*`)
    2. `~/.orcaflow/config.toml`
    3. 내장 기본값

M1 범위: 앱 전역 + sidecar 바인딩 + 로그 레벨만. providers/policy/db 세부는
이후 마일스톤에서 확장한다.
"""

from __future__ import annotations

from pathlib import Path
import tomllib
from typing import Any, Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .errors import ConfigError

DEFAULT_WORKSPACE = Path.home() / ".orcaflow"
DEFAULT_CONFIG_FILE = DEFAULT_WORKSPACE / "config.toml"


class AppSection(BaseModel):
    log_level: Literal["trace", "debug", "info", "warn", "error"] = "info"
    telemetry: bool = False


class SidecarSection(BaseModel):
    host: str = "127.0.0.1"
    port: int = 0  # 0 = OS 자동 할당


class DbSection(BaseModel):
    path: Path = Field(default_factory=lambda: DEFAULT_WORKSPACE / "db.sqlite")


class Config(BaseModel):
    """런타임 설정 스냅샷 (sidecar 가 노출하는 읽기 전용 뷰)."""

    app: AppSection = Field(default_factory=AppSection)
    sidecar: SidecarSection = Field(default_factory=SidecarSection)
    db: DbSection = Field(default_factory=DbSection)
    workspace: Path = Field(default=DEFAULT_WORKSPACE)

    def public_dict(self) -> dict[str, Any]:
        """사용자에게 노출 가능한 필드만 담은 dict (시크릿 제거 레이어 준비)."""
        return {
            "app": self.app.model_dump(),
            "sidecar": self.sidecar.model_dump(),
            "db": {"path": str(self.db.path)},
            "workspace": str(self.workspace),
        }


class Settings(BaseSettings):
    """CLI/환경변수 → config 오버라이드 브리지."""

    model_config = SettingsConfigDict(
        env_prefix="ORCA_",
        env_file=None,
        extra="ignore",
    )

    workspace: Path = Field(default=DEFAULT_WORKSPACE)
    config_file: Path | None = None
    log_level: Literal["trace", "debug", "info", "warn", "error"] | None = None
    sidecar_host: str | None = None
    sidecar_port: int | None = None

    def load(self) -> Config:
        """파일 + 오버라이드를 합쳐 Config 를 생성한다."""
        path = self.config_file or (self.workspace / "config.toml")
        data: dict[str, Any] = {}
        if path.exists():
            try:
                with path.open("rb") as fp:
                    data = tomllib.load(fp)
            except (OSError, tomllib.TOMLDecodeError) as exc:
                raise ConfigError(
                    f"설정 파일을 읽을 수 없습니다: {path}",
                    details={"path": str(path), "cause": str(exc)},
                ) from exc

        app = AppSection(**data.get("app", {}))
        sidecar = SidecarSection(**data.get("sidecar", {}))
        db = DbSection(**data.get("db", {}))

        if self.log_level is not None:
            app = app.model_copy(update={"log_level": self.log_level})
        if self.sidecar_host is not None:
            sidecar = sidecar.model_copy(update={"host": self.sidecar_host})
        if self.sidecar_port is not None:
            sidecar = sidecar.model_copy(update={"port": self.sidecar_port})

        # 외부 바인딩 차단 (conventions.md §8.4)
        if sidecar.host not in {"127.0.0.1", "localhost", "::1"}:
            raise ConfigError(
                "sidecar.host 는 로컬 루프백만 허용됩니다",
                details={"host": sidecar.host},
            )

        workspace = self.workspace
        workspace.mkdir(parents=True, exist_ok=True)

        return Config(app=app, sidecar=sidecar, db=db, workspace=workspace)


def load_config(settings: Settings | None = None) -> Config:
    return (settings or Settings()).load()
