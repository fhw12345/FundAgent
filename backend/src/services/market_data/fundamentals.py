"""
Company fundamentals and financial statements for Alpha Vantage service.
"""

import json
from io import StringIO
from typing import Any

import pandas as pd
import structlog

from .base import AlphaVantageBase

logger = structlog.get_logger()


class FundamentalsMixin(AlphaVantageBase):
    """Methods for company fundamentals, financial statements, and earnings data."""

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

            return data  # type: ignore[no-any-return]

        except Exception as e:
            logger.error("Company overview fetch failed", symbol=symbol, error=str(e))
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

            return data  # type: ignore[no-any-return]

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

            return data  # type: ignore[no-any-return]

        except Exception as e:
            logger.error("Balance sheet fetch failed", symbol=symbol, error=str(e))
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
            params: dict[str, str | int] = {
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

            return data  # type: ignore[no-any-return]

        except Exception as e:
            logger.error("News sentiment fetch failed", tickers=tickers, error=str(e))
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

            return data  # type: ignore[no-any-return]

        except Exception as e:
            logger.error("Market movers fetch failed", error=str(e))
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
                return json.loads(cached_data)  # type: ignore[no-any-return]

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
