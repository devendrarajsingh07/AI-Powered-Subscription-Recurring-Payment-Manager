from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://subtrack@localhost:5432/subtrack"
    web_origin: str = "http://localhost:5173"
    jwt_secret: SecretStr = SecretStr("")
    jwt_access_minutes: int = Field(default=30, ge=1, le=1440)
    jwt_issuer: str = "subtrack"
    jwt_audience: str = "subtrack-web"
    bcrypt_rounds: int = Field(default=12, ge=4, le=16)
    auth_register_limit: int = Field(default=5, ge=1, le=1000)
    auth_login_limit: int = Field(default=10, ge=1, le=1000)
    auth_window_seconds: int = Field(default=60, ge=1)
    app_timezone: str = "Asia/Kolkata"
    upload_workers: int = Field(default=2, ge=1, le=4)
    upload_queue_limit: int = Field(default=8, ge=1, le=32)


@lru_cache
def get_settings() -> Settings:
    return Settings()
