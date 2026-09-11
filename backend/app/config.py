"""Application settings (env-driven, safe defaults)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")

    env: str = "development"
    database_url: str = f"sqlite:///{BACKEND_ROOT / 'agentpassport.db'}"
    secret_keys_path: str = str(BACKEND_ROOT / "keys")
    admin_api_key: str = "dev-admin-key-change-me"   # mutating endpoints (spec §72: override in prod)
    read_api_key: str | None = None                  # optional: require key for reads too
    cors_origins: str = "http://localhost:5173,http://localhost:4173"
    rate_limit_per_minute: int = 120
    jobs_enabled: bool = True
    jobs_interval_seconds: int = 300
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    public_base_url: str = "http://localhost:8000"   # used for did:web + agent-card URLs


@lru_cache
def get_settings() -> Settings:
    return Settings()
