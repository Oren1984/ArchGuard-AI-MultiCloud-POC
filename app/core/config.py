"""Application configuration loaded from environment variables.

Centralizing config here keeps AWS/GCP/provider specifics out of business
logic — services depend on this Settings object, never on os.environ directly.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    app_name: str = "archguard-ai-multicloud-poc"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "archguard"
    postgres_user: str = "archguard"
    postgres_password: str = "changeme-local-only"
    database_url: str = "postgresql+psycopg://archguard:changeme-local-only@db:5432/archguard"

    ai_provider: Literal["mock", "openai_compatible"] = "mock"
    ai_model_name: str = "archguard-mock-v1"
    ai_prompt_version: str = "v1"

    openai_compatible_base_url: str = ""
    openai_compatible_api_key: str = ""
    openai_compatible_model: str = ""

    eval_min_confidence: float = 0.55
    eval_consistency_runs: int = 2

    approval_header_name: str = "X-ArchGuard-Actor"
    kill_switch_default_state: Literal["active", "inactive"] = "inactive"

    metrics_enabled: bool = True
    correlation_id_header: str = "X-Correlation-ID"


@lru_cache
def get_settings() -> Settings:
    return Settings()
