"""
Application configuration using Pydantic Settings.
Following Factor 1: Own Your Configuration.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    environment: Literal["development", "staging", "production"] = "development"

    # Database connections
    mongodb_url: str = "mongodb://localhost:27017/financial_agent"
    redis_url: str = "redis://localhost:6379"

    # Security
    secret_key: str = "dev-secret-key-change-in-production"
    allowed_hosts: list[str] = ["localhost", "127.0.0.1", "0.0.0.0"]
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # LangSmith configuration (Factor 2: Own Your Prompts)
    langsmith_tracing_v2: bool = True
    langsmith_api_key: str = ""
    langsmith_project: str = "financial-agent"

    # External APIs
    openai_api_key: str = ""
    qwen_api_key: str = ""

    # Cloud storage (Alibaba OSS)
    oss_access_key: str = ""
    oss_secret_key: str = ""
    oss_bucket: str = "financial-agent-charts"
    oss_endpoint: str = "oss-cn-hangzhou.aliyuncs.com"

    # Cache settings
    redis_ttl_seconds: int = 3600  # 1 hour default cache TTL

    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # per minute

    @property
    def database_name(self) -> str:
        """Extract database name from MongoDB URL."""
        return self.mongodb_url.split("/")[-1]

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
