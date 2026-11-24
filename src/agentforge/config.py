from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGENTFORGE_", env_file=".env", extra="ignore", hide_input_in_errors=True
    )

    environment: Literal["development", "production", "test"] = "development"
    database_url: str = Field(default="sqlite+aiosqlite:///./agentforge.db", repr=False)
    redis_url: str = Field(default="", repr=False)
    api_key: SecretStr = SecretStr("")
    sandbox_key: SecretStr = SecretStr("")
    sandbox_url: str = "http://127.0.0.1:8001"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8080"]
    request_limit: int = Field(default=65536, ge=1024, le=262144)
    rate_limit: int = Field(default=120, ge=1, le=10000)
    max_active_runs: int = Field(default=8, ge=1, le=100)
    # Owner-wide estimated spend ceiling across runs created in one UTC day.
    daily_budget_usd: float = Field(default=2.0, ge=0, le=1000, allow_inf_nan=False)
    lease_seconds: int = Field(default=30, ge=10, le=300)
    poll_seconds: float = Field(default=0.5, ge=0.1, le=10)
    tool_image: str = "agentforge-tool:local"
    # Reverse proxies in front of the API that append to X-Forwarded-For (Caddy, nginx = 2).
    # 0 ignores the header and uses the socket peer.
    trusted_proxy_hops: int = Field(default=0, ge=0, le=5)
    openai_key: SecretStr = SecretStr("")
    openai_model: str = "gpt-4.1-mini"
    gemini_key: SecretStr = SecretStr("")
    gemini_model: str = "gemini-3.8-flash"
    # Operator-supplied conservative rates, in micro-USD per token. Not live pricing.
    openai_input_rate: float = Field(default=1.0, gt=0)
    openai_output_rate: float = Field(default=5.0, gt=0)
    gemini_input_rate: float = Field(default=1.5, gt=0)
    gemini_output_rate: float = Field(default=8.0, gt=0)

    @model_validator(mode="after")
    def production_safety(self) -> "Settings":
        # Secrets are validated by the process that uses them (see require_secret), so the
        # API need not hold the sandbox or provider keys, and the worker need not hold the
        # operator key.
        if "*" in self.cors_origins:
            raise ValueError("Wildcard CORS is forbidden")
        if self.environment == "production":
            if not self.database_url.startswith("postgresql+asyncpg://"):
                raise ValueError("Production requires PostgreSQL")
            if any(not origin.startswith("https://") for origin in self.cors_origins):
                raise ValueError("Production CORS origins must use HTTPS")
        return self


def require_secret(value: SecretStr, name: str) -> str:
    secret = value.get_secret_value()
    if len(secret) < 32:
        raise ValueError(f"{name} must contain at least 32 characters")
    return secret


@lru_cache
def get_settings() -> Settings:
    return Settings()
