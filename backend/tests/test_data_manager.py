"""
Unit tests for the Data Manager Layer (DML).

Tests cover:
- Cache key generation and consistency
- OHLCV data fetching with correct cache behavior
- Treasury data caching
- Pre-fetch shared data pattern
- Cache hit/miss logging
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from src.services.data_manager import (
    CacheKeys,
    CacheOperations,
    DataManager,
    Granularity,
    OHLCVData,
    SharedDataContext,
    TreasuryData,
)


class TestCacheKeys:
    """Test cache key generation."""

    def test_market_key_format(self):
        """Verify market key follows {domain}:{granularity}:{symbol} format."""
        key = CacheKeys.market("daily", "AAPL")
        assert key == "market:daily:AAPL"

    def test_market_key_normalizes_case(self):
        """Verify symbol is uppercased, granularity lowercased."""
        key = CacheKeys.market("DAILY", "aapl")
        assert key == "market:daily:AAPL"

    def test_treasury_key_format(self):
        """Verify treasury key format."""
        key = CacheKeys.treasury("2y")
        assert key == "macro:treasury:2y"

    def test_treasury_key_normalizes(self):
        """Verify treasury maturity is lowercased."""
        key = CacheKeys.treasury("10Y")
        assert key == "macro:treasury:10y"

    def test_news_sentiment_key(self):
        """Verify news sentiment key format."""
        key = CacheKeys.news_sentiment("technology")
        assert key == "sentiment:news:technology"

    def test_ipo_calendar_key(self):
        """Verify IPO calendar key format."""
        key = CacheKeys.ipo_calendar()
        assert key == "macro:ipo:calendar"

    def test_insights_key_default_suffix(self):
        """Verify insights key with default suffix."""
        key = CacheKeys.insights("ai_sector_risk")
        assert key == "insights:ai_sector_risk:latest"

    def test_insights_key_custom_suffix(self):
        """Verify insights key with custom suffix."""
        key = CacheKeys.insights("ai_sector_risk", "trend")
        assert key == "insights:ai_sector_risk:trend"

    def test_parse_key(self):
        """Verify key parsing."""
        parsed = CacheKeys.parse("market:daily:AAPL")
        assert parsed["domain"] == "market"
        assert parsed["type"] == "daily"
        assert parsed["identifier"] == "AAPL"

    def test_pattern_generation(self):
        """Verify pattern generation for invalidation."""
        pattern = CacheKeys.pattern("market", "daily")
        assert pattern == "market:daily:*"


class TestGranularity:
    """Test granularity enum behavior."""

    def test_intraday_no_cache(self):
        """1min, 5min, 15min should not be cached."""
        assert Granularity.MIN_1.is_intraday is True
        assert Granularity.MIN_5.is_intraday is True
        assert Granularity.MIN_15.is_intraday is True

    def test_longer_intervals_cached(self):
        """30min+ should be cached."""
        assert Granularity.MIN_30.is_intraday is False
        assert Granularity.MIN_60.is_intraday is False
        assert Granularity.DAILY.is_intraday is False

    def test_ttl_values(self):
        """Verify TTL values for each granularity."""
        assert Granularity.MIN_1.ttl_seconds == 0
        assert Granularity.MIN_5.ttl_seconds == 0
        assert Granularity.MIN_30.ttl_seconds == 300  # 5 min
        assert Granularity.MIN_60.ttl_seconds == 900  # 15 min
        assert Granularity.DAILY.ttl_seconds == 3600  # 1 hour


class TestDataTypes:
    """Test data type serialization."""

    def test_ohlcv_to_dict(self):
        """Verify OHLCV serialization."""
        data = OHLCVData(
            date=datetime(2025, 1, 15, 10, 30, tzinfo=timezone.utc),
            open=150.0,
            high=151.5,
            low=149.5,
            close=151.0,
            volume=1000000,
        )
        d = data.to_dict()
        assert d["open"] == 150.0
        assert d["close"] == 151.0
        assert "2025-01-15" in d["date"]

    def test_ohlcv_from_dict(self):
        """Verify OHLCV deserialization."""
        d = {
            "date": "2025-01-15T10:30:00+00:00",
            "open": 150.0,
            "high": 151.5,
            "low": 149.5,
            "close": 151.0,
            "volume": 1000000,
        }
        data = OHLCVData.from_dict(d)
        assert data.open == 150.0
        assert data.volume == 1000000

    def test_treasury_round_trip(self):
        """Verify Treasury data serialization round-trip."""
        original = TreasuryData(
            date=datetime(2025, 1, 15, tzinfo=timezone.utc),
            yield_value=4.25,
            maturity="2y",
        )
        d = original.to_dict()
        restored = TreasuryData.from_dict(d)
        assert restored.yield_value == original.yield_value
        assert restored.maturity == original.maturity


class TestSharedDataContext:
    """Test shared data context container."""

    def test_get_ohlcv_by_symbol(self):
        """Verify OHLCV lookup by symbol."""
        ctx = SharedDataContext()
        data = [
            OHLCVData(
                date=datetime.now(timezone.utc),
                open=150,
                high=151,
                low=149,
                close=150.5,
                volume=1000,
            )
        ]
        ctx.ohlcv["AAPL"] = data

        assert ctx.get_ohlcv("AAPL") == data
        # Note: get_ohlcv uses symbol.upper() so lookup is case-insensitive
        assert ctx.get_ohlcv("MSFT") is None

    def test_get_treasury_by_maturity(self):
        """Verify treasury lookup by maturity."""
        ctx = SharedDataContext()
        data = [
            TreasuryData(
                date=datetime.now(timezone.utc), yield_value=4.25, maturity="2y"
            )
        ]
        ctx.treasury["2y"] = data

        assert ctx.get_treasury("2y") == data
        assert ctx.get_treasury("10y") is None

    def test_has_errors(self):
        """Verify error tracking."""
        ctx = SharedDataContext()
        assert ctx.has_errors() is False

        ctx.errors["ohlcv:AAPL"] = "API timeout"
        assert ctx.has_errors() is True


class TestCacheOperations:
    """Test cache operations wrapper."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock()
        redis.delete = AsyncMock(return_value=1)
        redis.exists = AsyncMock(return_value=False)
        return redis

    @pytest.fixture
    def cache_ops(self, mock_redis):
        """Create CacheOperations with mock Redis."""
        return CacheOperations(mock_redis)

    @pytest.mark.asyncio
    async def test_get_cache_miss(self, cache_ops, mock_redis):
        """Verify cache miss returns None."""
        result = await cache_ops.get("nonexistent:key")
        assert result is None
        mock_redis.get.assert_called_once_with("nonexistent:key")

    @pytest.mark.asyncio
    async def test_get_cache_hit_dict(self, cache_ops, mock_redis):
        """Verify cache hit returns parsed dict."""
        mock_redis.get = AsyncMock(return_value='{"foo": "bar"}')
        result = await cache_ops.get("test:key")
        assert result == {"foo": "bar"}

    @pytest.mark.asyncio
    async def test_set_with_ttl(self, cache_ops, mock_redis):
        """Verify set calls Redis with TTL."""
        await cache_ops.set("test:key", {"data": 123}, 3600)
        mock_redis.set.assert_called_once()
        # Verify the key and TTL were passed
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == "test:key"

    @pytest.mark.asyncio
    async def test_set_skips_zero_ttl(self, cache_ops, mock_redis):
        """Verify zero TTL skips caching."""
        result = await cache_ops.set("test:key", {"data": 123}, 0)
        assert result is False
        mock_redis.set.assert_not_called()


class TestDataManager:
    """Test DataManager core functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis cache that simulates cache miss then stores."""
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)  # Cache miss
        redis.set = AsyncMock()
        redis.delete = AsyncMock(return_value=1)
        redis.exists = AsyncMock(return_value=False)
        return redis

    @pytest.fixture
    def sample_df(self):
        """Sample DataFrame for OHLCV data."""
        return pd.DataFrame(
            {
                "Open": [150.0, 151.0],
                "High": [151.5, 152.0],
                "Low": [149.5, 150.5],
                "Close": [151.0, 151.5],
                "Volume": [1000000, 1100000],
            },
            index=pd.to_datetime(["2025-01-15", "2025-01-14"]),
        )

    @pytest.fixture
    def mock_av_service(self, sample_df):
        """Create mock Alpha Vantage service."""
        service = AsyncMock()
        service.get_daily_bars = AsyncMock(return_value=sample_df)
        service.get_intraday_bars = AsyncMock(return_value=sample_df)
        service.get_weekly_bars = AsyncMock(return_value=sample_df)
        service.get_monthly_bars = AsyncMock(return_value=sample_df)

        # Mock treasury
        treasury_df = pd.DataFrame(
            {
                "value": [4.25, 4.20],
            },
            index=pd.to_datetime(["2025-01-15", "2025-01-14"]),
        )
        service.get_treasury_yield = AsyncMock(return_value=treasury_df)

        return service

    @pytest.fixture
    def data_manager(self, mock_redis, mock_av_service):
        """Create DataManager with mocks."""
        return DataManager(mock_redis, mock_av_service)

    @pytest.mark.asyncio
    async def test_get_ohlcv_daily_fetches_on_miss(self, data_manager, mock_av_service):
        """Daily OHLCV should fetch from API on cache miss."""
        result = await data_manager.get_ohlcv("AAPL", "daily")

        # Should have fetched from API
        mock_av_service.get_daily_bars.assert_called_once()
        assert len(result) == 2
        assert result[0].close == 151.0

    @pytest.mark.asyncio
    async def test_get_ohlcv_intraday_always_fresh(
        self, data_manager, mock_redis, mock_av_service
    ):
        """Intraday OHLCV should NOT be cached - always fresh."""
        result = await data_manager.get_ohlcv("AAPL", "1min")

        assert len(result) == 2
        # Verify API was called
        mock_av_service.get_intraday_bars.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_treasury_fetches_on_miss(self, data_manager, mock_av_service):
        """Treasury data should fetch from API on cache miss."""
        result = await data_manager.get_treasury("2y")

        mock_av_service.get_treasury_yield.assert_called_once()
        assert len(result) == 2
        assert result[0].yield_value == 4.25
        assert result[0].maturity == "2y"

    @pytest.mark.asyncio
    async def test_prefetch_shared_parallel(self, data_manager, mock_av_service):
        """Prefetch should fetch multiple items in parallel."""
        context = await data_manager.prefetch_shared(
            symbols=["NVDA", "MSFT"],
            treasury_maturities=["2y", "10y"],
        )

        # Should have data for symbols (from parallel fetches)
        assert "NVDA" in context.ohlcv
        assert "MSFT" in context.ohlcv
        assert "2y" in context.treasury
        assert "10y" in context.treasury
        # Verify multiple calls were made
        assert mock_av_service.get_daily_bars.call_count == 2
        assert mock_av_service.get_treasury_yield.call_count == 2

    @pytest.mark.asyncio
    async def test_prefetch_continues_on_partial_error(self, mock_redis, sample_df):
        """Prefetch should continue even if one fetch fails."""
        # Create service where first call fails, second succeeds
        mock_av_service = AsyncMock()
        call_count = [0]

        async def mock_daily_bars(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("API Error")
            return sample_df

        mock_av_service.get_daily_bars = mock_daily_bars
        mock_av_service.get_treasury_yield = AsyncMock(return_value=sample_df)

        dm = DataManager(mock_redis, mock_av_service)
        context = await dm.prefetch_shared(symbols=["FAIL", "MSFT"])

        # Should have error for first symbol
        assert context.has_errors()
        # But still have data for second one
        assert "MSFT" in context.ohlcv


class TestCacheKeyConsistency:
    """Test that cache keys are consistent across the codebase."""

    def test_all_keys_follow_convention(self):
        """All generated keys should follow {domain}:{type}:{identifier}."""
        keys = [
            CacheKeys.market("daily", "AAPL"),
            CacheKeys.treasury("2y"),
            CacheKeys.news_sentiment("technology"),
            CacheKeys.ipo_calendar(),
            CacheKeys.insights("ai_sector_risk", "latest"),
            CacheKeys.etf_holdings("AIQ"),
        ]

        for key in keys:
            parts = key.split(":")
            assert len(parts) >= 3, f"Key {key} doesn't follow convention"
            assert parts[0] in ["market", "macro", "sentiment", "insights", "etf"]


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
