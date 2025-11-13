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
    mongodb_url: str = "mongodb://localhost:27017/financial_agent"
    redis_url: str = "redis://localhost:6379"

    # Security
    secret_key: str = "dev-secret-key-change-in-production"
    allowed_hosts: list[str] = [
        "*"
    ]  # Allow all hosts (override via ALLOWED_HOSTS env var)
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Langfuse observability configuration (Factor 2: Own Your Prompts)
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://langfuse-server:3000"

    # External APIs - LLM
    openai_api_key: str = ""
    qwen_api_key: str = ""  # Legacy - use dashscope_api_key instead
    dashscope_api_key: str = ""  # Alibaba Cloud DashScope API key

    # LLM Configuration
    default_llm_model: str = "qwen-plus-latest"  # Default model for agents
    default_llm_temperature: float = 0.7  # Default temperature for LLM calls

    # External APIs - Market Data & Trading
    alpha_vantage_api_key: str = ""  # Alpha Vantage API key (premium: 75 calls/min)
    alpaca_api_key: str = ""  # Alpaca Paper Trading API key
    alpaca_secret_key: str = ""  # Alpaca Paper Trading secret key
    alpaca_base_url: str = "https://paper-api.alpaca.markets"  # Paper trading endpoint
    polygon_api_key: str = ""  # Polygon.io API key for extended hours data

    # Email configuration (Tencent Cloud SES)
    tencent_secret_id: str = ""  # Tencent Cloud API SecretID
    tencent_secret_key: str = ""  # Tencent Cloud API SecretKey (from Azure Key Vault)
    tencent_ses_region: str = "ap-guangzhou"  # ap-guangzhou or ap-hongkong
    tencent_ses_from_email: str = "noreply@klinematrix.com"
    tencent_ses_from_name: str = "KlineMatrix"
    tencent_ses_template_id: int = 37066  # Template ID for verification emails
    email_verification_subject: str = "Your KlineMatrix Verification Code"
    email_code_ttl_seconds: int = 300  # 5 minutes

    # Development mode settings
    dev_bypass_email_verification: bool = False  # Skip actual email sending in dev mode
    dev_bypass_verification_code: str = "888888"  # Fixed code for dev bypass (6-digit)

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
