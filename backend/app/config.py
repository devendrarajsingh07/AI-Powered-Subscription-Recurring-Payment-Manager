from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal

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
    high_cost_yearly_inr: Decimal = Field(default=Decimal("12000"), ge=0)
    high_cost_share: Decimal = Field(default=Decimal("0.35"), ge=0, le=1)
    unused_days: int = Field(default=60, ge=1, le=3650)
    scheduler_enabled: bool = True
    alert_job_hour: int = Field(default=9, ge=0, le=23)
    alert_job_minute: int = Field(default=0, ge=0, le=59)
    alert_max_attempts: int = Field(default=3, ge=1, le=10)
    alert_retry_seconds: int = Field(default=300, ge=1, le=86400)
    notifier_provider: Literal["console", "smtp"] = "console"
    outbox_dir: Path = Path("var/outbox")
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_security: Literal["starttls", "tls", "none"] = "starttls"
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_from: str = ""
    smtp_timeout_seconds: int = Field(default=10, ge=1, le=60)


@lru_cache
def get_settings() -> Settings:
    return Settings()
