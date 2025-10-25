"""
Rate limiting utilities for API endpoints.
Uses Redis for distributed rate limiting.
"""

from typing import Any

import structlog
from fastapi import HTTPException, status

logger = structlog.get_logger()


class RateLimiter:
    """Redis-based rate limiter for API endpoints."""

    def __init__(self, redis_cache: Any) -> None:
        """
        Initialize rate limiter.

        Args:
            redis_cache: Redis cache instance
        """
        self.redis = redis_cache

    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> tuple[bool, int, int]:
        """
        Check if rate limit is exceeded.

        Args:
            key: Unique identifier for the rate limit (e.g., "vote:{user_id}")
            limit: Maximum number of requests allowed
            window_seconds: Time window in seconds

        Returns:
            Tuple of (is_allowed, current_count, remaining)
        """
        if not self.redis.client:
            # Redis not available - allow request (fail open)
            logger.warning("Redis not available for rate limiting - allowing request")
            return True, 0, limit

        # Use Redis INCR with expiry
        current = await self.redis.client.incr(key)

        if current == 1:
            # First request - set expiry
            await self.redis.client.expire(key, window_seconds)

        remaining = max(0, limit - current)
        is_allowed = current <= limit

        return is_allowed, current, remaining

    async def enforce_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> None:
        """
        Enforce rate limit or raise HTTPException.

        Args:
            key: Unique identifier for the rate limit
            limit: Maximum number of requests allowed
            window_seconds: Time window in seconds

        Raises:
            HTTPException: If rate limit exceeded (429)
        """
        is_allowed, current, remaining = await self.check_rate_limit(
            key, limit, window_seconds
        )

        if not is_allowed:
            logger.warning(
                "Rate limit exceeded",
                key=key,
                current=current,
                limit=limit,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {limit} requests per {window_seconds} seconds.",
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": str(remaining),
                    "X-RateLimit-Reset": str(window_seconds),
                    "Retry-After": str(window_seconds),
                },
            )
