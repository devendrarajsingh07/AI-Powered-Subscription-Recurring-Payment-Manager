from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, HttpUrl, SecretStr, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    environment: Literal["development", "test", "production"] = "development"
    demo_enabled: bool = True
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
    statement_max_mb: int = Field(default=10, ge=1, le=10)
    statement_max_pages: int = Field(default=30, ge=1, le=30)
    statement_max_megapixels: int = Field(default=25, ge=1, le=25)
    statement_timeout_seconds: int = Field(default=120, ge=1, le=120)
    statement_page_seconds: int = Field(default=20, ge=1, le=20)
    statement_memory_mb: int = Field(default=512, ge=64, le=1024)
    statement_preview_ttl_minutes: int = Field(default=30, ge=1, le=30)
    statement_daily_limit: int = Field(default=20, ge=1, le=100)
    statement_concurrent_limit: int = Field(default=2, ge=1, le=2)
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
    llm_provider: Literal["fake", "gemini"] = "fake"
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = ""
    llm_base_url: HttpUrl = "https://generativelanguage.googleapis.com"
    llm_max_tokens: int = Field(default=1024, ge=64, le=4096)
    llm_timeout_seconds: int = Field(default=20, ge=1, le=120)
    llm_retries: int = Field(default=2, ge=0, le=3)
    chat_timeout_seconds: int = Field(default=60, ge=1, le=180)
    chat_history_window: int = Field(default=8, ge=0, le=20)
    chat_minute_limit: int = Field(default=10, ge=1, le=100)
    chat_daily_limit: int = Field(default=100, ge=1, le=1000)
    app_test_as_of: str = ""

    @model_validator(mode="before")
    @classmethod
    def demo_default(cls, values):
        if isinstance(values, dict) and values.get("environment") == "production":
            values = dict(values)
            values.setdefault("demo_enabled", False)
        return values

    @model_validator(mode="after")
    def live_configuration(self):
        if self.app_test_as_of:
            date.fromisoformat(self.app_test_as_of)
        if self.environment != "development":
            secret = self.jwt_secret.get_secret_value()
            if (
                len(secret) < 40
                or len(set(secret)) < 16
                or any(
                    word in secret.lower() for word in ("replace", "default", "secret", "example")
                )
            ):
                raise ValueError("A strong non-default JWT_SECRET is required")
            if "web_origin" not in self.model_fields_set or "*" in self.web_origin:
                raise ValueError("An explicit WEB_ORIGIN is required")
        if self.environment == "production":
            if self.demo_enabled or self.app_test_as_of or self.notifier_provider == "console":
                raise ValueError("Production forbids demo data, test clocks and console notifier")
        if self.llm_provider == "gemini" and (
            not self.llm_api_key.get_secret_value() or not self.llm_model.strip()
        ):
            raise ValueError("Live chat requires LLM_API_KEY and LLM_MODEL")
        return self


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError:
        raise RuntimeError(
            "Invalid configuration; check environment safety, JWT, CORS "
            "and LLM_PROVIDER/key/model settings"
        ) from None
