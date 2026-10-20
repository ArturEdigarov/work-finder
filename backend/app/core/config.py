from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Literal["dev", "test", "prod"] = "dev"

    database_url: str = "postgresql+asyncpg://work_service:work_service@127.0.0.1:5432/work_service"
    test_database_url: str = (
        "postgresql+asyncpg://work_service:work_service@127.0.0.1:5432/work_service_test"
    )

    # "id:base64key,id:base64key" — the highest id is used for encryption.
    field_encryption_keys: SecretStr = SecretStr("")
    email_hash_key: SecretStr = SecretStr("")

    owner_email: str | None = None
    consent_version: str = "2026-10-18"

    telegram_bot_token: SecretStr | None = None
    telegram_bot_username: str | None = None
    telegram_link_ttl_minutes: int = 10

    web_origin: str = "http://localhost:3000"
    session_cookie_name: str = "ws_session"
    session_ttl_days: int = 30
    cookie_secure: bool = False

    password_min_length: int = 12

    # --- LLM (see ADR-0001: subscription only, never an API key) ---
    llm_provider: Literal["claude_code", "fake"] = "claude_code"
    claude_bin: str = "claude"
    llm_timeout_seconds: int = 180
    llm_model_parse: str = "sonnet"
    llm_model_score: str = "sonnet"
    llm_model_draft: str = "sonnet"
    # Our own daily caps, so the service never eats the whole subscription limit.
    llm_daily_cap_parse: int = 5
    llm_daily_cap_score: int = 30
    llm_daily_cap_draft: int = 8
    # Pause when the provider reports a limit without a reset time:
    # first pause = default, then doubled per consecutive hit, capped at max.
    llm_pause_default_minutes: int = 60
    llm_pause_max_minutes: int = 300

    def llm_model(self, kind: str) -> str:
        return str(getattr(self, f"llm_model_{kind}"))

    def llm_daily_cap(self, kind: str) -> int:
        return int(getattr(self, f"llm_daily_cap_{kind}"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
