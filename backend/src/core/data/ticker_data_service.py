"""
Centralized ticker data service with intelligent caching.

This service eliminates redundant API calls by providing shared ticker data
to all analyzers through a unified caching layer.
"""

import pandas as pd
import structlog
import yfinance as yf

from ...database.redis import RedisCache
from ..utils.date_utils import DateUtils
from ..utils.yfinance_utils import map_timeframe_to_yfinance_interval

logger = structlog.get_logger()


class TickerDataService:
    """
    Centralized service for fetching and caching raw ticker data.

    Provides unified interface to ticker data with intelligent caching
    to prevent redundant yfinance API calls across analyzers.
    """

    def __init__(self, redis_cache: RedisCache):
        """
        Initialize ticker data service.

        Args:
            redis_cache: Redis cache instance for data storage
        """
        self.redis_cache = redis_cache
        self.default_ttl = 1800  # 30 minutes default TTL

    async def get_ticker_history(
        self,
        symbol: str,
        interval: str = "1d",
        period: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """
        Get ticker history with unified caching.

        Args:
            symbol: Stock symbol (e.g., "AAPL")
            interval: Data interval ("1m", "1h", "1d", "1wk", "1mo")
            period: Relative period ("1d", "5d", "1mo", "6mo", "1y", etc.)
                   OR
            start_date: Start date ("YYYY-MM-DD") - requires end_date
            end_date: End date ("YYYY-MM-DD") - requires start_date

        Returns:
            DataFrame with OHLCV data

        Raises:
            ValueError: If both period and date range are provided or parameters are invalid
        """
        logger.info(
            "Ticker data request",
            symbol=symbol,
            interval=interval,
            period=period,
            start_date=start_date,
            end_date=end_date,
        )

        # Validate parameters
        self._validate_parameters(period, start_date, end_date)

        # Normalize to start/end dates for consistent caching
        normalized_start, normalized_end = self._normalize_to_date_range(
            period, start_date, end_date
        )

        # Generate cache key
        cache_key = self._generate_cache_key(
            symbol, normalized_start, normalized_end, interval
        )

        logger.info(
            "Normalized ticker request",
            symbol=symbol,
            cache_key=cache_key,
            start_date=normalized_start,
            end_date=normalized_end,
        )

        # Check cache first
        cached_data = await self.redis_cache.get(cache_key)
        if cached_data is not None:
            logger.info("Cache hit", cache_key=cache_key)
            # Deserialize DataFrame from cached dict
            return pd.DataFrame(cached_data)

        logger.info("Cache miss", cache_key=cache_key)

        # Fetch from yfinance
        df = await self._fetch_from_yfinance(
            symbol, interval, normalized_start, normalized_end
        )

        # Cache the result if non-empty
        if not df.empty:
            ttl = self._calculate_ttl(interval, normalized_start, normalized_end)
            # Serialize DataFrame to dict for Redis storage
            await self.redis_cache.set(cache_key, df.to_dict(), ttl_seconds=ttl)
            logger.info(
                "Cached ticker data", cache_key=cache_key, ttl=ttl, rows=len(df)
            )

        return df

    def _validate_parameters(
        self, period: str | None, start_date: str | None, end_date: str | None
    ) -> None:
        """Validate input parameters."""
        # Cannot specify both period and date range
        if period and (start_date or end_date):
            raise ValueError(
                "Cannot specify both 'period' and date range (start_date/end_date)"
            )

        # Date range requires both start and end
        if (start_date and not end_date) or (end_date and not start_date):
            raise ValueError(
                "Both start_date and end_date are required for date range queries"
            )

        # Validate date format and logic if provided
        if start_date and end_date:
            DateUtils.validate_date_range(start_date, end_date)

    def _normalize_to_date_range(
        self, period: str | None, start_date: str | None, end_date: str | None
    ) -> tuple[str, str]:
        """
        Normalize all requests to start/end date format for consistent caching.

        Returns:
            Tuple of (start_date, end_date) as YYYY-MM-DD strings
        """
        if period:
            # Convert period to date range
            return DateUtils.period_to_date_range(period)
        elif start_date and end_date:
            # Already in date range format
            return start_date, end_date
        else:
            # Default to 6mo if nothing specified
            return DateUtils.period_to_date_range("6mo")

    def _generate_cache_key(
        self, symbol: str, start_date: str, end_date: str, interval: str
    ) -> str:
        """
        Generate unified cache key using normalized dates.

        Args:
            symbol: Stock symbol (normalized to uppercase)
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            interval: Data interval

        Returns:
            Cache key string for Redis storage
        """
        normalized_symbol = symbol.upper().strip()
        return f"ticker_data:{normalized_symbol}:{start_date}:{end_date}:{interval}"

    def _calculate_ttl(self, interval: str, start_date: str, end_date: str) -> int:
        """
        Calculate appropriate TTL based on data characteristics.

        Args:
            interval: Data interval
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            TTL in seconds
        """
        from datetime import datetime

        # Base TTL by interval
        base_ttl_map = {
            "1m": 60,  # 1 minute data - cache for 1 minute
            "5m": 300,  # 5 minute data - cache for 5 minutes
            "1h": 1800,  # 1 hour data - cache for 30 minutes
            "1d": 3600,  # Daily data - cache for 1 hour
            "1wk": 7200,  # Weekly data - cache for 2 hours
            "1mo": 14400,  # Monthly data - cache for 4 hours
        }

        base_ttl = base_ttl_map.get(interval, self.default_ttl)

        # Historical data can be cached longer
        today = datetime.now().date().strftime("%Y-%m-%d")
        is_current_data = end_date == today

        if not is_current_data:
            # Historical data cache 8x longer
            base_ttl *= 8

        return base_ttl

    async def _fetch_from_yfinance(
        self, symbol: str, interval: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """
        Fetch ticker data from yfinance API.

        Args:
            symbol: Stock symbol
            interval: Data interval
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            DataFrame with OHLCV data, or empty DataFrame on error
        """
        try:
            # Map interval to yfinance format
            yf_interval = map_timeframe_to_yfinance_interval(interval)

            logger.info(
                "Fetching from yfinance",
                symbol=symbol,
                interval=interval,
                yf_interval=yf_interval,
                start=start_date,
                end=end_date,
            )

            # Fetch data using yfinance
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date, interval=yf_interval)

            if df.empty:
                logger.warning(
                    "No data returned from yfinance",
                    symbol=symbol,
                    interval=interval,
                    start=start_date,
                    end=end_date,
                )
                return pd.DataFrame()

            logger.info(
                "Successfully fetched from yfinance",
                symbol=symbol,
                rows=len(df),
                columns=list(df.columns),
            )

            return df

        except Exception as e:
            logger.error(
                "Error fetching from yfinance",
                symbol=symbol,
                interval=interval,
                error=str(e),
                exc_info=True,
            )
            return pd.DataFrame()
