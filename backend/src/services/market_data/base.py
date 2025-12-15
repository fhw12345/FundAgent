"""
Base class for Alpha Vantage market data service.
Provides initialization, HTTP client management, and sanitization utilities.
"""

import re
from typing import Any

import httpx
import structlog

from ...core.config import Settings

logger = structlog.get_logger()


class AlphaVantageBase:
    """
    Base class for Alpha Vantage API interactions.

    Provides:
    - HTTP client with connection pooling
    - API key management
    - Response sanitization (removes API keys from logs)
    - Resource cleanup
    """

    # Class-level compiled regex pattern for API key sanitization
    _API_KEY_PATTERN = re.compile(
        r"(API[\s_-]?key[^A-Z0-9]*)[A-Z0-9]{16,}", flags=re.IGNORECASE
    )

    def __init__(self, settings: Settings, redis_cache: Any | None = None):
        """Initialize service with Alpha Vantage API key and persistent HTTP client.

        Args:
            settings: Application settings with API keys
            redis_cache: Optional Redis cache instance for caching API responses
        """
        self.settings = settings
        self.api_key = settings.alpha_vantage_api_key
        self.base_url = "https://www.alphavantage.co/query"
        self.redis_cache = redis_cache  # Optional caching support

        # Persistent HTTP client with connection pooling
        self.client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(
                max_keepalive_connections=5,
                max_connections=10,
                keepalive_expiry=30.0,
            ),
        )

        if not self.api_key:
            logger.warning("Alpha Vantage API key not configured")

        logger.info(
            "Alpha Vantage market data service initialized",
            api_key_configured=bool(self.api_key),
            connection_pool_enabled=True,
        )

    async def close(self) -> None:
        """Close HTTP client and cleanup resources."""
        await self.client.aclose()
        logger.info("Alpha Vantage market data service closed")

    def _sanitize_text(self, text: str) -> str:
        """Remove API key from text strings before logging or raising exceptions."""
        # Use pre-compiled regex pattern (class-level optimization)
        if "API key" in text or "api key" in text or "apikey" in text:
            text = self._API_KEY_PATTERN.sub(r"\1****", text)
        return text

    def _sanitize_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Remove API key from error responses before logging."""
        sanitized = response.copy()

        # Mask API key in Information messages
        if "Information" in sanitized:
            sanitized["Information"] = self._sanitize_text(sanitized["Information"])

        # Mask API key in Note messages
        if "Note" in sanitized:
            sanitized["Note"] = self._sanitize_text(sanitized["Note"])

        # Mask API key in Error messages
        if "Error Message" in sanitized:
            sanitized["Error Message"] = self._sanitize_text(sanitized["Error Message"])

        return sanitized
