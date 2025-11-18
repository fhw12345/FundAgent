"""
Alpha Vantage Agent Tools for LLM Access.

Provides rich markdown outputs with metadata and trend analysis.
All tools use AlphaVantageMarketDataService for market data access.
"""

from datetime import UTC, datetime

import structlog
from langchain_core.tools import tool

from ...services.alphavantage_market_data import AlphaVantageMarketDataService
from ...services.alphavantage_response_formatter import AlphaVantageResponseFormatter

logger = structlog.get_logger()


def create_alpha_vantage_tools(
    service: AlphaVantageMarketDataService, formatter: AlphaVantageResponseFormatter
) -> list:
    """
    Create Alpha Vantage agent tools with service dependency injection.

    Args:
        service: Initialized AlphaVantageMarketDataService instance
        formatter: AlphaVantageResponseFormatter for consistent markdown output

    Returns:
        List of 5 LangChain tools for agent access
    """

    @tool
    async def search_ticker(query: str) -> str:
        """
        Search for stock ticker symbols by company name or partial symbol.

        Supports fuzzy matching on company names and symbols.
        Returns top matches with symbol, name, exchange, and confidence scores.

        Args:
            query: Company name or partial symbol (e.g., "apple", "micro", "AAPL")

        Returns:
            Compressed search results (top 5 matches with confidence scores)

        Examples:
            - query="apple" → AAPL, AAON, etc.
            - query="microsoft" → MSFT
            - query="TSL" → TSLA (Tesla)
        """
        try:
            results = await service.search_symbols(query, limit=5)

            if not results:
                return f"No ticker symbols found for query: {query}"

            # Format top 5 results
            formatted = [
                f"{r['symbol']} ({r['name']}, {r['exchange']}, {r['confidence']:.0%})"
                for r in results[:5]
            ]

            return f"""Ticker Search: "{query}"
Top Matches: {', '.join(formatted[:3])}
{f"More: {', '.join(formatted[3:])}" if len(formatted) > 3 else ""}"""

        except Exception as e:
            logger.error("Ticker search tool failed", query=query, error=str(e))
            return f"Ticker search error for '{query}': {str(e)}"

    @tool
    async def get_company_overview(symbol: str) -> str:
        """
        Get comprehensive company fundamentals and overview.

        Returns key financial metrics, ratios, and company information including:
        - Company info: Name, Description, Industry, Sector
        - Market metrics: Market Cap, P/E Ratio, EPS, Beta
        - Financial ratios: Profit Margin, Revenue, Dividend Yield
        - Ownership: Percent held by insiders and institutions
        - Price metrics: 52-week high/low, Moving averages

        Args:
            symbol: Stock ticker symbol (e.g., "AAPL", "MSFT", "TSLA")

        Returns:
            Formatted company overview with key metrics table

        Examples:
            - symbol="AAPL" → Apple Inc. fundamentals
            - symbol="MSFT" → Microsoft Corporation overview
        """
        try:
            data = await service.get_company_overview(symbol)

            if not data or "Symbol" not in data:
                return f"No company overview data available for {symbol}"

            # Use formatter for consistent rich markdown output
            return formatter.format_company_overview(
                raw_data=data,
                symbol=symbol,
                invoked_at=datetime.now(UTC).isoformat(),
            )

        except Exception as e:
            logger.error("Company overview tool failed", symbol=symbol, error=str(e))
            return f"Company overview error for {symbol}: {str(e)}"

    @tool
    async def get_news_sentiment(
        symbol: str,
        max_positive: int = 3,
        max_negative: int = 3,
    ) -> str:
        """
        Get latest news articles with sentiment analysis for a stock.

        Returns filtered news feed with sentiment scores and classifications.
        Automatically filters to top positive and negative sentiment articles.

        Args:
            symbol: Stock ticker symbol (e.g., "AAPL", "MSFT")
            max_positive: Maximum positive sentiment articles to return (default: 3)
            max_negative: Maximum negative sentiment articles to return (default: 3)

        Returns:
            Compressed news sentiment summary with top positive/negative articles

        Sentiment Labels:
            - Bullish: Positive sentiment (score > 0.15)
            - Bearish: Negative sentiment (score < -0.15)
            - Neutral: Mixed or neutral sentiment (-0.15 to 0.15)

        Examples:
            - symbol="AAPL" → Latest Apple news with sentiment
            - symbol="TSLA", max_positive=2, max_negative=2 → Tesla top 4 news
        """
        try:
            data = await service.get_news_sentiment(
                tickers=symbol,
                limit=50,  # Get more to filter best positive/negative
                sort="LATEST",
            )

            if not data.get("feed"):
                return f"No news sentiment data available for {symbol}"

            # Use formatter for consistent rich markdown output
            return formatter.format_news_sentiment(
                raw_data=data,
                symbol=symbol,
                invoked_at=datetime.now(UTC).isoformat(),
            )

        except Exception as e:
            logger.error("News sentiment tool failed", symbol=symbol, error=str(e))
            return f"News sentiment error for {symbol}: {str(e)}"

    @tool
    async def get_financial_statements(
        symbol: str,
        statement_type: str = "cash_flow",
    ) -> str:
        """
        Get financial statements (Cash Flow or Balance Sheet) for a company.

        Returns annual and quarterly financial data with key metrics.
        Supports both cash flow and balance sheet statement types.

        Args:
            symbol: Stock ticker symbol (e.g., "AAPL", "MSFT")
            statement_type: Type of statement - "cash_flow" or "balance_sheet"

        Returns:
            Compressed financial statement summary (latest annual and quarterly)

        Cash Flow Metrics:
            - Operating Cash Flow, Capital Expenditures
            - Free Cash Flow (Operating - CapEx)
            - Dividend Payout, Cash Changes

        Balance Sheet Metrics:
            - Total Assets, Total Liabilities, Shareholder Equity
            - Current Assets/Liabilities, Cash, Debt
            - Inventory, Goodwill, Intangible Assets

        Examples:
            - symbol="AAPL", statement_type="cash_flow" → Apple cash flow
            - symbol="MSFT", statement_type="balance_sheet" → Microsoft balance sheet
        """
        try:
            statement_type = statement_type.lower().strip()

            if statement_type not in ["cash_flow", "balance_sheet"]:
                return f"Invalid statement_type: {statement_type}. Use 'cash_flow' or 'balance_sheet'"

            # Fetch data based on type
            if statement_type == "cash_flow":
                data = await service.get_cash_flow(symbol)
                # Use formatter for consistent rich markdown output with trends
                return formatter.format_cash_flow(
                    raw_data=data,
                    symbol=symbol,
                    invoked_at=datetime.now(UTC).isoformat(),
                )
            else:
                data = await service.get_balance_sheet(symbol)
                # Use formatter for consistent rich markdown output with trends
                return formatter.format_balance_sheet(
                    raw_data=data,
                    symbol=symbol,
                    invoked_at=datetime.now(UTC).isoformat(),
                )

        except Exception as e:
            logger.error(
                "Financial statements tool failed",
                symbol=symbol,
                statement_type=statement_type,
                error=str(e),
            )
            return f"Financial statements error for {symbol}: {str(e)}"

    @tool
    async def get_market_movers() -> str:
        """
        Get today's top market movers in the US stock market.

        Returns three categories of top performers:
        - Top Gainers: Stocks with highest price increase (% and $)
        - Top Losers: Stocks with largest price decrease (% and $)
        - Most Active: Stocks with highest trading volume

        Each category shows top 5 stocks with ticker, price, change, and volume.

        Args:
            None

        Returns:
            Compressed market movers summary (top 5 in each category)

        Examples:
            - Returns: NVDA +15.2%, TSLA -8.3%, AAPL 250M volume, etc.
        """
        try:
            data = await service.get_top_gainers_losers()

            if not data:
                return "No market movers data available"

            # Use formatter for consistent rich markdown output
            return formatter.format_market_movers(
                raw_data=data,
                invoked_at=datetime.now(UTC).isoformat(),
            )

        except Exception as e:
            logger.error("Market movers tool failed", error=str(e))
            return f"Market movers error: {str(e)}"

    # Return all tools
    return [
        search_ticker,
        get_company_overview,
        get_news_sentiment,
        get_financial_statements,
        get_market_movers,
    ]
