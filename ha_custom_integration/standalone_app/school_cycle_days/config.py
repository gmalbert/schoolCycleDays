"""Environment configuration for the standalone app."""

from __future__ import annotations

from functools import lru_cache

from pydantic import HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment or .env."""

    model_config = SettingsConfigDict(env_prefix="SCD_", env_file=".env", extra="ignore")

    ha_url: HttpUrl
    ha_token: str
    database_path: str = "./data/school_cycle_days.sqlite3"
    verify_ssl: bool = True
    host: str = "0.0.0.0"
    port: int = 8088

    @property
    def ha_base_url(self) -> str:
        return str(self.ha_url).rstrip("/")


@lru_cache

def get_settings() -> Settings:
    return Settings()
