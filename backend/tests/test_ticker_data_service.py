"""
Unit tests for TickerDataService.
Tests the core service structure, parameter validation, and cache key generation.
"""

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pandas as pd
import pytest

from src.core.data.ticker_data_service import TickerDataService
from src.database.redis import RedisCache


class TestTickerDataService:
    """Test suite for TickerDataService class."""

    @pytest.fixture
    def mock_redis_cache(self):
        """Create mock Redis cache for testing."""
        cache = Mock(spec=RedisCache)
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock(return_value=None)
        return cache

    @pytest.fixture
    def ticker_service(self, mock_redis_cache):
        """Create TickerDataService instance with mocked dependencies."""
        return TickerDataService(mock_redis_cache)

    @pytest.mark.asyncio
    async def test_service_initialization(self, mock_redis_cache):
        """Test TickerDataService initialization."""
        service = TickerDataService(mock_redis_cache)

        assert service.redis_cache == mock_redis_cache
        assert service.default_ttl == 1800  # 30 minutes

    @pytest.mark.asyncio
    async def test_get_ticker_history_with_period(self, ticker_service):
        """Test get_ticker_history with period parameter."""
        with patch("yfinance.Ticker") as mock_ticker_class:
            mock_ticker = Mock()
            mock_ticker.history.return_value = pd.DataFrame()
            mock_ticker_class.return_value = mock_ticker

            result = await ticker_service.get_ticker_history(
                symbol="AAPL", interval="1d", period="6mo"
            )

            # Should return DataFrame (empty if no mock data)
            assert isinstance(result, pd.DataFrame)

    @pytest.mark.asyncio
    async def test_get_ticker_history_with_date_range(self, ticker_service):
        """Test get_ticker_history with start/end dates."""
        with patch("yfinance.Ticker") as mock_ticker_class:
            mock_ticker = Mock()
            mock_ticker.history.return_value = pd.DataFrame()
            mock_ticker_class.return_value = mock_ticker

            result = await ticker_service.get_ticker_history(
                symbol="AAPL",
                interval="1d",
                start_date="2024-01-01",
                end_date="2024-06-01",
            )

            assert isinstance(result, pd.DataFrame)

    @pytest.mark.asyncio
    async def test_get_ticker_history_defaults(self, ticker_service):
        """Test get_ticker_history with default parameters."""
        with patch("yfinance.Ticker") as mock_ticker_class:
            mock_ticker = Mock()
            mock_ticker.history.return_value = pd.DataFrame()
            mock_ticker_class.return_value = mock_ticker

            result = await ticker_service.get_ticker_history(symbol="AAPL")

            assert isinstance(result, pd.DataFrame)

    def test_validate_parameters_valid_period(self, ticker_service):
        """Test parameter validation with valid period."""
        # Should not raise any exception
        ticker_service._validate_parameters("6mo", None, None)

    def test_validate_parameters_valid_date_range(self, ticker_service):
        """Test parameter validation with valid date range."""
        # Should not raise any exception
        ticker_service._validate_parameters(None, "2024-01-01", "2024-06-01")

    def test_validate_parameters_no_params(self, ticker_service):
        """Test parameter validation with no parameters."""
        # Should not raise any exception (will use defaults)
        ticker_service._validate_parameters(None, None, None)

    def test_validate_parameters_period_and_dates_conflict(self, ticker_service):
        """Test parameter validation rejects period + date range."""
        with pytest.raises(
            ValueError, match="Cannot specify both 'period' and date range"
        ):
            ticker_service._validate_parameters("6mo", "2024-01-01", "2024-06-01")

    def test_validate_parameters_incomplete_date_range(self, ticker_service):
        """Test parameter validation rejects incomplete date ranges."""
        # Missing end_date
        with pytest.raises(
            ValueError, match="Both start_date and end_date are required"
        ):
            ticker_service._validate_parameters(None, "2024-01-01", None)

        # Missing start_date
        with pytest.raises(
            ValueError, match="Both start_date and end_date are required"
        ):
            ticker_service._validate_parameters(None, None, "2024-06-01")

    def test_validate_parameters_invalid_date_format(self, ticker_service):
        """Test parameter validation rejects invalid date formats."""
        with pytest.raises(ValueError, match="Invalid date format"):
            ticker_service._validate_parameters(None, "2024/01/01", "2024-06-01")

    def test_validate_parameters_invalid_date_logic(self, ticker_service):
        """Test parameter validation rejects illogical date ranges."""
        with pytest.raises(ValueError, match="Start date .* must be before end date"):
            ticker_service._validate_parameters(None, "2024-06-01", "2024-01-01")

    def test_normalize_to_date_range_with_period(self, ticker_service):
        """Test date normalization with period parameter."""
        # Mock DateUtils.period_to_date_range for predictable results
        with patch(
            "src.core.data.ticker_data_service.DateUtils.period_to_date_range"
        ) as mock_convert:
            mock_convert.return_value = ("2024-04-03", "2024-10-03")

            start, end = ticker_service._normalize_to_date_range("6mo", None, None)

            assert start == "2024-04-03"
            assert end == "2024-10-03"
            mock_convert.assert_called_once_with("6mo")

    def test_normalize_to_date_range_with_dates(self, ticker_service):
        """Test date normalization with explicit dates."""
        start, end = ticker_service._normalize_to_date_range(
            None, "2024-01-01", "2024-06-01"
        )

        assert start == "2024-01-01"
        assert end == "2024-06-01"

    def test_normalize_to_date_range_defaults(self, ticker_service):
        """Test date normalization with default parameters."""
        with patch(
            "src.core.data.ticker_data_service.DateUtils.period_to_date_range"
        ) as mock_convert:
            mock_convert.return_value = ("2024-04-03", "2024-10-03")

            start, end = ticker_service._normalize_to_date_range(None, None, None)

            assert start == "2024-04-03"
            assert end == "2024-10-03"
            mock_convert.assert_called_once_with("6mo")  # Default period

    def test_generate_cache_key_basic(self, ticker_service):
        """Test cache key generation with basic parameters."""
        cache_key = ticker_service._generate_cache_key(
            "AAPL", "2024-01-01", "2024-06-01", "1d"
        )

        expected = "ticker_data:AAPL:2024-01-01:2024-06-01:1d"
        assert cache_key == expected

    def test_generate_cache_key_symbol_normalization(self, ticker_service):
        """Test cache key generation normalizes symbol case."""
        cache_key = ticker_service._generate_cache_key(
            "aapl", "2024-01-01", "2024-06-01", "1d"
        )

        expected = "ticker_data:AAPL:2024-01-01:2024-06-01:1d"
        assert cache_key == expected

    def test_generate_cache_key_symbol_whitespace(self, ticker_service):
        """Test cache key generation handles symbol whitespace."""
        cache_key = ticker_service._generate_cache_key(
            " AAPL ", "2024-01-01", "2024-06-01", "1d"
        )

        expected = "ticker_data:AAPL:2024-01-01:2024-06-01:1d"
        assert cache_key == expected

    def test_generate_cache_key_different_intervals(self, ticker_service):
        """Test cache key generation for different intervals."""
        intervals = ["1m", "1h", "1d", "1wk", "1mo"]

        for interval in intervals:
            cache_key = ticker_service._generate_cache_key(
                "AAPL", "2024-01-01", "2024-06-01", interval
            )

            expected = f"ticker_data:AAPL:2024-01-01:2024-06-01:{interval}"
            assert cache_key == expected

    def test_calculate_ttl_interval_mapping(self, ticker_service):
        """Test TTL calculation for different intervals."""
        test_cases = [
            ("1m", 60),  # 1 minute
            ("5m", 300),  # 5 minutes
            ("1h", 1800),  # 30 minutes
            ("1d", 3600),  # 1 hour
            ("1wk", 7200),  # 2 hours
            ("1mo", 14400),  # 4 hours
            ("unknown", 1800),  # Default
        ]

        # Use historical date (not today) to avoid current data multiplier
        start_date = "2024-01-01"
        end_date = "2024-06-01"

        for interval, expected_base_ttl in test_cases:
            ttl = ticker_service._calculate_ttl(interval, start_date, end_date)
            # Historical data gets 8x multiplier
            expected_ttl = expected_base_ttl * 8
            assert ttl == expected_ttl

    def test_calculate_ttl_current_vs_historical(self, ticker_service):
        """Test TTL calculation for current vs historical data."""
        interval = "1d"
        base_ttl = 3600  # 1 hour for daily data

        # Historical data
        historical_ttl = ticker_service._calculate_ttl(
            interval, "2024-01-01", "2024-06-01"
        )
        assert historical_ttl == base_ttl * 8  # 8x multiplier

        # Current data (today)
        today = datetime.now().date().strftime("%Y-%m-%d")
        yesterday = "2024-01-01"  # Doesn't matter, end date is what counts
        current_ttl = ticker_service._calculate_ttl(interval, yesterday, today)
        assert current_ttl == base_ttl  # No multiplier

    @pytest.mark.asyncio
    async def test_integration_cache_key_consistency(self, ticker_service):
        """Test that same logical request generates same cache key."""
        # Mock period conversion for predictable results
        with patch(
            "src.core.data.ticker_data_service.DateUtils.period_to_date_range"
        ) as mock_convert:
            mock_convert.return_value = ("2024-04-03", "2024-10-03")

            # Two equivalent requests should generate same cache key
            await ticker_service.get_ticker_history("AAPL", interval="1d", period="6mo")
            await ticker_service.get_ticker_history(
                "AAPL", interval="1d", start_date="2024-04-03", end_date="2024-10-03"
            )

            # Both should have same normalized parameters and cache key
            # (We'll verify this more thoroughly when we add actual caching logic)

    def test_cache_key_uniqueness(self, ticker_service):
        """Test that different parameters generate different cache keys."""
        base_params = ("AAPL", "2024-01-01", "2024-06-01", "1d")
        base_key = ticker_service._generate_cache_key(*base_params)

        # Different symbol
        key1 = ticker_service._generate_cache_key(
            "MSFT", "2024-01-01", "2024-06-01", "1d"
        )
        assert key1 != base_key

        # Different dates
        key2 = ticker_service._generate_cache_key(
            "AAPL", "2024-02-01", "2024-06-01", "1d"
        )
        assert key2 != base_key

        # Different interval
        key3 = ticker_service._generate_cache_key(
            "AAPL", "2024-01-01", "2024-06-01", "1h"
        )
        assert key3 != base_key


class TestTickerDataServiceCaching:
    """Test suite for TickerDataService caching behavior."""

    @pytest.fixture
    def mock_redis_cache(self):
        """Create mock Redis cache for testing."""
        cache = Mock(spec=RedisCache)
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock(return_value=None)
        return cache

    @pytest.fixture
    def ticker_service(self, mock_redis_cache):
        """Create TickerDataService instance with mocked dependencies."""
        return TickerDataService(mock_redis_cache)

    @pytest.mark.asyncio
    async def test_cache_miss_returns_empty_df(self, ticker_service, mock_redis_cache):
        """Test cache miss returns empty DataFrame when yfinance returns no data."""
        mock_redis_cache.get.return_value = None

        with patch("yfinance.Ticker") as mock_ticker_class:
            mock_ticker = Mock()
            mock_ticker.history.return_value = pd.DataFrame()
            mock_ticker_class.return_value = mock_ticker

            result = await ticker_service.get_ticker_history(
                "AAPL", interval="1d", period="6mo"
            )

            assert isinstance(result, pd.DataFrame)
            assert result.empty
            # Should check cache
            assert mock_redis_cache.get.called

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_data(
        self, ticker_service, mock_redis_cache
    ):
        """Test cache hit returns deserialized DataFrame."""
        # Mock cached data
        cached_dict = {
            "Open": {0: 150.0, 1: 151.0},
            "High": {0: 152.0, 1: 153.0},
            "Low": {0: 149.0, 1: 150.0},
            "Close": {0: 151.0, 1: 152.0},
            "Volume": {0: 1000000, 1: 1100000},
        }
        mock_redis_cache.get.return_value = cached_dict

        result = await ticker_service.get_ticker_history(
            "AAPL", interval="1d", period="6mo"
        )

        # Should return DataFrame from cache
        assert isinstance(result, pd.DataFrame)
        assert not result.empty
        assert len(result) == 2
        assert "Open" in result.columns
        assert result["Open"].iloc[0] == 150.0

        # Should not call set (cache hit, no write)
        assert not mock_redis_cache.set.called

    @pytest.mark.asyncio
    async def test_cache_key_used_correctly(self, ticker_service, mock_redis_cache):
        """Test correct cache key is used for get operation."""
        mock_redis_cache.get.return_value = None

        await ticker_service.get_ticker_history(
            "AAPL", interval="1d", start_date="2024-01-01", end_date="2024-06-01"
        )

        # Verify get was called with correct cache key
        expected_key = "ticker_data:AAPL:2024-01-01:2024-06-01:1d"
        mock_redis_cache.get.assert_called_once_with(expected_key)

    @pytest.mark.asyncio
    async def test_empty_df_not_cached(self, ticker_service, mock_redis_cache):
        """Test that empty DataFrames are not cached when yfinance returns no data."""
        mock_redis_cache.get.return_value = None

        with patch("yfinance.Ticker") as mock_ticker_class:
            mock_ticker = Mock()
            mock_ticker.history.return_value = pd.DataFrame()
            mock_ticker_class.return_value = mock_ticker

            result = await ticker_service.get_ticker_history(
                "AAPL", interval="1d", period="6mo"
            )

            # Empty DataFrame should not be cached
            assert result.empty
            assert not mock_redis_cache.set.called

    @pytest.mark.asyncio
    async def test_cache_ttl_calculation(self, ticker_service, mock_redis_cache):
        """Test TTL is calculated correctly for cache operations."""
        # We'll test this more thoroughly when we have yfinance integration
        # For now, verify the TTL calculation method works
        ttl = ticker_service._calculate_ttl("1d", "2024-01-01", "2024-06-01")

        # Historical daily data: 3600 * 8 = 28800
        assert ttl == 28800

    @pytest.mark.asyncio
    async def test_cache_miss_logs_correctly(self, ticker_service, mock_redis_cache):
        """Test cache miss scenario triggers correct logging."""
        mock_redis_cache.get.return_value = None

        with patch("src.core.data.ticker_data_service.logger") as mock_logger:
            await ticker_service.get_ticker_history("AAPL", interval="1d", period="6mo")

            # Should log cache miss
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any("Cache miss" in str(call) for call in log_calls)

    @pytest.mark.asyncio
    async def test_cache_hit_logs_correctly(self, ticker_service, mock_redis_cache):
        """Test cache hit scenario triggers correct logging."""
        mock_redis_cache.get.return_value = {"Open": {0: 150.0}}

        with patch("src.core.data.ticker_data_service.logger") as mock_logger:
            await ticker_service.get_ticker_history("AAPL", interval="1d", period="6mo")

            # Should log cache hit
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any("Cache hit" in str(call) for call in log_calls)


class TestTickerDataServiceYfinance:
    """Test suite for TickerDataService yfinance integration."""

    @pytest.fixture
    def mock_redis_cache(self):
        """Create mock Redis cache for testing."""
        cache = Mock(spec=RedisCache)
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock(return_value=None)
        return cache

    @pytest.fixture
    def ticker_service(self, mock_redis_cache):
        """Create TickerDataService instance with mocked dependencies."""
        return TickerDataService(mock_redis_cache)

    @pytest.mark.asyncio
    async def test_fetch_from_yfinance_success(self, ticker_service, mock_redis_cache):
        """Test successful data fetch from yfinance."""
        # Mock yfinance response
        mock_df = pd.DataFrame(
            {
                "Open": [150.0, 151.0, 152.0],
                "High": [152.0, 153.0, 154.0],
                "Low": [149.0, 150.0, 151.0],
                "Close": [151.0, 152.0, 153.0],
                "Volume": [1000000, 1100000, 1200000],
            }
        )

        with patch("yfinance.Ticker") as mock_ticker_class:
            mock_ticker = Mock()
            mock_ticker.history.return_value = mock_df
            mock_ticker_class.return_value = mock_ticker

            result = await ticker_service.get_ticker_history(
                "AAPL", interval="1d", start_date="2024-01-01", end_date="2024-01-03"
            )

            # Should return fetched data
            assert not result.empty
            assert len(result) == 3
            assert "Open" in result.columns
            assert result["Open"].iloc[0] == 150.0

            # Should cache the result
            assert mock_redis_cache.set.called

    @pytest.mark.asyncio
    async def test_fetch_from_yfinance_empty_response(
        self, ticker_service, mock_redis_cache
    ):
        """Test handling of empty yfinance response."""
        with patch("yfinance.Ticker") as mock_ticker_class:
            mock_ticker = Mock()
            mock_ticker.history.return_value = pd.DataFrame()
            mock_ticker_class.return_value = mock_ticker

            result = await ticker_service.get_ticker_history(
                "INVALID", interval="1d", period="6mo"
            )

            # Should return empty DataFrame
            assert result.empty
            # Should not cache empty results
            assert not mock_redis_cache.set.called

    @pytest.mark.asyncio
    async def test_fetch_from_yfinance_exception(
        self, ticker_service, mock_redis_cache
    ):
        """Test handling of yfinance exceptions."""
        with patch("yfinance.Ticker") as mock_ticker_class:
            mock_ticker_class.side_effect = Exception("API error")

            result = await ticker_service.get_ticker_history(
                "AAPL", interval="1d", period="6mo"
            )

            # Should return empty DataFrame on error
            assert result.empty
            # Should not cache errors
            assert not mock_redis_cache.set.called

    @pytest.mark.asyncio
    async def test_interval_mapping(self, ticker_service, mock_redis_cache):
        """Test interval is correctly mapped to yfinance format."""
        mock_df = pd.DataFrame({"Close": [150.0]})

        with patch("yfinance.Ticker") as mock_ticker_class:
            mock_ticker = Mock()
            mock_ticker.history.return_value = mock_df
            mock_ticker_class.return_value = mock_ticker

            await ticker_service.get_ticker_history("AAPL", interval="1d", period="5d")

            # Verify yfinance was called with correct interval
            call_kwargs = mock_ticker.history.call_args[1]
            assert call_kwargs["interval"] == "1d"

    @pytest.mark.asyncio
    async def test_cache_and_fetch_integration(self, ticker_service, mock_redis_cache):
        """Test full integration: miss -> fetch -> cache -> hit."""
        mock_df = pd.DataFrame({"Close": [150.0, 151.0]})

        with patch("yfinance.Ticker") as mock_ticker_class:
            mock_ticker = Mock()
            mock_ticker.history.return_value = mock_df
            mock_ticker_class.return_value = mock_ticker

            # First call: cache miss, fetch from yfinance
            mock_redis_cache.get.return_value = None
            result1 = await ticker_service.get_ticker_history(
                "AAPL", interval="1d", start_date="2024-01-01", end_date="2024-01-02"
            )

            assert not result1.empty
            assert len(result1) == 2
            # Should have cached the result
            assert mock_redis_cache.set.called

            # Verify cache key and TTL
            call_args, call_kwargs = mock_redis_cache.set.call_args
            cache_key, cached_data = call_args
            assert cache_key == "ticker_data:AAPL:2024-01-01:2024-01-02:1d"
            assert "ttl_seconds" in call_kwargs
            # Historical data (not today): should be 3600 * 8 = 28800
            assert call_kwargs["ttl_seconds"] == 28800

    @pytest.mark.asyncio
    async def test_yfinance_uses_start_end_dates(
        self, ticker_service, mock_redis_cache
    ):
        """Test yfinance is called with normalized start/end dates."""
        mock_df = pd.DataFrame({"Close": [150.0]})

        with patch("yfinance.Ticker") as mock_ticker_class:
            mock_ticker = Mock()
            mock_ticker.history.return_value = mock_df
            mock_ticker_class.return_value = mock_ticker

            # Use period, which should be converted to dates
            with patch(
                "src.core.data.ticker_data_service.DateUtils.period_to_date_range"
            ) as mock_convert:
                mock_convert.return_value = ("2024-04-03", "2024-10-03")

                await ticker_service.get_ticker_history(
                    "AAPL", interval="1d", period="6mo"
                )

                # Verify yfinance was called with start/end, NOT period
                call_kwargs = mock_ticker.history.call_args[1]
                assert "start" in call_kwargs
                assert "end" in call_kwargs
                assert call_kwargs["start"] == "2024-04-03"
                assert call_kwargs["end"] == "2024-10-03"
                # Should NOT pass period to yfinance
                assert "period" not in call_kwargs
