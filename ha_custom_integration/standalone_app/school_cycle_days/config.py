"""Environment configuration for the standalone application."""
from __future__ import annotations
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SCD_", env_file=".env", extra="ignore")
    database_path:str="./data/school_cycle_days.sqlite3"; host:str="0.0.0.0"; port:int=8088
    session_secret:str=""; require_login:bool=False; source_refresh_seconds:int=21600
    ha_url:str=""; ha_token:str=""; verify_ssl:bool=True
    mqtt_host:str=""; mqtt_port:int=1883; mqtt_username:str=""; mqtt_password:str=""; mqtt_discovery_prefix:str="homeassistant"; mqtt_base_topic:str="school_cycle_days"
    @property
    def ha_enabled(self):return bool(self.ha_url.strip() and self.ha_token.strip())
    @property
    def ha_base_url(self):return self.ha_url.strip().rstrip("/")
    @property
    def mqtt_enabled(self):return bool(self.mqtt_host.strip())

@lru_cache
def get_settings()->Settings:return Settings()
