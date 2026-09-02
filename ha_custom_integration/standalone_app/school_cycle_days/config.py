"""Environment configuration for the standalone app.

Home Assistant is deliberately optional. The standalone application can run,
generate schedules, import/export ICS files, and serve its own calendar without
any external integration configured.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment or .env."""

    model_config = SettingsConfigDict(env_prefix="SCD_", env_file=".env", extra="ignore")

    database_path: str = "./data/school_cycle_days.sqlite3"
    host: str = "0.0.0.0"
    port: int = 8088

    # Optional Home Assistant adapter. Neither value is required for startup.
    ha_url: str = ""
    ha_token: str = ""
    verify_ssl: bool = True

    @property
    def ha_enabled(self) -> bool:
        return bool(self.ha_url.strip() and self.ha_token.strip())

    @property
    def ha_base_url(self) -> str:
        return self.ha_url.strip().rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()
