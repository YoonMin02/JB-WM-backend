"""애플리케이션 설정. .env에서 로드 (pydantic-settings)."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Core
    app_env: Literal["local", "dev", "staging", "prod"] = "local"
    app_name: str = "jb-wm-backend"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    log_level: str = "info"

    # Database
    database_url: str = "postgresql://jbwm:jbwm@localhost:5432/jbwm_dev"

    # Auth
    jwt_secret: str = "change-me"

    # Codex / 추론
    # 'stub' = 결정론적 가짜(테스트/데모), 'codex' = 실제 Codex SDK
    reasoner: Literal["stub", "codex"] = "stub"
    openai_api_key: str | None = None
    codex_working_directory: str = "./workspace"
    codex_model: str = "gpt-5.4"  # 사용 가능: gpt-5.5/5.4/5.4-mini/5.3-codex/5.2
    # 호출 횟수 가드 (쿼터 보호 — 넉넉하게). 0 = 무제한
    codex_max_calls_per_minute: int = 30
    codex_max_calls_total: int = 500

    # Storage
    file_storage_driver: str = "local"
    local_storage_path: str = "./storage"
    policy_docs_path: str = "./policy_docs"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
