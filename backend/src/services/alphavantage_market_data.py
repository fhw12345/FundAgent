"""
Alpha Vantage market data service.
Provides symbol search, quotes, and historical data using Alpha Vantage API.
"""

import re
from datetime import datetime, timedelta
from typing import Any

import httpx
import pandas as pd
import structlog

from ..core.config import Settings

logger = structlog.get_logger()


class AlphaVantageMarketDataService:
    """
    Market data service using Alpha Vantage API exclusively.

    Features:
    - Symbol search (SYMBOL_SEARCH)
    - Real-time quotes (GLOBAL_QUOTE)
    - Intraday data with pre/post market (TIME_SERIES_INTRADAY_EXTENDED)
    - Daily/Weekly/Monthly data (TIME_SERIES_DAILY/WEEKLY/MONTHLY)

    Performance optimizations:
    - Connection pooling with persistent HTTP client
    - Pre-compiled regex patterns for API key sanitization
    """

    # Class-level compiled regex pattern for API key sanitization
    _API_KEY_PATTERN = re.compile(
        r'(API[\s_-]?key[^A-Z0-9]*)[A-Z0-9]{16,}',
        flags=re.IGNORECASE
    )

    def __init__(self, settings: Settings):
        """Initialize service with Alpha Vantage API key and persistent HTTP client."""
        self.settings = settings
        self.api_key = settings.alpha_vantage_api_key
        self.base_url = "https://www.alphavantage.co/query"

        # Persistent HTTP client with connection pooling
        self.client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(
                max_keepalive_connections=5,
                max_connections=10,
                keepalive_expiry=30.0,
            )
        )

        if not self.api_key:
            logger.warning("Alpha Vantage API key not configured")

        logger.info(
            "Alpha Vantage market data service initialized",
            api_key_configured=bool(self.api_key),
            connection_pool_enabled=True,
        )

    async def close(self):
        """Close HTTP client and cleanup resources."""
        await self.client.aclose()
        logger.info("Alpha Vantage market data service closed")

    def _sanitize_text(self, text: str) -> str:
        """Remove API key from text strings before logging or raising exceptions."""
        # Use pre-compiled regex pattern (class-level optimization)
        if "API key" in text or "api key" in text or "apikey" in text:
            text = self._API_KEY_PATTERN.sub(r'\1****', text)
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

    async def search_symbols(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """
        Search for stock symbols using Alpha Vantage SYMBOL_SEARCH.

        Args:
            query: Search query (symbol or company name)
            limit: Maximum number of results

        Returns:
            List of search results with symbol, name, type, region, currency
        """
        try:
            response = await self.client.get(
                self.base_url,
                params={
                    "function": "SYMBOL_SEARCH",
                    "keywords": query,
                    "apikey": self.api_key,
                },
            )

            if response.status_code != 200:
                sanitized_text = self._sanitize_text(response.text)
                raise ValueError(
                    f"Alpha Vantage API error: {response.status_code} - {sanitized_text}"
                )

            data = response.json()

            if "bestMatches" not in data:
                # Sanitize response to avoid logging API keys
                sanitized = self._sanitize_response(data)
                logger.warning("No matches found", query=query, response=sanitized)
                return []

            matches = data["bestMatches"][:limit]

            # Format results to match API contract
            results = []
            for match in matches:
                match_score = float(match.get("9. matchScore", "0.0"))
                results.append({
                    "symbol": match.get("1. symbol", ""),
                    "name": match.get("2. name", ""),
                    "type": match.get("3. type", ""),
                    "exchange": match.get("4. region", ""),  # Use region as exchange
                    "match_type": "exact_symbol" if match_score >= 0.9 else "fuzzy",
                    "confidence": match_score,
                })

            logger.info(
                "Symbol search completed",
                query=query,
                results_count=len(results),
            )

            return results

        except Exception as e:
            logger.error("Symbol search failed", query=query, error=str(e))
            raise

    async def get_quote(self, symbol: str) -> dict[str, Any]:
        """
        Get real-time quote using Alpha Vantage GLOBAL_QUOTE.

        Args:
            symbol: Stock symbol

        Returns:
            Dict with price, volume, change, etc.
        """
        try:
            response = await self.client.get(
                self.base_url,
                params={
                    "function": "GLOBAL_QUOTE",
                    "symbol": symbol,
                    "apikey": self.api_key,
                },
            )

            if response.status_code != 200:
                sanitized_text = self._sanitize_text(response.text)
                raise ValueError(
                    f"Alpha Vantage API error: {response.status_code} - {sanitized_text}"
                )

            data = response.json()

            if "Global Quote" not in data or not data["Global Quote"]:
                raise ValueError(f"No quote data for symbol: {symbol}")

            quote = data["Global Quote"]

            result = {
                "symbol": quote.get("01. symbol", symbol),
                "price": float(quote.get("05. price", 0)),
                "volume": int(quote.get("06. volume", 0)),
                "latest_trading_day": quote.get("07. latest trading day", ""),
                "previous_close": float(quote.get("08. previous close", 0)),
                "change": float(quote.get("09. change", 0)),
                "change_percent": quote.get("10. change percent", "0%").rstrip("%"),
                "open": float(quote.get("02. open", 0)),
                "high": float(quote.get("03. high", 0)),
                "low": float(quote.get("04. low", 0)),
            }

            logger.info(
                "Quote fetched",
                symbol=symbol,
                price=result["price"],
            )

            return result

        except Exception as e:
            logger.error("Quote fetch failed", symbol=symbol, error=str(e))
            raise

    async def get_intraday_bars(
        self,
        symbol: str,
        interval: str = "1min",
        outputsize: str = "compact",
    ) -> pd.DataFrame:
        """
        Get intraday bars with extended hours using TIME_SERIES_INTRADAY.

        Args:
            symbol: Stock symbol
            interval: 1min, 5min, 15min, 30min, 60min
            outputsize: compact (latest 100 points) or full (full-length)

        Returns:
            DataFrame with Open, High, Low, Close, Volume columns
        """
        try:
            response = await self.client.get(
                self.base_url,
                params={
                    "function": "TIME_SERIES_INTRADAY",
                    "symbol": symbol,
                    "interval": interval,
                    "outputsize": outputsize,
                    "extended_hours": "true",  # Include pre/post market
                    "apikey": self.api_key,
                },
            )

            if response.status_code != 200:
                sanitized_text = self._sanitize_text(response.text)
                raise ValueError(
                    f"Alpha Vantage API error: {response.status_code} - {sanitized_text}"
                )

            data = response.json()

            # Find the time series key
            ts_key = f"Time Series ({interval})"
            if ts_key not in data:
                raise ValueError(f"No intraday data for symbol: {symbol}")

            time_series = data[ts_key]

            # Convert to DataFrame
            df_data = []
            for timestamp, values in time_series.items():
                df_data.append({
                    "timestamp": pd.to_datetime(timestamp),
                    "Open": float(values["1. open"]),
                    "High": float(values["2. high"]),
                    "Low": float(values["3. low"]),
                    "Close": float(values["4. close"]),
                    "Volume": int(values["5. volume"]),
                })

            df = pd.DataFrame(df_data)
            df.set_index("timestamp", inplace=True)
            df.sort_index(inplace=True)  # Ensure chronological order

            logger.info(
                "Intraday bars fetched",
                symbol=symbol,
                interval=interval,
                bars_count=len(df),
            )

            return df

        except Exception as e:
            logger.error(
                "Intraday bars fetch failed",
                symbol=symbol,
                interval=interval,
                error=str(e),
            )
            raise

    async def get_daily_bars(
        self,
        symbol: str,
        outputsize: str = "compact",
    ) -> pd.DataFrame:
        """
        Get daily bars using TIME_SERIES_DAILY.

        Args:
            symbol: Stock symbol
            outputsize: compact (latest 100 days) or full (20+ years)

        Returns:
            DataFrame with Open, High, Low, Close, Volume columns
        """
        try:
            response = await self.client.get(
                self.base_url,
                params={
                    "function": "TIME_SERIES_DAILY",
                    "symbol": symbol,
                    "outputsize": outputsize,
                    "apikey": self.api_key,
                },
            )

            if response.status_code != 200:
                sanitized_text = self._sanitize_text(response.text)
                raise ValueError(
                    f"Alpha Vantage API error: {response.status_code} - {sanitized_text}"
                )

            data = response.json()

            if "Time Series (Daily)" not in data:
                raise ValueError(f"No daily data for symbol: {symbol}")

            time_series = data["Time Series (Daily)"]

            # Convert to DataFrame
            df_data = []
            for date, values in time_series.items():
                df_data.append({
                    "date": pd.to_datetime(date),
                    "Open": float(values["1. open"]),
                    "High": float(values["2. high"]),
                    "Low": float(values["3. low"]),
                    "Close": float(values["4. close"]),
                    "Volume": int(values["5. volume"]),
                })

            df = pd.DataFrame(df_data)
            df.set_index("date", inplace=True)
            df.sort_index(inplace=True)

            logger.info(
                "Daily bars fetched",
                symbol=symbol,
                bars_count=len(df),
            )

            return df

        except Exception as e:
            logger.error(
                "Daily bars fetch failed",
                symbol=symbol,
                error=str(e),
            )
            raise

    async def get_price_bars(
        self,
        symbol: str,
        interval: str = "1d",
        period: str = "6mo",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """
        Unified method to get price bars for any interval/period.

        Args:
            symbol: Stock symbol
            interval: 1m, 5m, 15m, 30m, 60m, 1d, 1w, 1M
            period: Relative period (1d, 5d, 1mo, 6mo, 1y, etc.) - ignored if dates provided
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            DataFrame with Open, High, Low, Close, Volume columns
        """
        try:
            # Map intervals to Alpha Vantage format
            if interval in ["1m", "5m", "15m", "30m", "60m"]:
                # Intraday
                av_interval = interval.replace("m", "min")
                df = await self.get_intraday_bars(symbol, av_interval, "full")
            elif interval in ["1d", "day"]:
                # Daily
                df = await self.get_daily_bars(symbol, "full")
            else:
                # Default to daily
                logger.warning(
                    f"Unsupported interval '{interval}', defaulting to daily",
                    symbol=symbol,
                )
                df = await self.get_daily_bars(symbol, "full")

            # Filter by date range if provided
            if start_date and end_date:
                start = pd.to_datetime(start_date)
                end = pd.to_datetime(end_date)
                df = df[(df.index >= start) & (df.index <= end)]

            return df

        except Exception as e:
            logger.error(
                "Price bars fetch failed",
                symbol=symbol,
                interval=interval,
                error=str(e),
            )
            raise
