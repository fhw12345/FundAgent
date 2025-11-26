"""
Alpha Vantage market data service.
Provides symbol search, quotes, and historical data using Alpha Vantage API.
"""

import asyncio
import re
from datetime import datetime, time
from typing import Any, Literal

import httpx
import pandas as pd
import structlog

from ..core.config import Settings

logger = structlog.get_logger()


def get_market_session(
    timestamp: pd.Timestamp,
) -> Literal["pre", "regular", "post", "closed"]:
    """
    Determine market session for a given timestamp (US Eastern Time).

    Market hours (ET):
    - Pre-market: 4:00 AM - 9:30 AM
    - Regular: 9:30 AM - 4:00 PM
    - Post-market: 4:00 PM - 8:00 PM
    - Closed: 8:00 PM - 4:00 AM, weekends

    Args:
        timestamp: Timestamp to check (should be in ET timezone)

    Returns:
        Market session: "pre", "regular", "post", or "closed"
    """
    # Convert to ET if not already
    if timestamp.tz is None:
        # Assume UTC, convert to ET
        timestamp = timestamp.tz_localize("UTC").tz_convert("America/New_York")
    elif str(timestamp.tz) != "America/New_York":
        timestamp = timestamp.tz_convert("America/New_York")

    # Check if weekend
    if timestamp.weekday() >= 5:  # Saturday=5, Sunday=6
        return "closed"

    time_of_day = timestamp.time()

    # Define session boundaries
    pre_start = time(4, 0)  # 4:00 AM
    regular_start = time(9, 30)  # 9:30 AM
    regular_end = time(16, 0)  # 4:00 PM
    post_end = time(20, 0)  # 8:00 PM

    if pre_start <= time_of_day < regular_start:
        return "pre"
    elif regular_start <= time_of_day < regular_end:
        return "regular"
    elif regular_end <= time_of_day < post_end:
        return "post"
    else:
        return "closed"


def validate_date_range(
    start_date: str | None,
    end_date: str | None,
    interval: str,
) -> tuple[bool, str | None]:
    """
    Validate date range based on interval constraints.

    Rules:
    - Intraday (1m, 1h): Must be today only (enforced in UI via market status)
    - Daily+ (1d, 1w, 1mo): No restrictions, any historical range allowed

    Args:
        start_date: Start date string (YYYY-MM-DD)
        end_date: End date string (YYYY-MM-DD)
        interval: Data interval (1m, 1h, 1d, etc.)

    Returns:
        (is_valid, error_message)
    """
    # If no custom dates provided, always valid (use defaults)
    if not start_date or not end_date:
        return True, None

    # Parse dates
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError as e:
        return False, f"Invalid date format: {e}. Use YYYY-MM-DD"

    # Validate start <= end
    if start > end:
        return False, "Start date must be before or equal to end date"

    # For intraday intervals, allow recent dates (last 30 days)
    # Show whatever data is available - market closed/pre/post hours data included
    intraday_intervals = ["1m", "1h", "60min"]
    if interval in intraday_intervals:
        # Get current date in Eastern Time
        now_et = pd.Timestamp.now(tz="America/New_York")
        today = now_et.date()

        # Allow dates within last 30 days (Alpha Vantage intraday limit)
        earliest_allowed = today - pd.Timedelta(days=30)

        if start.date() < earliest_allowed:
            return (
                False,
                f"Intraday data ({interval}) only available for last 30 days (since {earliest_allowed})",
            )

        if end.date() > today:
            return False, f"End date cannot be in the future (today is {today})"

    # Daily+ intervals: no restrictions
    return True, None


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
        r"(API[\s_-]?key[^A-Z0-9]*)[A-Z0-9]{16,}", flags=re.IGNORECASE
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
            ),
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
                results.append(
                    {
                        "symbol": match.get("1. symbol", ""),
                        "name": match.get("2. name", ""),
                        "type": match.get("3. type", ""),
                        "exchange": match.get(
                            "4. region", ""
                        ),  # Use region as exchange
                        "match_type": "exact_symbol" if match_score >= 0.9 else "fuzzy",
                        "confidence": match_score,
                    }
                )

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
            # GLOBAL_QUOTE with entitlement=delayed returns previous day's close during market hours
            # It will show today's close only after market closes
            response = await self.client.get(
                self.base_url,
                params={
                    "function": "GLOBAL_QUOTE",
                    "symbol": symbol,
                    "entitlement": "delayed",
                    "apikey": self.api_key,
                },
            )

            if response.status_code != 200:
                sanitized_text = self._sanitize_text(response.text)
                raise ValueError(
                    f"Alpha Vantage API error: {response.status_code} - {sanitized_text}"
                )

            data = response.json()

            # Handle both standard and delayed response formats
            # Standard: "Global Quote"
            # Delayed: "Global Quote - DATA DELAYED BY 15 MINUTES"
            quote_key = None
            for key in data.keys():
                if key.startswith("Global Quote"):
                    quote_key = key
                    break

            if not quote_key or not data[quote_key]:
                raise ValueError(f"No quote data for symbol: {symbol}")

            quote = data[quote_key]

            logger.info(
                "Quote API response parsed",
                symbol=symbol,
                quote_key=quote_key,
            )

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
                    "entitlement": "delayed",  # 15-minute delayed data (premium)
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
                df_data.append(
                    {
                        "timestamp": pd.to_datetime(timestamp),
                        "Open": float(values["1. open"]),
                        "High": float(values["2. high"]),
                        "Low": float(values["3. low"]),
                        "Close": float(values["4. close"]),
                        "Volume": int(values["5. volume"]),
                    }
                )

            df = pd.DataFrame(df_data)
            df.set_index("timestamp", inplace=True)
            df.sort_index(inplace=True)  # Ensure chronological order

            # Alpha Vantage returns intraday timestamps in US Eastern Time
            # Localize naive timestamps to ET for proper session detection
            if not df.empty and df.index.tz is None:
                df.index = df.index.tz_localize("America/New_York")

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

    async def get_intraday_bars_extended(
        self,
        symbol: str,
        interval: str = "1min",
        months: int = 3,
    ) -> pd.DataFrame:
        """
        Get extended intraday bars using TIME_SERIES_INTRADAY_EXTENDED (Premium feature).

        This endpoint provides up to 2 years of historical intraday data by fetching
        monthly slices. Each slice represents one month of data.

        Args:
            symbol: Stock symbol
            interval: 1min, 5min, 15min, 30min, 60min
            months: Number of recent months to fetch (1-24, default 3)

        Returns:
            DataFrame with Open, High, Low, Close, Volume columns

        Note:
            - Requires Premium API key
            - Each month is fetched as a separate "slice" (year1month1, year1month2, etc.)
            - year1month1 = most recent month, year2month1 = 13-24 months ago
            - Extended hours (pre/post market) included by default
        """
        try:
            if months < 1 or months > 24:
                raise ValueError("months must be between 1 and 24")

            # Prepare all API requests concurrently for better performance
            async def fetch_slice(
                month_offset: int,
            ) -> tuple[str, httpx.Response | None]:
                """Fetch a single month slice."""
                year = ((month_offset - 1) // 12) + 1
                month = ((month_offset - 1) % 12) + 1
                slice_name = f"year{year}month{month}"

                logger.info(
                    "Fetching extended intraday slice",
                    symbol=symbol,
                    interval=interval,
                    slice=slice_name,
                    month_offset=month_offset,
                )

                try:
                    response = await self.client.get(
                        self.base_url,
                        params={
                            "function": "TIME_SERIES_INTRADAY_EXTENDED",
                            "symbol": symbol,
                            "interval": interval,
                            "slice": slice_name,
                            "adjusted": "false",  # Raw prices
                            "apikey": self.api_key,
                        },
                    )
                    return slice_name, response
                except Exception as e:
                    logger.warning(
                        "Extended intraday slice fetch exception",
                        symbol=symbol,
                        slice=slice_name,
                        error=str(e),
                    )
                    return slice_name, None

            # Fetch all slices concurrently (3x faster for 3 months)
            tasks = [fetch_slice(i) for i in range(1, months + 1)]
            results = await asyncio.gather(*tasks)

            # Process all responses and parse CSV using pandas
            all_dataframes = []
            for slice_name, response in results:
                if response is None or response.status_code != 200:
                    if response is not None:
                        sanitized_text = self._sanitize_text(response.text)
                        logger.warning(
                            "Extended intraday slice fetch failed",
                            symbol=symbol,
                            slice=slice_name,
                            status=response.status_code,
                            error=sanitized_text,
                        )
                    continue

                # Check for API error messages before parsing
                response_text = response.text.strip()
                if (
                    not response_text
                    or "Error" in response_text
                    or "please see" in response_text
                ):
                    logger.warning(
                        "API error or no data in extended intraday slice",
                        symbol=symbol,
                        slice=slice_name,
                        response_preview=(
                            response_text[:200] if response_text else "empty"
                        ),
                    )
                    continue

                # Parse CSV using pandas (2-3x faster than manual parsing)
                try:
                    from io import StringIO

                    df_slice = pd.read_csv(
                        StringIO(response_text),
                        parse_dates=[0],  # First column is timestamp
                        index_col=0,  # Use timestamp as index
                        names=["timestamp", "Open", "High", "Low", "Close", "Volume"],
                        dtype={
                            "Open": float,
                            "High": float,
                            "Low": float,
                            "Close": float,
                            "Volume": int,
                        },
                        on_bad_lines="skip",  # Skip malformed lines
                    )

                    if not df_slice.empty:
                        all_dataframes.append(df_slice)
                    else:
                        logger.warning(
                            "No data in extended intraday slice",
                            symbol=symbol,
                            slice=slice_name,
                        )
                except Exception as e:
                    logger.warning(
                        "Failed to parse CSV for slice",
                        symbol=symbol,
                        slice=slice_name,
                        error=str(e),
                    )

            if not all_dataframes:
                error_msg = (
                    f"No extended intraday data retrieved for {symbol}. "
                    f"API Note: TIME_SERIES_INTRADAY_EXTENDED has been deprecated and merged into TIME_SERIES_INTRADAY."
                )
                logger.error(
                    "Extended endpoint failed - API deprecated",
                    symbol=symbol,
                    interval=interval,
                    months_requested=months,
                )
                raise ValueError(error_msg)

            # Combine all dataframes efficiently
            df = pd.concat(all_dataframes, axis=0)
            df.sort_index(inplace=True)  # Ensure chronological order

            # Remove duplicates (in case of overlapping slices)
            df = df[~df.index.duplicated(keep="first")]

            # Alpha Vantage returns intraday timestamps in US Eastern Time
            # Localize naive timestamps to ET for proper session detection
            if not df.empty and df.index.tz is None:
                df.index = df.index.tz_localize("America/New_York")

            logger.info(
                "Extended intraday bars fetched",
                symbol=symbol,
                interval=interval,
                bars_count=len(df),
                months_fetched=months,
                date_range=(
                    f"{df.index.min()} to {df.index.max()}" if not df.empty else "empty"
                ),
            )

            return df

        except Exception as e:
            logger.error(
                "Extended intraday bars fetch failed",
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
        Get daily bars using TIME_SERIES_DAILY_ADJUSTED (split-adjusted prices).

        Args:
            symbol: Stock symbol
            outputsize: compact (latest 100 days) or full (20+ years)

        Returns:
            DataFrame with Open, High, Low, Close, Volume columns (split-adjusted)
        """
        try:
            response = await self.client.get(
                self.base_url,
                params={
                    "function": "TIME_SERIES_DAILY_ADJUSTED",
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

            # DAILY_ADJUSTED returns data with different key name
            key = "Time Series (Daily)"
            if key not in data:
                raise ValueError(
                    f"No daily data for symbol: {symbol}. Keys: {list(data.keys())}"
                )

            time_series = data[key]

            # Convert to DataFrame
            # DAILY_ADJUSTED provides: adjusted close (field 5), dividend (7), split coeff (8)
            df_data = []
            for date, values in time_series.items():
                df_data.append(
                    {
                        "date": pd.to_datetime(date),
                        "Open": float(values["1. open"]),
                        "High": float(values["2. high"]),
                        "Low": float(values["3. low"]),
                        "Close": float(
                            values["5. adjusted close"]
                        ),  # Use adjusted close
                        "Volume": int(
                            values["6. volume"]
                        ),  # Volume is field 6 in DAILY_ADJUSTED
                    }
                )

            df = pd.DataFrame(df_data)
            df.set_index("date", inplace=True)
            df.sort_index(inplace=True)

            logger.info(
                "Daily bars fetched (split-adjusted)",
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

    async def get_weekly_bars(
        self,
        symbol: str,
        outputsize: str = "compact",
    ) -> pd.DataFrame:
        """
        Get weekly bars using TIME_SERIES_WEEKLY.

        Args:
            symbol: Stock symbol
            outputsize: compact (latest 100 weeks) or full (20+ years)

        Returns:
            DataFrame with Open, High, Low, Close, Volume columns
        """
        try:
            response = await self.client.get(
                self.base_url,
                params={
                    "function": "TIME_SERIES_WEEKLY",
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

            if "Weekly Time Series" not in data:
                raise ValueError(f"No weekly data for symbol: {symbol}")

            time_series = data["Weekly Time Series"]

            # Convert to DataFrame
            df_data = []
            for date, values in time_series.items():
                df_data.append(
                    {
                        "date": pd.to_datetime(date),
                        "Open": float(values["1. open"]),
                        "High": float(values["2. high"]),
                        "Low": float(values["3. low"]),
                        "Close": float(values["4. close"]),
                        "Volume": int(values["5. volume"]),
                    }
                )

            df = pd.DataFrame(df_data)
            df.set_index("date", inplace=True)
            df.sort_index(inplace=True)

            logger.info(
                "Weekly bars fetched",
                symbol=symbol,
                bars_count=len(df),
            )

            return df

        except Exception as e:
            logger.error(
                "Weekly bars fetch failed",
                symbol=symbol,
                error=str(e),
            )
            raise

    async def get_monthly_bars(
        self,
        symbol: str,
        outputsize: str = "compact",
    ) -> pd.DataFrame:
        """
        Get monthly bars using TIME_SERIES_MONTHLY.

        Args:
            symbol: Stock symbol
            outputsize: compact (latest 100 months) or full (20+ years)

        Returns:
            DataFrame with Open, High, Low, Close, Volume columns
        """
        try:
            response = await self.client.get(
                self.base_url,
                params={
                    "function": "TIME_SERIES_MONTHLY",
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

            if "Monthly Time Series" not in data:
                raise ValueError(f"No monthly data for symbol: {symbol}")

            time_series = data["Monthly Time Series"]

            # Convert to DataFrame
            df_data = []
            for date, values in time_series.items():
                df_data.append(
                    {
                        "date": pd.to_datetime(date),
                        "Open": float(values["1. open"]),
                        "High": float(values["2. high"]),
                        "Low": float(values["3. low"]),
                        "Close": float(values["4. close"]),
                        "Volume": int(values["5. volume"]),
                    }
                )

            df = pd.DataFrame(df_data)
            df.set_index("date", inplace=True)
            df.sort_index(inplace=True)

            logger.info(
                "Monthly bars fetched",
                symbol=symbol,
                bars_count=len(df),
            )

            return df

        except Exception as e:
            logger.error(
                "Monthly bars fetch failed",
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
            interval: 1m, 5m, 15m, 30m, 60m, 1d, 1wk, 1mo
            period: Relative period (1d, 5d, 1mo, 6mo, 1y, etc.) - ignored if dates provided
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            DataFrame with Open, High, Low, Close, Volume columns
        """
        try:
            # Map intervals to Alpha Vantage format
            if interval in ["1m", "5m", "15m", "30m", "60m", "60min", "1h"]:
                # Map to Alpha Vantage interval format
                if interval in ["1h", "60m"]:
                    av_interval = "60min"
                else:
                    av_interval = interval.replace("m", "min")

                # Use TIME_SERIES_INTRADAY (converged API with extended hours support)
                # Use compact mode (100 bars) per user principle: "for below and including 1day use compact mode"
                # Note: Extended endpoint (TIME_SERIES_INTRADAY_EXTENDED) has been deprecated
                df = await self.get_intraday_bars(symbol, av_interval, "compact")

                logger.info(
                    "Fetched intraday data",
                    symbol=symbol,
                    interval=interval,
                    outputsize="compact",
                    bars_count=len(df),
                    time_range=(
                        f"{df.index.min()} to {df.index.max()}"
                        if not df.empty
                        else "empty"
                    ),
                )

            elif interval in ["1d", "day"]:
                # Daily - use full mode for complete historical data (20+ years)
                df = await self.get_daily_bars(symbol, "full")
            elif interval in ["1wk", "1w", "week"]:
                # Weekly
                df = await self.get_weekly_bars(symbol, "full")
            elif interval in ["1mo", "1M", "month"]:
                # Monthly
                df = await self.get_monthly_bars(symbol, "full")
            else:
                # Default to daily
                logger.warning(
                    f"Unsupported interval '{interval}', defaulting to daily",
                    symbol=symbol,
                )
                df = await self.get_daily_bars(symbol, "compact")

            # For intraday data, always return the most recent data available
            # Don't filter by requested dates - if Sunday is requested, show Friday's data
            # This matches behavior of other trading platforms
            if (
                interval in ["1m", "5m", "15m", "30m", "60m", "60min", "1h"]
                and not df.empty
            ):
                logger.info(
                    "Returning latest available intraday data",
                    symbol=symbol,
                    requested_range=(
                        f"{start_date} to {end_date}"
                        if start_date and end_date
                        else "none"
                    ),
                    actual_range=f"{df.index.min()} to {df.index.max()}",
                )

            # Apply interval-specific time caps to reduce API load and optimize data volume
            # User preference: "1d 2 year max, 1w 6 year, 1mo go full"
            if not df.empty:
                from datetime import datetime, timedelta

                # Define time caps per interval
                time_cap_years = {
                    "1d": 2,  # Daily: 2 years (~500 trading days)
                    "day": 2,
                    "1w": 6,  # Weekly: 6 years (~312 weeks)
                    "1wk": 6,
                    "week": 6,
                    # Monthly: No cap - full historical data
                    # Intraday (60m, 1m, etc.): No cap - compact mode already limits
                }

                years_cap = time_cap_years.get(interval)

                if years_cap:
                    # Calculate cutoff date based on interval-specific cap
                    cutoff_date = datetime.now() - timedelta(days=years_cap * 365)

                    # Check if DataFrame index is timezone-aware
                    if df.index.tz is not None:
                        # Timezone-aware (intraday data) - localize cutoff to Eastern Time
                        cutoff_dt = pd.to_datetime(cutoff_date).tz_localize(
                            "America/New_York"
                        )
                    else:
                        # Timezone-naive (daily/weekly/monthly data) - use naive timestamp
                        cutoff_dt = pd.to_datetime(cutoff_date)

                    original_count = len(df)
                    df = df[df.index >= cutoff_dt]

                    logger.info(
                        "Applied time cap",
                        symbol=symbol,
                        interval=interval,
                        years_cap=years_cap,
                        cutoff_date=cutoff_dt,
                        original_count=original_count,
                        filtered_count=len(df),
                        date_range=(
                            f"{df.index.min()} to {df.index.max()}"
                            if not df.empty
                            else "empty"
                        ),
                    )
                else:
                    logger.info(
                        "No time cap applied (full historical data)",
                        symbol=symbol,
                        interval=interval,
                        bars_count=len(df),
                        date_range=(
                            f"{df.index.min()} to {df.index.max()}"
                            if not df.empty
                            else "empty"
                        ),
                    )

            # Filter data by custom date range OR apply default limits
            if not df.empty:
                # If custom dates provided, filter to that range
                if start_date and end_date:
                    # Check if DataFrame index is timezone-aware
                    if df.index.tz is not None:
                        # Timezone-aware (intraday data) - localize timestamps to Eastern Time
                        start_dt = pd.to_datetime(start_date).tz_localize(
                            "America/New_York"
                        )
                        end_dt = (
                            pd.to_datetime(end_date)
                            + pd.Timedelta(days=1)
                            - pd.Timedelta(seconds=1)
                        ).tz_localize("America/New_York")
                    else:
                        # Timezone-naive (daily/weekly/monthly data) - use naive timestamps
                        start_dt = pd.to_datetime(start_date)
                        end_dt = (
                            pd.to_datetime(end_date)
                            + pd.Timedelta(days=1)
                            - pd.Timedelta(seconds=1)
                        )

                    original_count = len(df)
                    original_df_copy = df.copy()  # Save copy before filtering
                    df = df[(df.index >= start_dt) & (df.index <= end_dt)]

                    logger.info(
                        "Filtered to custom date range",
                        symbol=symbol,
                        interval=interval,
                        start_date=start_date,
                        end_date=end_date,
                        original_count=original_count,
                        filtered_count=len(df),
                    )

                    # For intraday: if filtering resulted in no data, fall back to most recent available
                    if df.empty and interval in ["1m", "60m", "1h", "60min"]:
                        logger.info(
                            "No data for requested date range, returning most recent intraday data",
                            symbol=symbol,
                            interval=interval,
                            requested_range=f"{start_date} to {end_date}",
                        )
                        # Restore original DataFrame and take most recent bars
                        df = original_df_copy
                        max_bars = (
                            420 if interval == "1m" else 85
                        )  # 1 day of 1min or 1 week of 1h
                        if len(df) > max_bars:
                            df = df.tail(max_bars)
                else:
                    # Apply default bar limits for specific intervals
                    # Following principle: cache full data efficiently, show what we got
                    max_bars_map = {
                        "1m": 100,  # Compact mode returns 100 bars
                        "1h": 100,  # Compact mode returns 100 bars
                        "60min": 100,  # Compact mode returns 100 bars
                        # Note: 1d, 1w, 1mo have NO limit - show all historical data (full mode)
                        # Note: 5m, 15m, 30m also have NO limit - full historical data
                    }
                    max_bars = max_bars_map.get(interval)
                    if max_bars and len(df) > max_bars:
                        original_count = len(df)
                        df = df.tail(max_bars)
                        logger.info(
                            "Limited data to max bars",
                            symbol=symbol,
                            interval=interval,
                            original_count=original_count,
                            limited_count=len(df),
                            max_bars=max_bars,
                        )

            return df

        except Exception as e:
            logger.error(
                "Price bars fetch failed",
                symbol=symbol,
                interval=interval,
                error=str(e),
            )
            raise

    async def get_company_overview(self, symbol: str) -> dict[str, Any]:
        """
        Get company fundamentals and overview using OVERVIEW endpoint.

        Returns raw Alpha Vantage response with comprehensive company data including:
        - Symbol, Name, Description, Exchange, Currency
        - MarketCapitalization, EBITDA, PERatio, EPS
        - ProfitMargin, RevenuePerShareTTM, DividendYield
        - 52WeekHigh, 52WeekLow, Beta, etc.

        Args:
            symbol: Stock symbol

        Returns:
            Dict with raw Alpha Vantage company overview data
        """
        try:
            response = await self.client.get(
                self.base_url,
                params={
                    "function": "OVERVIEW",
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

            if not data or "Symbol" not in data:
                raise ValueError(f"No company overview data for symbol: {symbol}")

            logger.info(
                "Company overview fetched",
                symbol=symbol,
                company_name=data.get("Name", "N/A"),
            )

            return data

        except Exception as e:
            logger.error("Company overview fetch failed", symbol=symbol, error=str(e))
            raise

    async def get_news_sentiment(
        self,
        tickers: str,
        limit: int = 50,
        sort: str = "LATEST",
    ) -> dict[str, Any]:
        """
        Get news with sentiment analysis using NEWS_SENTIMENT endpoint.

        Args:
            tickers: Comma-separated stock symbols (e.g., "AAPL,MSFT")
            limit: Maximum number of news items (default 50, max 1000)
            sort: Sort order - LATEST | EARLIEST | RELEVANCE

        Returns:
            Dict with feed (news items) and sentiment_score_definition
        """
        try:
            params = {
                "function": "NEWS_SENTIMENT",
                "tickers": tickers,
                "limit": limit,
                "sort": sort,
                "apikey": self.api_key,
            }

            response = await self.client.get(self.base_url, params=params)

            if response.status_code != 200:
                sanitized_text = self._sanitize_text(response.text)
                raise ValueError(
                    f"Alpha Vantage API error: {response.status_code} - {sanitized_text}"
                )

            data = response.json()

            if "feed" not in data:
                sanitized = self._sanitize_response(data)
                logger.warning(
                    "No news sentiment data", tickers=tickers, response=sanitized
                )
                return {
                    "feed": [],
                    "sentiment_score_definition": data.get(
                        "sentiment_score_definition"
                    ),
                }

            logger.info(
                "News sentiment fetched",
                tickers=tickers,
                news_count=len(data["feed"]),
            )

            return data

        except Exception as e:
            logger.error("News sentiment fetch failed", tickers=tickers, error=str(e))
            raise

    async def get_cash_flow(self, symbol: str) -> dict[str, Any]:
        """
        Get cash flow statements using CASH_FLOW endpoint.

        Returns both annual and quarterly cash flow reports with fields like:
        - operatingCashflow
        - capitalExpenditures
        - cashflowFromInvestment
        - cashflowFromFinancing
        - dividendPayout

        Args:
            symbol: Stock symbol

        Returns:
            Dict with annualReports and quarterlyReports lists
        """
        try:
            response = await self.client.get(
                self.base_url,
                params={
                    "function": "CASH_FLOW",
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

            if "annualReports" not in data and "quarterlyReports" not in data:
                raise ValueError(f"No cash flow data for symbol: {symbol}")

            logger.info(
                "Cash flow fetched",
                symbol=symbol,
                annual_reports=len(data.get("annualReports", [])),
                quarterly_reports=len(data.get("quarterlyReports", [])),
            )

            return data

        except Exception as e:
            logger.error("Cash flow fetch failed", symbol=symbol, error=str(e))
            raise

    async def get_balance_sheet(self, symbol: str) -> dict[str, Any]:
        """
        Get balance sheet using BALANCE_SHEET endpoint.

        Returns both annual and quarterly balance sheets with fields like:
        - totalAssets
        - totalLiabilities
        - totalShareholderEquity
        - cash
        - currentDebt, longTermDebt

        Args:
            symbol: Stock symbol

        Returns:
            Dict with annualReports and quarterlyReports lists
        """
        try:
            response = await self.client.get(
                self.base_url,
                params={
                    "function": "BALANCE_SHEET",
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

            if "annualReports" not in data and "quarterlyReports" not in data:
                raise ValueError(f"No balance sheet data for symbol: {symbol}")

            logger.info(
                "Balance sheet fetched",
                symbol=symbol,
                annual_reports=len(data.get("annualReports", [])),
                quarterly_reports=len(data.get("quarterlyReports", [])),
            )

            return data

        except Exception as e:
            logger.error("Balance sheet fetch failed", symbol=symbol, error=str(e))
            raise

    async def get_top_gainers_losers(self) -> dict[str, Any]:
        """
        Get market movers using TOP_GAINERS_LOSERS endpoint.

        Returns today's top performing stocks across three categories:
        - top_gainers: Top 20 stocks with highest price increase
        - top_losers: Top 20 stocks with largest price decrease
        - most_actively_traded: Top 20 stocks by trading volume

        Returns:
            Dict with top_gainers, top_losers, most_actively_traded lists
        """
        try:
            response = await self.client.get(
                self.base_url,
                params={
                    "function": "TOP_GAINERS_LOSERS",
                    "apikey": self.api_key,
                },
            )

            if response.status_code != 200:
                sanitized_text = self._sanitize_text(response.text)
                raise ValueError(
                    f"Alpha Vantage API error: {response.status_code} - {sanitized_text}"
                )

            data = response.json()

            if not any(
                key in data
                for key in ["top_gainers", "top_losers", "most_actively_traded"]
            ):
                sanitized = self._sanitize_response(data)
                raise ValueError(f"No market movers data available: {sanitized}")

            logger.info(
                "Market movers fetched",
                gainers_count=len(data.get("top_gainers", [])),
                losers_count=len(data.get("top_losers", [])),
                active_count=len(data.get("most_actively_traded", [])),
            )

            return data

        except Exception as e:
            logger.error("Market movers fetch failed", error=str(e))
            raise

    async def get_real_gdp(self, interval: str = "annual") -> pd.DataFrame:
        """
        Get Real GDP economic indicator using REAL_GDP endpoint.

        Args:
            interval: annual (default) or quarterly

        Returns:
            DataFrame with date index and value column
        """
        try:
            response = await self.client.get(
                self.base_url,
                params={
                    "function": "REAL_GDP",
                    "interval": interval,
                    "apikey": self.api_key,
                },
            )

            if response.status_code != 200:
                sanitized_text = self._sanitize_text(response.text)
                raise ValueError(
                    f"Alpha Vantage API error: {response.status_code} - {sanitized_text}"
                )

            data = response.json()

            if "data" not in data:
                sanitized = self._sanitize_response(data)
                raise ValueError(f"No REAL_GDP data available: {sanitized}")

            # Convert to DataFrame
            df_data = []
            for item in data["data"]:
                df_data.append(
                    {
                        "date": pd.to_datetime(item["date"]),
                        "value": float(item["value"]),
                    }
                )

            df = pd.DataFrame(df_data)
            df.set_index("date", inplace=True)
            df.sort_index(inplace=True)

            logger.info("REAL_GDP data fetched", interval=interval, data_points=len(df))

            return df

        except Exception as e:
            logger.error("REAL_GDP fetch failed", interval=interval, error=str(e))
            raise

    async def get_cpi(self, interval: str = "monthly") -> pd.DataFrame:
        """
        Get Consumer Price Index (CPI) using CPI endpoint.

        Args:
            interval: monthly (default) or semiannual

        Returns:
            DataFrame with date index and value column
        """
        try:
            response = await self.client.get(
                self.base_url,
                params={
                    "function": "CPI",
                    "interval": interval,
                    "apikey": self.api_key,
                },
            )

            if response.status_code != 200:
                sanitized_text = self._sanitize_text(response.text)
                raise ValueError(
                    f"Alpha Vantage API error: {response.status_code} - {sanitized_text}"
                )

            data = response.json()

            if "data" not in data:
                sanitized = self._sanitize_response(data)
                raise ValueError(f"No CPI data available: {sanitized}")

            # Convert to DataFrame
            df_data = []
            for item in data["data"]:
                df_data.append(
                    {
                        "date": pd.to_datetime(item["date"]),
                        "value": float(item["value"]),
                    }
                )

            df = pd.DataFrame(df_data)
            df.set_index("date", inplace=True)
            df.sort_index(inplace=True)

            logger.info("CPI data fetched", interval=interval, data_points=len(df))

            return df

        except Exception as e:
            logger.error("CPI fetch failed", interval=interval, error=str(e))
            raise

    async def get_inflation(self) -> pd.DataFrame:
        """
        Get Inflation rate using INFLATION endpoint.

        Returns:
            DataFrame with date index and value column
        """
        try:
            response = await self.client.get(
                self.base_url,
                params={
                    "function": "INFLATION",
                    "apikey": self.api_key,
                },
            )

            if response.status_code != 200:
                sanitized_text = self._sanitize_text(response.text)
                raise ValueError(
                    f"Alpha Vantage API error: {response.status_code} - {sanitized_text}"
                )

            data = response.json()

            if "data" not in data:
                sanitized = self._sanitize_response(data)
                raise ValueError(f"No INFLATION data available: {sanitized}")

            # Convert to DataFrame
            df_data = []
            for item in data["data"]:
                df_data.append(
                    {
                        "date": pd.to_datetime(item["date"]),
                        "value": float(item["value"]),
                    }
                )

            df = pd.DataFrame(df_data)
            df.set_index("date", inplace=True)
            df.sort_index(inplace=True)

            logger.info("INFLATION data fetched", data_points=len(df))

            return df

        except Exception as e:
            logger.error("INFLATION fetch failed", error=str(e))
            raise

    async def get_unemployment(self) -> pd.DataFrame:
        """
        Get Unemployment rate using UNEMPLOYMENT endpoint.

        Returns:
            DataFrame with date index and value column
        """
        try:
            response = await self.client.get(
                self.base_url,
                params={
                    "function": "UNEMPLOYMENT",
                    "apikey": self.api_key,
                },
            )

            if response.status_code != 200:
                sanitized_text = self._sanitize_text(response.text)
                raise ValueError(
                    f"Alpha Vantage API error: {response.status_code} - {sanitized_text}"
                )

            data = response.json()

            if "data" not in data:
                sanitized = self._sanitize_response(data)
                raise ValueError(f"No UNEMPLOYMENT data available: {sanitized}")

            # Convert to DataFrame
            df_data = []
            for item in data["data"]:
                df_data.append(
                    {
                        "date": pd.to_datetime(item["date"]),
                        "value": float(item["value"]),
                    }
                )

            df = pd.DataFrame(df_data)
            df.set_index("date", inplace=True)
            df.sort_index(inplace=True)

            logger.info("UNEMPLOYMENT data fetched", data_points=len(df))

            return df

        except Exception as e:
            logger.error("UNEMPLOYMENT fetch failed", error=str(e))
            raise

    async def get_commodity_prices(self, interval: str = "monthly") -> pd.DataFrame:
        """
        Get Global Price Index of All Commodities using WTI endpoint as proxy.

        Note: Alpha Vantage provides WTI (West Texas Intermediate) crude oil prices,
        which serves as a commodity market indicator.

        Args:
            interval: daily, weekly, or monthly (default)

        Returns:
            DataFrame with date index and value column
        """
        try:
            response = await self.client.get(
                self.base_url,
                params={
                    "function": "WTI",
                    "interval": interval,
                    "apikey": self.api_key,
                },
            )

            if response.status_code != 200:
                sanitized_text = self._sanitize_text(response.text)
                raise ValueError(
                    f"Alpha Vantage API error: {response.status_code} - {sanitized_text}"
                )

            data = response.json()

            if "data" not in data:
                sanitized = self._sanitize_response(data)
                raise ValueError(f"No commodity price data available: {sanitized}")

            # Convert to DataFrame
            df_data = []
            for item in data["data"]:
                df_data.append(
                    {
                        "date": pd.to_datetime(item["date"]),
                        "value": float(item["value"]),
                    }
                )

            df = pd.DataFrame(df_data)
            df.set_index("date", inplace=True)
            df.sort_index(inplace=True)

            logger.info(
                "Commodity prices (WTI) fetched",
                interval=interval,
                data_points=len(df),
            )

            return df

        except Exception as e:
            logger.error(
                "Commodity prices fetch failed", interval=interval, error=str(e)
            )
            raise

    async def get_insider_transactions(
        self, symbol: str, limit: int = 50
    ) -> dict[str, Any]:
        """
        Get insider transactions (executive buy/sell activity).

        Returns CSV data from INSIDER_TRANSACTIONS endpoint.
        Filters to most recent transactions for context efficiency.

        Args:
            symbol: Stock ticker symbol
            limit: Maximum number of transactions to return (default: 50)

        Returns:
            Dict with 'symbol' and 'data' list containing transaction records
        """
        try:
            response = await self.client.get(
                self.base_url,
                params={
                    "function": "INSIDER_TRANSACTIONS",
                    "symbol": symbol,
                    "apikey": self.api_key,
                },
            )

            if response.status_code != 200:
                sanitized_text = self._sanitize_text(response.text)
                raise ValueError(
                    f"Alpha Vantage API error: {response.status_code} - {sanitized_text}"
                )

            # Parse CSV response
            from io import StringIO

            csv_text = response.text.strip()

            if not csv_text or "Error" in csv_text[:100]:
                sanitized = self._sanitize_text(csv_text[:200])
                raise ValueError(
                    f"No insider transaction data for symbol: {symbol}. Response: {sanitized}"
                )

            # Parse CSV using pandas
            df = pd.read_csv(
                StringIO(csv_text),
                on_bad_lines="skip",
            )

            if df.empty:
                logger.warning("No insider transactions found", symbol=symbol)
                return {"symbol": symbol, "data": []}

            # Convert to list of dicts and limit to recent transactions
            transactions = df.head(limit).to_dict("records")

            logger.info(
                "Insider transactions fetched",
                symbol=symbol,
                total_count=len(df),
                returned_count=len(transactions),
            )

            return {"symbol": symbol, "data": transactions}

        except Exception as e:
            logger.error(
                "Insider transactions fetch failed", symbol=symbol, error=str(e)
            )
            raise

    async def get_etf_profile(self, symbol: str) -> dict[str, Any]:
        """
        Get ETF profile with holdings and sector allocation.

        Uses ETF_PROFILE endpoint to return holdings (top constituents)
        and sector breakdown for exchange-traded funds.

        **Caching**: ETF profiles change infrequently, cached for 24 hours.

        Args:
            symbol: ETF ticker symbol (e.g., "QQQ", "SOXS", "SPY")

        Returns:
            Dict with net_assets, holdings, sectors, leveraged flag, etc.
        """
        # Check cache first (24h TTL - ETF profiles rarely change)
        cache_key = f"etf_profile:{symbol}"
        if self.redis_cache:
            cached_data = await self.redis_cache.get(cache_key)
            if cached_data:
                logger.info("ETF profile cache hit", symbol=symbol)
                return json.loads(cached_data)

        try:
            response = await self.client.get(
                self.base_url,
                params={
                    "function": "ETF_PROFILE",
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

            if not data or "Error Message" in data:
                sanitized = self._sanitize_response(data)
                raise ValueError(
                    f"No ETF profile data for symbol: {symbol}. Response: {sanitized}"
                )

            result = {"symbol": symbol, **data}

            # Cache for 24 hours (ETF profiles change infrequently)
            if self.redis_cache:
                await self.redis_cache.set(
                    cache_key, json.dumps(result), ttl=86400  # 24 hours
                )

            logger.info(
                "ETF profile fetched and cached",
                symbol=symbol,
                holdings_count=len(data.get("holdings", [])),
                sectors_count=len(data.get("sectors", [])),
            )

            return result

        except Exception as e:
            logger.error("ETF profile fetch failed", symbol=symbol, error=str(e))
            raise

    async def get_commodity_price(
        self, commodity: str = "COPPER", interval: str = "monthly"
    ) -> pd.DataFrame:
        """
        Get global commodity prices (COPPER, ALUMINUM, WHEAT, etc.).

        Uses commodity-specific endpoints (COPPER, ALUMINUM, etc.).
        Returns time series of commodity prices.

        Args:
            commodity: Commodity code (COPPER, ALUMINUM, WHEAT, CORN, etc.)
            interval: daily, weekly, or monthly (default: monthly)

        Returns:
            DataFrame with date index and value column
        """
        try:
            # Validate commodity code
            valid_commodities = [
                "COPPER",
                "ALUMINUM",
                "WHEAT",
                "CORN",
                "COTTON",
                "SUGAR",
                "COFFEE",
                "ALL_COMMODITIES",
            ]
            commodity_upper = commodity.upper()

            if commodity_upper not in valid_commodities:
                raise ValueError(
                    f"Invalid commodity: {commodity}. Use one of: {', '.join(valid_commodities)}"
                )

            response = await self.client.get(
                self.base_url,
                params={
                    "function": commodity_upper,
                    "interval": interval,
                    "apikey": self.api_key,
                },
            )

            if response.status_code != 200:
                sanitized_text = self._sanitize_text(response.text)
                raise ValueError(
                    f"Alpha Vantage API error: {response.status_code} - {sanitized_text}"
                )

            data = response.json()

            if "data" not in data:
                sanitized = self._sanitize_response(data)
                raise ValueError(f"No {commodity} price data available: {sanitized}")

            # Convert to DataFrame
            df_data = []
            for item in data["data"]:
                df_data.append(
                    {
                        "date": pd.to_datetime(item["date"]),
                        "value": float(item["value"]),
                    }
                )

            df = pd.DataFrame(df_data)
            df.set_index("date", inplace=True)
            df.sort_index(inplace=True)

            logger.info(
                "Commodity price fetched",
                commodity=commodity,
                interval=interval,
                data_points=len(df),
            )

            return df

        except Exception as e:
            logger.error(
                "Commodity price fetch failed",
                commodity=commodity,
                interval=interval,
                error=str(e),
            )
            raise

    async def get_technical_indicator(
        self,
        symbol: str,
        function: str,
        interval: str,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Get technical indicator data (unified method for all indicators).

        Supports: SMA, EMA, VWAP, MACD, STOCH, RSI, ADX, AROON, BBANDS, AD, OBV

        Args:
            symbol: Stock ticker symbol
            function: Technical indicator name (uppercase)
            interval: Time interval (1min, 5min, 15min, 30min, 60min, daily, weekly, monthly)
            **kwargs: Indicator-specific parameters:
                - time_period: Period for MA indicators (default: 10)
                - series_type: close, open, high, low (default: close)
                - fastperiod, slowperiod, signalperiod: For MACD
                - fastkperiod, slowkperiod, slowdperiod: For STOCH
                - nbdevup, nbdevdn, matype: For BBANDS

        Returns:
            DataFrame with date/timestamp index and indicator values
        """
        try:
            # Validate indicator
            supported = [
                "SMA",
                "EMA",
                "VWAP",
                "MACD",
                "STOCH",
                "RSI",
                "ADX",
                "AROON",
                "BBANDS",
                "AD",
                "OBV",
            ]
            function_upper = function.upper()

            if function_upper not in supported:
                raise ValueError(
                    f"Unsupported indicator: {function}. Use one of: {', '.join(supported)}"
                )

            # Build params with defaults
            params = {
                "function": function_upper,
                "symbol": symbol,
                "interval": interval,
                "apikey": self.api_key,
            }

            # Add optional parameters
            if "time_period" in kwargs:
                params["time_period"] = kwargs["time_period"]
            if "series_type" in kwargs:
                params["series_type"] = kwargs["series_type"]

            # MACD-specific params
            if function_upper == "MACD":
                params["fastperiod"] = kwargs.get("fastperiod", 12)
                params["slowperiod"] = kwargs.get("slowperiod", 26)
                params["signalperiod"] = kwargs.get("signalperiod", 9)

            # STOCH-specific params
            if function_upper == "STOCH":
                params["fastkperiod"] = kwargs.get("fastkperiod", 5)
                params["slowkperiod"] = kwargs.get("slowkperiod", 3)
                params["slowdperiod"] = kwargs.get("slowdperiod", 3)

            # BBANDS-specific params
            if function_upper == "BBANDS":
                params["nbdevup"] = kwargs.get("nbdevup", 2)
                params["nbdevdn"] = kwargs.get("nbdevdn", 2)

            response = await self.client.get(self.base_url, params=params)

            if response.status_code != 200:
                sanitized_text = self._sanitize_text(response.text)
                raise ValueError(
                    f"Alpha Vantage API error: {response.status_code} - {sanitized_text}"
                )

            data = response.json()

            # Find the technical indicator key in response
            tech_key = None
            for key in data.keys():
                if "Technical Analysis" in key or function_upper in key:
                    tech_key = key
                    break

            if not tech_key or not data[tech_key]:
                sanitized = self._sanitize_response(data)
                raise ValueError(
                    f"No {function} data for symbol: {symbol}. Response: {sanitized}"
                )

            time_series = data[tech_key]

            # Convert to DataFrame
            df_data = []
            for timestamp, values in time_series.items():
                row = {"timestamp": pd.to_datetime(timestamp)}
                # Add all indicator values (handles single and multi-column indicators)
                for val_key, val in values.items():
                    # Clean column name (remove numeric prefix like "1. ")
                    clean_key = (
                        val_key.split(". ", 1)[-1] if ". " in val_key else val_key
                    )
                    row[clean_key] = float(val)
                df_data.append(row)

            df = pd.DataFrame(df_data)
            df.set_index("timestamp", inplace=True)
            df.sort_index(inplace=True)

            # Localize intraday timestamps to ET
            if interval in ["1min", "5min", "15min", "30min", "60min"]:
                if df.index.tz is None:
                    df.index = df.index.tz_localize("America/New_York")

            logger.info(
                "Technical indicator fetched",
                symbol=symbol,
                function=function,
                interval=interval,
                data_points=len(df),
            )

            return df

        except Exception as e:
            logger.error(
                "Technical indicator fetch failed",
                symbol=symbol,
                function=function,
                interval=interval,
                error=str(e),
            )
            raise
