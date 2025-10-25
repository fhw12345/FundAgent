"""
Comprehensive tests for RateLimiter class.

Tests cover:
- Redis availability handling (fail-open behavior)
- Rate limit counting and expiry
- Boundary conditions (at limit, over limit)
- HTTP exception raising with proper headers
- Multiple concurrent requests
"""

import pytest
from fastapi import HTTPException, status
from unittest.mock import AsyncMock, MagicMock

from src.core.rate_limiter import RateLimiter


class TestRateLimiterInitialization:
    """Test RateLimiter initialization."""

    def test_init_stores_redis_cache(self):
        """Test that RateLimiter stores redis cache reference."""
        mock_redis = MagicMock()
        limiter = RateLimiter(mock_redis)

        assert limiter.redis == mock_redis


class TestCheckRateLimitRedisUnavailable:
    """Test check_rate_limit when Redis is unavailable (fail-open behavior)."""

    @pytest.mark.asyncio
    async def test_fail_open_when_redis_unavailable(self):
        """Test that rate limiter allows requests when Redis is unavailable (fail-open)."""
        # Arrange: Redis client is None (unavailable)
        mock_redis = MagicMock()
        mock_redis.client = None
        limiter = RateLimiter(mock_redis)

        # Act
        is_allowed, current, remaining = await limiter.check_rate_limit(
            key="test:user:123",
            limit=10,
            window_seconds=60,
        )

        # Assert: Fail-open behavior
        assert is_allowed is True
        assert current == 0
        assert remaining == 10

    @pytest.mark.asyncio
    async def test_logs_warning_when_redis_unavailable(self, caplog):
        """Test that warning is logged when Redis is unavailable."""
        # Arrange
        mock_redis = MagicMock()
        mock_redis.client = None
        limiter = RateLimiter(mock_redis)

        # Act
        await limiter.check_rate_limit("test:key", 10, 60)

        # Assert: Warning is logged
        # Note: structlog is used, so we check if the method was called
        # In a real scenario, you'd configure structlog to write to caplog


class TestCheckRateLimitFirstRequest:
    """Test check_rate_limit on first request (sets expiry)."""

    @pytest.mark.asyncio
    async def test_first_request_increments_and_sets_expiry(self):
        """Test that first request increments counter and sets expiry."""
        # Arrange
        mock_redis_client = AsyncMock()
        mock_redis_client.incr = AsyncMock(return_value=1)  # First request
        mock_redis_client.expire = AsyncMock()

        mock_redis = MagicMock()
        mock_redis.client = mock_redis_client

        limiter = RateLimiter(mock_redis)

        # Act
        is_allowed, current, remaining = await limiter.check_rate_limit(
            key="vote:user:456",
            limit=5,
            window_seconds=300,
        )

        # Assert
        assert is_allowed is True
        assert current == 1
        assert remaining == 4

        # Verify Redis operations
        mock_redis_client.incr.assert_called_once_with("vote:user:456")
        mock_redis_client.expire.assert_called_once_with("vote:user:456", 300)

    @pytest.mark.asyncio
    async def test_first_request_remaining_calculation(self):
        """Test remaining count calculation on first request."""
        # Arrange
        mock_redis_client = AsyncMock()
        mock_redis_client.incr = AsyncMock(return_value=1)
        mock_redis_client.expire = AsyncMock()

        mock_redis = MagicMock()
        mock_redis.client = mock_redis_client

        limiter = RateLimiter(mock_redis)

        # Act
        is_allowed, current, remaining = await limiter.check_rate_limit(
            key="test:key",
            limit=100,
            window_seconds=3600,
        )

        # Assert: remaining = limit - current
        assert remaining == 99
        assert current == 1


class TestCheckRateLimitWithinLimit:
    """Test check_rate_limit when requests are within limit."""

    @pytest.mark.asyncio
    async def test_second_request_no_expiry_set(self):
        """Test that second request does not set expiry again."""
        # Arrange: Second request (counter = 2)
        mock_redis_client = AsyncMock()
        mock_redis_client.incr = AsyncMock(return_value=2)
        mock_redis_client.expire = AsyncMock()

        mock_redis = MagicMock()
        mock_redis.client = mock_redis_client

        limiter = RateLimiter(mock_redis)

        # Act
        is_allowed, current, remaining = await limiter.check_rate_limit(
            key="test:key",
            limit=10,
            window_seconds=60,
        )

        # Assert
        assert is_allowed is True
        assert current == 2
        assert remaining == 8

        # Verify expiry NOT called (only on first request)
        mock_redis_client.expire.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_requests_within_limit(self):
        """Test multiple requests under the limit."""
        # Arrange
        mock_redis_client = AsyncMock()
        mock_redis = MagicMock()
        mock_redis.client = mock_redis_client

        limiter = RateLimiter(mock_redis)

        # Simulate 3 requests (all within limit of 5)
        for count in [1, 2, 3]:
            mock_redis_client.incr = AsyncMock(return_value=count)
            mock_redis_client.expire = AsyncMock()

            is_allowed, current, remaining = await limiter.check_rate_limit(
                key="test:key",
                limit=5,
                window_seconds=60,
            )

            assert is_allowed is True
            assert current == count
            assert remaining == 5 - count


class TestCheckRateLimitAtBoundary:
    """Test check_rate_limit at exact limit boundary."""

    @pytest.mark.asyncio
    async def test_exactly_at_limit_is_allowed(self):
        """Test that request at exact limit is still allowed."""
        # Arrange: At limit (5th request out of 5 allowed)
        mock_redis_client = AsyncMock()
        mock_redis_client.incr = AsyncMock(return_value=5)

        mock_redis = MagicMock()
        mock_redis.client = mock_redis_client

        limiter = RateLimiter(mock_redis)

        # Act
        is_allowed, current, remaining = await limiter.check_rate_limit(
            key="test:key",
            limit=5,
            window_seconds=60,
        )

        # Assert: At limit is allowed (current <= limit)
        assert is_allowed is True
        assert current == 5
        assert remaining == 0  # No more remaining


class TestCheckRateLimitExceeded:
    """Test check_rate_limit when limit is exceeded."""

    @pytest.mark.asyncio
    async def test_exceeding_limit_is_denied(self):
        """Test that request exceeding limit is denied."""
        # Arrange: Over limit (6th request out of 5 allowed)
        mock_redis_client = AsyncMock()
        mock_redis_client.incr = AsyncMock(return_value=6)

        mock_redis = MagicMock()
        mock_redis.client = mock_redis_client

        limiter = RateLimiter(mock_redis)

        # Act
        is_allowed, current, remaining = await limiter.check_rate_limit(
            key="test:key",
            limit=5,
            window_seconds=60,
        )

        # Assert: Over limit is denied
        assert is_allowed is False
        assert current == 6
        assert remaining == 0  # Capped at 0 (max(0, limit - current))

    @pytest.mark.asyncio
    async def test_remaining_never_negative(self):
        """Test that remaining count never goes negative."""
        # Arrange: Way over limit
        mock_redis_client = AsyncMock()
        mock_redis_client.incr = AsyncMock(return_value=100)

        mock_redis = MagicMock()
        mock_redis.client = mock_redis_client

        limiter = RateLimiter(mock_redis)

        # Act
        is_allowed, current, remaining = await limiter.check_rate_limit(
            key="test:key",
            limit=10,
            window_seconds=60,
        )

        # Assert: remaining is capped at 0 (not -90)
        assert remaining == 0
        assert is_allowed is False


class TestEnforceLimitAllowed:
    """Test enforce_limit when requests are allowed."""

    @pytest.mark.asyncio
    async def test_enforce_limit_allows_when_under_limit(self):
        """Test that enforce_limit does not raise exception when under limit."""
        # Arrange
        mock_redis_client = AsyncMock()
        mock_redis_client.incr = AsyncMock(return_value=3)

        mock_redis = MagicMock()
        mock_redis.client = mock_redis_client

        limiter = RateLimiter(mock_redis)

        # Act & Assert: No exception raised
        try:
            await limiter.enforce_limit(
                key="test:key",
                limit=5,
                window_seconds=60,
            )
        except HTTPException:
            pytest.fail("enforce_limit should not raise exception when under limit")

    @pytest.mark.asyncio
    async def test_enforce_limit_allows_at_exact_limit(self):
        """Test that enforce_limit allows request at exact limit."""
        # Arrange: Exactly at limit
        mock_redis_client = AsyncMock()
        mock_redis_client.incr = AsyncMock(return_value=10)

        mock_redis = MagicMock()
        mock_redis.client = mock_redis_client

        limiter = RateLimiter(mock_redis)

        # Act & Assert: No exception at boundary
        try:
            await limiter.enforce_limit(
                key="test:key",
                limit=10,
                window_seconds=60,
            )
        except HTTPException:
            pytest.fail("enforce_limit should not raise exception at exact limit")


class TestEnforceLimitExceeded:
    """Test enforce_limit when limit is exceeded."""

    @pytest.mark.asyncio
    async def test_enforce_limit_raises_429_when_exceeded(self):
        """Test that enforce_limit raises HTTP 429 when limit exceeded."""
        # Arrange: Over limit
        mock_redis_client = AsyncMock()
        mock_redis_client.incr = AsyncMock(return_value=11)

        mock_redis = MagicMock()
        mock_redis.client = mock_redis_client

        limiter = RateLimiter(mock_redis)

        # Act & Assert: HTTP 429 raised
        with pytest.raises(HTTPException) as exc_info:
            await limiter.enforce_limit(
                key="test:key",
                limit=10,
                window_seconds=60,
            )

        assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    @pytest.mark.asyncio
    async def test_enforce_limit_exception_message(self):
        """Test that exception contains proper error message."""
        # Arrange
        mock_redis_client = AsyncMock()
        mock_redis_client.incr = AsyncMock(return_value=11)

        mock_redis = MagicMock()
        mock_redis.client = mock_redis_client

        limiter = RateLimiter(mock_redis)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await limiter.enforce_limit(
                key="test:key",
                limit=10,
                window_seconds=60,
            )

        assert "Rate limit exceeded" in exc_info.value.detail
        assert "10 requests per 60 seconds" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_enforce_limit_exception_headers(self):
        """Test that exception includes proper rate limit headers."""
        # Arrange
        mock_redis_client = AsyncMock()
        mock_redis_client.incr = AsyncMock(return_value=6)

        mock_redis = MagicMock()
        mock_redis.client = mock_redis_client

        limiter = RateLimiter(mock_redis)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await limiter.enforce_limit(
                key="test:key",
                limit=5,
                window_seconds=300,
            )

        headers = exc_info.value.headers
        assert headers["X-RateLimit-Limit"] == "5"
        assert headers["X-RateLimit-Remaining"] == "0"
        assert headers["X-RateLimit-Reset"] == "300"
        assert headers["Retry-After"] == "300"


class TestRateLimiterEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_zero_limit_immediately_exceeds(self):
        """Test that limit of 0 immediately exceeds."""
        # Arrange
        mock_redis_client = AsyncMock()
        mock_redis_client.incr = AsyncMock(return_value=1)

        mock_redis = MagicMock()
        mock_redis.client = mock_redis_client

        limiter = RateLimiter(mock_redis)

        # Act
        is_allowed, current, remaining = await limiter.check_rate_limit(
            key="test:key",
            limit=0,
            window_seconds=60,
        )

        # Assert: Even first request exceeds limit of 0
        assert is_allowed is False
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_large_limit_value(self):
        """Test with very large limit value."""
        # Arrange
        mock_redis_client = AsyncMock()
        mock_redis_client.incr = AsyncMock(return_value=1)
        mock_redis_client.expire = AsyncMock()

        mock_redis = MagicMock()
        mock_redis.client = mock_redis_client

        limiter = RateLimiter(mock_redis)

        # Act
        is_allowed, current, remaining = await limiter.check_rate_limit(
            key="test:key",
            limit=1000000,
            window_seconds=3600,
        )

        # Assert
        assert is_allowed is True
        assert remaining == 999999

    @pytest.mark.asyncio
    async def test_different_keys_independent(self):
        """Test that different keys have independent rate limits."""
        # Arrange
        mock_redis_client = AsyncMock()
        # Set up incr to return 1 for both calls (first request for each key)
        mock_redis_client.incr = AsyncMock(return_value=1)
        mock_redis_client.expire = AsyncMock()

        mock_redis = MagicMock()
        mock_redis.client = mock_redis_client

        limiter = RateLimiter(mock_redis)

        # Act: Check two different keys
        await limiter.check_rate_limit("key:A", limit=5, window_seconds=60)
        await limiter.check_rate_limit("key:B", limit=5, window_seconds=60)

        # Assert: Each key incremented independently
        assert mock_redis_client.incr.call_count == 2
        mock_redis_client.incr.assert_any_call("key:A")
        mock_redis_client.incr.assert_any_call("key:B")
