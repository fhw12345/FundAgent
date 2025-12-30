"""
Data Manager - Single source of truth for all data access.

The DataManager provides a unified interface for:
- Market OHLCV data (with smart caching based on granularity)
- Macro indicators (Treasury yields, IPO calendar)
- News sentiment
- Computed insights

Key Features:
- Automatic caching with TTL based on data type
- No caching for real-time/intraday data
- Pre-fetch pattern for shared data
- Parallel fetching with asyncio.gather
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

import pandas as pd
import structlog

from .cache import CacheOperations
from .keys import CacheKeys
from .types import (
    DataFetchError,
    Granularity,
    IPOData,
    NewsData,
    OHLCVData,
    OptionContract,
    QuoteData,
    SharedDataContext,
    TreasuryData,
)

logger = structlog.get_logger(__name__)


class DataManager:
    """
    Single source of truth for all data access in the application.

    All data consumers (charts, AI tools, insights, analysis) should
    use this class instead of calling services directly.

    Cache Strategy:
    - Intraday (1min-15min): NO CACHE - always fresh
    - 30min-60min: Short TTL (5-15 min)
    - Daily+: Standard TTL (1-4 hours)
    - Macro data: 1-24 hour TTL based on update frequency
    """

    # TTL constants (seconds)
    TTL_TREASURY = 3600  # 1 hour
    TTL_NEWS = 3600  # 1 hour
    TTL_IPO = 86400  # 24 hours
    TTL_INSIGHTS = 86400  # 24 hours
    TTL_QUOTE = 300  # 5 minutes (real-time quotes)
    TTL_OPTIONS = 3600  # 1 hour (options chains - daily data)

    def __init__(
        self,
        redis_cache: Any,
        alpha_vantage_service: Any,
    ):
        """
        Initialize the Data Manager.

        Args:
            redis_cache: RedisCache instance for caching
            alpha_vantage_service: AlphaVantageMarketDataService for API calls
        """
        self._cache = CacheOperations(redis_cache)
        self._av_service = alpha_vantage_service
        logger.info("data_manager_initialized")

    # =========================================================================
    # Market Data (OHLCV)
    # =========================================================================

    async def get_ohlcv(
        self,
        symbol: str,
        granularity: str | Granularity,
        outputsize: str = "compact",
    ) -> list[OHLCVData]:
        """
        Get OHLCV bars for a symbol.

        Caching:
        - 1min/5min/15min: NO CACHE (returns fresh data)
        - 30min/60min: 5-15 min TTL
        - daily/weekly/monthly: 1-4 hour TTL

        Args:
            symbol: Stock symbol (e.g., "AAPL")
            granularity: Time granularity ("daily", "1min", etc.)
            outputsize: "compact" (100 points) or "full" (all data)

        Returns:
            List of OHLCVData objects, newest first

        Raises:
            DataFetchError: If fetch fails
        """
        # Normalize granularity
        if isinstance(granularity, str):
            try:
                gran = Granularity(granularity.lower())
            except ValueError:
                gran = Granularity.DAILY
        else:
            gran = granularity

        symbol = symbol.upper()
        cache_key = CacheKeys.market(gran.value, symbol)

        # Skip cache for intraday
        if gran.is_intraday:
            logger.debug("ohlcv_no_cache", symbol=symbol, granularity=gran.value)
            return await self._fetch_ohlcv(symbol, gran, outputsize)

        # Try cache first
        async def fetch_func():
            data = await self._fetch_ohlcv(symbol, gran, outputsize)
            return [d.to_dict() for d in data]

        cached = await self._cache.get_with_fetch(
            cache_key, fetch_func, gran.ttl_seconds
        )

        if cached is None:
            raise DataFetchError(f"Failed to fetch OHLCV for {symbol}", "market")

        return [OHLCVData.from_dict(d) for d in cached]

    async def _fetch_ohlcv(
        self,
        symbol: str,
        granularity: Granularity,
        outputsize: str,
    ) -> list[OHLCVData]:
        """Internal: Fetch OHLCV from Alpha Vantage."""
        try:
            if granularity.is_intraday or granularity in (
                Granularity.MIN_30,
                Granularity.MIN_60,
            ):
                # Intraday API
                df = await self._av_service.get_intraday_bars(
                    symbol=symbol,
                    interval=granularity.value,
                    outputsize=outputsize,
                )
            else:
                # Daily/Weekly/Monthly API
                method_map = {
                    Granularity.DAILY: self._av_service.get_daily_bars,
                    Granularity.WEEKLY: self._av_service.get_weekly_bars,
                    Granularity.MONTHLY: self._av_service.get_monthly_bars,
                }
                method = method_map.get(granularity, self._av_service.get_daily_bars)
                df = await method(symbol=symbol, outputsize=outputsize)

            return self._dataframe_to_ohlcv(df)

        except Exception as e:
            logger.error(
                "ohlcv_fetch_failed",
                symbol=symbol,
                granularity=granularity.value,
                error=str(e),
            )
            raise DataFetchError(str(e), "alpha_vantage") from e

    def _dataframe_to_ohlcv(self, df: pd.DataFrame) -> list[OHLCVData]:
        """Convert pandas DataFrame to list of OHLCVData."""
        if df is None or df.empty:
            return []

        result = []
        for idx, row in df.iterrows():
            # Handle both timezone-aware and naive datetimes
            if isinstance(idx, pd.Timestamp):
                dt = idx.to_pydatetime()
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
            else:
                dt = datetime.fromisoformat(str(idx))

            result.append(
                OHLCVData(
                    date=dt,
                    open=float(row.get("Open", row.get("open", 0))),
                    high=float(row.get("High", row.get("high", 0))),
                    low=float(row.get("Low", row.get("low", 0))),
                    close=float(row.get("Close", row.get("close", 0))),
                    volume=int(row.get("Volume", row.get("volume", 0))),
                )
            )

        # Sort newest first
        result.sort(key=lambda x: x.date, reverse=True)
        return result

    # =========================================================================
    # Macro Data (Treasury, IPO)
    # =========================================================================

    async def get_treasury(
        self,
        maturity: str,
        interval: str = "daily",
    ) -> list[TreasuryData]:
        """
        Get treasury yield data.

        Args:
            maturity: Treasury maturity ("2y", "10y", "5y", etc.)
            interval: Data interval ("daily", "weekly", "monthly")

        Returns:
            List of TreasuryData objects, newest first

        Raises:
            DataFetchError: If fetch fails
        """
        # Normalize maturity format
        maturity_normalized = maturity.lower().replace("year", "y")
        cache_key = CacheKeys.treasury(maturity_normalized)

        async def fetch_func():
            data = await self._fetch_treasury(maturity, interval)
            return [d.to_dict() for d in data]

        cached = await self._cache.get_with_fetch(
            cache_key, fetch_func, self.TTL_TREASURY
        )

        if cached is None:
            raise DataFetchError(f"Failed to fetch treasury {maturity}", "macro")

        return [TreasuryData.from_dict(d) for d in cached]

    async def _fetch_treasury(self, maturity: str, interval: str) -> list[TreasuryData]:
        """Internal: Fetch treasury from Alpha Vantage."""
        try:
            # Map short maturity to API format
            maturity_map = {
                "2y": "2year",
                "5y": "5year",
                "10y": "10year",
                "30y": "30year",
                "3m": "3month",
            }
            api_maturity = maturity_map.get(maturity.lower(), maturity.lower())

            df = await self._av_service.get_treasury_yield(
                maturity=api_maturity, interval=interval
            )

            if df is None or df.empty:
                return []

            result = []
            for idx, row in df.iterrows():
                if isinstance(idx, pd.Timestamp):
                    dt = idx.to_pydatetime()
                else:
                    dt = datetime.fromisoformat(str(idx))

                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)

                result.append(
                    TreasuryData(
                        date=dt,
                        yield_value=float(row.get("value", row.iloc[0])),
                        maturity=maturity.lower(),
                    )
                )

            # Sort newest first
            result.sort(key=lambda x: x.date, reverse=True)
            return result

        except Exception as e:
            logger.error("treasury_fetch_failed", maturity=maturity, error=str(e))
            raise DataFetchError(str(e), "alpha_vantage") from e

    async def get_ipo_calendar(self) -> list[IPOData]:
        """
        Get IPO calendar for upcoming IPOs.

        Returns:
            List of IPOData objects for upcoming IPOs

        Raises:
            DataFetchError: If fetch fails
        """
        cache_key = CacheKeys.ipo_calendar()

        async def fetch_func():
            data = await self._fetch_ipo_calendar()
            return [d.to_dict() for d in data]

        cached = await self._cache.get_with_fetch(cache_key, fetch_func, self.TTL_IPO)

        if cached is None:
            return []  # IPO calendar can be empty

        return [IPOData.from_dict(d) for d in cached]

    async def _fetch_ipo_calendar(self) -> list[IPOData]:
        """Internal: Fetch IPO calendar from Alpha Vantage."""
        try:
            # Check if method exists on service
            if not hasattr(self._av_service, "get_ipo_calendar"):
                logger.warning("ipo_calendar_not_available")
                return []

            df = await self._av_service.get_ipo_calendar()

            if df is None or df.empty:
                return []

            result = []
            for _, row in df.iterrows():
                # Parse IPO date
                ipo_date = row.get("ipoDate", row.get("date", ""))
                if not ipo_date:
                    continue

                try:
                    dt = pd.to_datetime(ipo_date).to_pydatetime()
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=UTC)
                except Exception:
                    continue

                # Parse price range
                price_low = None
                price_high = None
                price_range = row.get("priceRangeLow", row.get("price", ""))
                if price_range:
                    try:
                        price_low = float(row.get("priceRangeLow", 0))
                        price_high = float(row.get("priceRangeHigh", 0))
                    except (ValueError, TypeError):
                        pass

                result.append(
                    IPOData(
                        date=dt,
                        name=str(row.get("name", row.get("company", ""))),
                        exchange=str(row.get("exchange", "")),
                        price_range_low=price_low,
                        price_range_high=price_high,
                        shares_offered=row.get("shares", None),
                    )
                )

            return result

        except Exception as e:
            logger.error("ipo_fetch_failed", error=str(e))
            raise DataFetchError(str(e), "alpha_vantage") from e

    # =========================================================================
    # News Sentiment
    # =========================================================================

    async def get_news_sentiment(
        self,
        topic: str | None = None,
        tickers: list[str] | None = None,
    ) -> list[NewsData]:
        """
        Get news sentiment data.

        Args:
            topic: News topic (e.g., "technology", "earnings")
            tickers: List of ticker symbols to filter by

        Returns:
            List of NewsData objects

        Raises:
            DataFetchError: If fetch fails
        """
        cache_key = CacheKeys.news_sentiment(topic or "general")

        async def fetch_func():
            data = await self._fetch_news_sentiment(topic, tickers)
            return [d.to_dict() for d in data]

        cached = await self._cache.get_with_fetch(cache_key, fetch_func, self.TTL_NEWS)

        if cached is None:
            return []

        return [NewsData.from_dict(d) for d in cached]

    async def _fetch_news_sentiment(
        self,
        topic: str | None,
        tickers: list[str] | None,
    ) -> list[NewsData]:
        """Internal: Fetch news sentiment from Alpha Vantage."""
        try:
            if not hasattr(self._av_service, "get_news_sentiment"):
                logger.warning("news_sentiment_not_available")
                return []

            data = await self._av_service.get_news_sentiment(
                tickers=",".join(tickers) if tickers else None,
                topics=topic,
            )

            if not data or "feed" not in data:
                return []

            result = []
            for item in data.get("feed", []):
                try:
                    # Parse time
                    time_str = item.get("time_published", "")
                    dt = datetime.strptime(time_str[:15], "%Y%m%dT%H%M%S")
                    dt = dt.replace(tzinfo=UTC)

                    # Get overall sentiment
                    sentiment = float(item.get("overall_sentiment_score", 0))

                    # Get ticker relevance (average if multiple)
                    relevance = 1.0
                    ticker_sentiment = item.get("ticker_sentiment", [])
                    if ticker_sentiment:
                        relevances = [
                            float(t.get("relevance_score", 0)) for t in ticker_sentiment
                        ]
                        relevance = sum(relevances) / len(relevances)

                    result.append(
                        NewsData(
                            date=dt,
                            sentiment_score=sentiment,
                            ticker_relevance=relevance,
                            title=item.get("title", ""),
                            source=item.get("source", ""),
                        )
                    )
                except Exception as e:
                    logger.debug("news_item_parse_error", error=str(e))
                    continue

            # Sort newest first
            result.sort(key=lambda x: x.date, reverse=True)
            return result

        except Exception as e:
            logger.error("news_fetch_failed", topic=topic, error=str(e))
            raise DataFetchError(str(e), "alpha_vantage") from e

    # =========================================================================
    # Quotes and Options (Story 2.6: Put/Call Ratio)
    # =========================================================================

    async def get_quote(self, symbol: str) -> QuoteData:
        """
        Get real-time quote for a symbol.

        Uses existing QuotesMixin.get_quote() from Alpha Vantage.
        Short TTL since prices change frequently.

        Args:
            symbol: Stock symbol (e.g., "NVDA")

        Returns:
            QuoteData object with current price, volume, etc.

        Raises:
            DataFetchError: If fetch fails
        """
        symbol = symbol.upper()
        cache_key = CacheKeys.quote(symbol)

        async def fetch_func() -> dict[str, Any]:
            data = await self._fetch_quote(symbol)
            return data.to_dict()

        cached = await self._cache.get_with_fetch(cache_key, fetch_func, self.TTL_QUOTE)

        if cached is None:
            raise DataFetchError(f"Failed to fetch quote for {symbol}", "market")

        # Type assertion: cached is dict from get_with_fetch
        if not isinstance(cached, dict):
            raise DataFetchError(f"Invalid cache data for {symbol}", "cache")

        return QuoteData.from_dict(cached)

    async def _fetch_quote(self, symbol: str) -> QuoteData:
        """Internal: Fetch quote from Alpha Vantage."""
        try:
            # Reuse existing get_quote() from QuotesMixin
            data = await self._av_service.get_quote(symbol)
            return QuoteData(
                symbol=data["symbol"],
                price=data["price"],
                volume=data["volume"],
                latest_trading_day=data["latest_trading_day"],
                previous_close=data["previous_close"],
                change=data["change"],
                change_percent=float(data["change_percent"]),
                open=data["open"],
                high=data["high"],
                low=data["low"],
            )
        except Exception as e:
            logger.error("quote_fetch_failed", symbol=symbol, error=str(e))
            raise DataFetchError(str(e), "alpha_vantage") from e

    async def get_options(self, symbol: str) -> list[OptionContract]:
        """
        Get options chain for a symbol.

        Fetches from Alpha Vantage HISTORICAL_OPTIONS endpoint.
        Returns previous trading day's options data.

        Args:
            symbol: Stock symbol (e.g., "NVDA")

        Returns:
            List of OptionContract objects

        Raises:
            DataFetchError: If fetch fails
        """
        symbol = symbol.upper()
        cache_key = CacheKeys.options(symbol)

        async def fetch_func() -> list[dict[str, Any]]:
            data = await self._fetch_options(symbol)
            return [d.to_dict() for d in data]

        cached = await self._cache.get_with_fetch(
            cache_key, fetch_func, self.TTL_OPTIONS
        )

        if cached is None:
            return []  # Options data may not be available

        # Type assertion: cached is list from get_with_fetch
        if not isinstance(cached, list):
            return []

        return [OptionContract.from_dict(d) for d in cached]

    async def _fetch_options(self, symbol: str) -> list[OptionContract]:
        """Internal: Fetch options chain from Alpha Vantage."""
        try:
            if not hasattr(self._av_service, "get_historical_options"):
                logger.warning("options_endpoint_not_available")
                return []

            data = await self._av_service.get_historical_options(symbol)

            if not data or "data" not in data:
                return []

            result = []
            for item in data.get("data", []):
                try:
                    result.append(
                        OptionContract(
                            contract_id=item.get("contractID", ""),
                            symbol=symbol,
                            expiration=datetime.strptime(
                                item.get("expiration", ""), "%Y-%m-%d"
                            ),
                            strike=float(item.get("strike", 0)),
                            option_type=item.get("type", "").lower(),
                            last_price=float(item.get("last", 0)),
                            bid=float(item.get("bid", 0)),
                            ask=float(item.get("ask", 0)),
                            volume=int(item.get("volume", 0) or 0),
                            open_interest=int(item.get("open_interest", 0) or 0),
                            implied_volatility=float(
                                item.get("implied_volatility", 0) or 0
                            ),
                            delta=(
                                float(item.get("delta", 0))
                                if item.get("delta")
                                else None
                            ),
                        )
                    )
                except Exception as e:
                    logger.debug("options_item_parse_error", error=str(e))
                    continue

            logger.info(
                "options_fetched",
                symbol=symbol,
                contracts=len(result),
            )
            return result

        except Exception as e:
            logger.error("options_fetch_failed", symbol=symbol, error=str(e))
            raise DataFetchError(str(e), "alpha_vantage") from e

    # =========================================================================
    # Insights (Computed Data)
    # =========================================================================

    async def get_insights(
        self, category_id: str, suffix: str = "latest"
    ) -> dict | None:
        """
        Get computed insight data from cache.

        Args:
            category_id: Insight category (e.g., "ai_sector_risk")
            suffix: Key suffix ("latest", "trend", etc.)

        Returns:
            Cached insight data or None
        """
        cache_key = CacheKeys.insights(category_id, suffix)
        return await self._cache.get(cache_key)

    async def set_insights(
        self,
        category_id: str,
        data: dict,
        suffix: str = "latest",
        ttl: int | None = None,
    ) -> bool:
        """
        Store computed insight data in cache.

        Args:
            category_id: Insight category
            data: Insight data to cache
            suffix: Key suffix
            ttl: TTL in seconds (default: 24 hours)

        Returns:
            True if successful
        """
        cache_key = CacheKeys.insights(category_id, suffix)
        return await self._cache.set(cache_key, data, ttl or self.TTL_INSIGHTS)

    # =========================================================================
    # Pre-fetch Pattern (Shared Data)
    # =========================================================================

    async def prefetch_shared(
        self,
        symbols: list[str] | None = None,
        treasury_maturities: list[str] | None = None,
        include_news: bool = False,
        include_ipo: bool = False,
    ) -> SharedDataContext:
        """
        Pre-fetch shared data in parallel.

        Use this to fetch data that will be used by multiple
        metric calculations, ensuring each data source is
        fetched only once.

        Example:
            context = await dm.prefetch_shared(
                symbols=["NVDA", "MSFT", "AMD"],
                treasury_maturities=["2y", "10y"],
            )
            # Now use context.get_treasury("2y") in multiple metrics
            # without duplicate API calls

        Args:
            symbols: Stock symbols to fetch OHLCV for
            treasury_maturities: Treasury maturities to fetch
            include_news: Whether to fetch news sentiment
            include_ipo: Whether to fetch IPO calendar

        Returns:
            SharedDataContext with all fetched data
        """
        context = SharedDataContext()
        tasks = []
        task_keys = []

        # Queue OHLCV tasks
        for symbol in symbols or []:
            tasks.append(self.get_ohlcv(symbol, "daily"))
            task_keys.append(("ohlcv", symbol.upper()))

        # Queue treasury tasks
        for maturity in treasury_maturities or []:
            tasks.append(self.get_treasury(maturity))
            task_keys.append(("treasury", maturity.lower()))

        # Queue news task
        if include_news:
            tasks.append(self.get_news_sentiment(topic="technology"))
            task_keys.append(("news", "technology"))

        # Queue IPO task
        if include_ipo:
            tasks.append(self.get_ipo_calendar())
            task_keys.append(("ipo", "calendar"))

        # Execute all in parallel
        if tasks:
            logger.info(
                "prefetch_started",
                symbols=symbols,
                treasury=treasury_maturities,
                total_tasks=len(tasks),
            )

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for (data_type, key), result in zip(task_keys, results, strict=False):
                if isinstance(result, Exception):
                    context.errors[f"{data_type}:{key}"] = str(result)
                    logger.warning(
                        "prefetch_task_failed",
                        data_type=data_type,
                        key=key,
                        error=str(result),
                    )
                elif data_type == "ohlcv":
                    context.ohlcv[key] = result
                elif data_type == "treasury":
                    context.treasury[key] = result
                elif data_type == "news":
                    context.news[key] = result
                elif data_type == "ipo":
                    context.ipo = result

            logger.info(
                "prefetch_completed",
                ohlcv_count=len(context.ohlcv),
                treasury_count=len(context.treasury),
                errors=len(context.errors),
            )

        return context

    # =========================================================================
    # Cache Management
    # =========================================================================

    async def invalidate_market(
        self, symbol: str | None = None, granularity: str | None = None
    ) -> int:
        """
        Invalidate market data cache.

        Args:
            symbol: Symbol to invalidate, or all if None
            granularity: Granularity to invalidate, or all if None

        Returns:
            Number of keys invalidated
        """
        if symbol and granularity:
            key = CacheKeys.market(granularity, symbol)
            deleted = await self._cache.delete(key)
            return 1 if deleted else 0
        elif symbol:
            pattern = f"{CacheKeys.MARKET}:*:{symbol.upper()}"
        elif granularity:
            pattern = CacheKeys.pattern(CacheKeys.MARKET, granularity)
        else:
            pattern = CacheKeys.pattern(CacheKeys.MARKET)

        return await self._cache.invalidate_pattern(pattern)

    async def invalidate_insights(self, category_id: str | None = None) -> int:
        """
        Invalidate insights cache.

        Args:
            category_id: Category to invalidate, or all if None

        Returns:
            Number of keys invalidated
        """
        if category_id:
            pattern = f"{CacheKeys.INSIGHTS}:{category_id.lower()}:*"
        else:
            pattern = CacheKeys.pattern(CacheKeys.INSIGHTS)

        return await self._cache.invalidate_pattern(pattern)
