"""
Alpha Vantage market data service.
Provides symbol search, quotes, and historical data using Alpha Vantage API.
"""

import re
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
            if interval in ["1m", "5m", "15m", "30m", "60m"]:
                # Intraday - fetch compact (100 points) for better performance
                # For 60m: 100 points = ~15 trading days
                # For 5m: 100 points = ~8 hours of trading
                # For 1m: 100 points = ~1.5 hours of trading
                av_interval = interval.replace("m", "min")
                df = await self.get_intraday_bars(symbol, av_interval, "compact")

                # Filter to last 1 day for intraday intervals
                if not df.empty and not (start_date and end_date):
                    # Get the latest timestamp
                    latest_time = df.index.max()
                    # Filter to last 1 trading day (24 hours)
                    one_day_ago = latest_time - pd.Timedelta(days=1)
                    df = df[df.index >= one_day_ago]

                    logger.info(
                        "Filtered intraday data to last 1 day",
                        symbol=symbol,
                        interval=av_interval,
                        original_points=len(df),
                        filtered_points=len(df),
                        time_range=f"{df.index.min()} to {df.index.max()}",
                    )

            elif interval in ["1d", "day"]:
                # Daily - use compact mode (100 bars) per user principle
                df = await self.get_daily_bars(symbol, "compact")
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

            # Filter by date range if provided (overrides 1-day filter for intraday)
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

    async def get_commodity_prices(
        self, interval: str = "monthly"
    ) -> pd.DataFrame:
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
