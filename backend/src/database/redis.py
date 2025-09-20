"""
Redis cache connection and operations.
Following Factor 3: External Dependencies as Services.
"""

import json
from typing import Any

import redis.asyncio as redis
import structlog

logger = structlog.get_logger()


class RedisCache:
    """Redis connection manager with async support."""

    def __init__(self) -> None:
        self.client: redis.Redis | None = None

    async def connect(self, redis_url: str) -> None:
        """Establish connection to Redis."""
        try:
            self.client = redis.from_url(redis_url, decode_responses=True)

            # Test connection
            await self.client.ping()

            logger.info("Redis connection established", url=redis_url)

        except Exception as e:
            logger.error("Failed to connect to Redis", error=str(e))
            raise

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self.client:
            await self.client.aclose()
            logger.info("Redis connection closed")

    async def health_check(self) -> dict[str, bool | str]:
        """Check Redis connection health."""
        try:
            if not self.client:
                return {"connected": False, "error": "No client connection"}

            # Ping Redis
            await self.client.ping()

            # Get server info
            info = await self.client.info()

            return {
                "connected": True,
                "version": info.get("redis_version", "unknown"),
                "memory_usage": info.get("used_memory_human", "unknown"),
            }

        except Exception as e:
            logger.error("Redis health check failed", error=str(e))
            return {"connected": False, "error": str(e)}

    async def get(self, key: str) -> Any | None:
        """Get value from Redis cache."""
        if not self.client:
            raise RuntimeError("Redis connection not established")

        try:
            value = await self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except json.JSONDecodeError:
            logger.warning("Failed to decode JSON from Redis", key=key)
            return None
        except Exception as e:
            logger.error("Redis get operation failed", key=key, error=str(e))
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int | None = None,
    ) -> bool:
        """Set value in Redis cache with optional TTL."""
        if not self.client:
            raise RuntimeError("Redis connection not established")

        try:
            json_value = json.dumps(value, default=str)
            await self.client.set(key, json_value, ex=ttl_seconds)
            return True
        except Exception as e:
            logger.error("Redis set operation failed", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from Redis cache."""
        if not self.client:
            raise RuntimeError("Redis connection not established")

        try:
            result = await self.client.delete(key)
            return result > 0
        except Exception as e:
            logger.error("Redis delete operation failed", key=key, error=str(e))
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis cache."""
        if not self.client:
            raise RuntimeError("Redis connection not established")

        try:
            result = await self.client.exists(key)
            return result > 0
        except Exception as e:
            logger.error("Redis exists operation failed", key=key, error=str(e))
            return False
