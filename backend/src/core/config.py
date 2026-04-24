"""
Application configuration using Pydantic Settings.
Following Factor 1: Own Your Configuration.

Supports hierarchical environment configuration:
- .env.base: Common non-secret defaults (committed to git)
- .env.{ENVIRONMENT}: Environment-specific overrides (gitignored)
- Environment variables: Highest priority
"""

import os
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Get environment from env var, default to development
ENV = os.getenv("ENVIRONMENT", "development")


class Settings(BaseSettings):
    """Application settings with hierarchical env file support."""

    model_config = SettingsConfigDict(
        # Load base first, then environment-specific override
        env_file=[
            ".env.base",  # Common defaults (committed)
            f".env.{ENV}",  # Environment overrides (gitignored)
        ],
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    environment: Literal["development", "test", "production"] = "development"

    # Database connections
    mongodb_url: str = "mongodb://localhost:27017/fund_agent"
    redis_url: str = "redis://localhost:6379"

    # Security
    secret_key: str = "dev-secret-key-change-in-production"
    admin_secret: str = "dev-admin-secret-change-in-production"  # For CronJob auth
    allowed_hosts: list[str] = [
        "*"
    ]  # Allow all hosts (override via ALLOWED_HOSTS env var)
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Langfuse observability (optional - disabled by default)
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = ""

    # Agent Maestro LLM proxy
    agent_maestro_base_url: str = "http://localhost:23333"
    openai_api_key: str = ""  # Not used - Agent Maestro handles auth

    # LLM Configuration
    default_llm_model: str = "claude-opus-4.7"
    default_llm_temperature: float = 0.7

    # Context Window Management
    llm_context_limits: dict[str, int] = {
        "claude-opus-4.7": 200_000,
        "gpt-5.4": 128_000,
        "gemini-3.1-pro-preview": 1_000_000,
        "claude-haiku-4.5": 200_000,
    }
    compact_threshold_ratio: float = 0.75
    compact_target_ratio: float = 0.25
    tail_messages_keep: int = 3
    summarization_model: str = "claude-haiku-4.5"

    # Cache settings
    redis_ttl_seconds: int = 3600
    cache_ttl_fund_nav: int = 86400  # Fund NAV data (24 hours)
    cache_ttl_fund_holdings: int = 604800  # Fund holdings (7 days)
    cache_ttl_fund_ranking: int = 86400  # Fund rankings (24 hours)
    cache_ttl_macro: int = 86400  # Macro data (24 hours)
    cache_ttl_news: int = 3600  # News (1 hour)

    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60

    @property
    def database_name(self) -> str:
        """Extract database name from MongoDB URL."""
        # Extract database name and strip query parameters
        db_with_params = self.mongodb_url.split("/")[-1]
        return db_with_params.split("?")[0] if "?" in db_with_params else db_with_params

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
