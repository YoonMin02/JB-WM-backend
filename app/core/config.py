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
    privacy_sensitive_retention_days: int = 365

    # Storage
    file_storage_driver: str = "local"
    local_storage_path: str = "./storage"
    policy_docs_path: str = "./policy_docs"

    # Action execution
    # mock_apply = 승인 시 mock DB에 반영, external_request = 실제 외부 실행 요청(현재 미구현)
    action_execution_mode: Literal["mock_apply", "external_request"] = "mock_apply"

    # Redesign runtime
    agent_job_mode: Literal["local_stub", "codex_cli"] = "local_stub"
    agent_job_root: str = "/tmp/jbwm-agent-jobs"
    codex_command: str = "codex"
    agent_job_codex_model: str = "gpt-5.4-mini"
    agent_job_codex_reasoning_effort: str = "low"
    agent_job_codex_model_candidates: str = (
        "gpt-5.4-mini,gpt-5.5,gpt-5.3-codex-spark,gpt-5-mini,gpt-5-nano,gpt-5.1-codex-mini,gpt-5.2-codex"
    )
    agent_job_timeout_seconds: int = 1800
    agent_job_output_max_bytes: int = 200_000


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
