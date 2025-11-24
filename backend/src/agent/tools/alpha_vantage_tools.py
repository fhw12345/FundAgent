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

    @tool
    async def get_insider_activity(symbol: str, limit: int = 50) -> str:
        """
        Get recent insider trading activity (executive buy/sell transactions).

        Shows insider sentiment through actual transactions by company executives,
        directors, and major shareholders. Useful for detecting insider confidence.

        Args:
            symbol: Stock ticker symbol (e.g., "AAPL", "TSLA")
            limit: Number of recent transactions to analyze (default: 50)

        Returns:
            Formatted insider activity summary with acquisition/disposal trends

        Examples:
            - symbol="AAPL" → Recent insider transactions with buy/sell ratio
            - symbol="NVDA", limit=100 → Extended insider activity analysis
        """
        try:
            data = await service.get_insider_transactions(symbol, limit)

            if not data or not data.get("data"):
                return f"No insider transaction data available for {symbol}"

            return formatter.format_insider_transactions(
                raw_data=data,
                symbol=symbol,
                invoked_at=datetime.now(UTC).isoformat(),
            )
        except Exception as e:
            logger.error("Insider activity tool failed", symbol=symbol, error=str(e))
            return f"Insider activity error for {symbol}: {str(e)}"

    @tool
    async def get_etf_holdings(symbol: str) -> str:
        """
        Get ETF profile with top holdings and sector allocation.

        Returns comprehensive ETF information including constituent stocks,
        sector breakdown, and fund characteristics. Useful for understanding
        ETF composition and diversification.

        Args:
            symbol: ETF ticker symbol (e.g., "QQQ", "SPY", "SOXS")

        Returns:
            Formatted ETF profile with holdings, sectors, and fund metrics

        Examples:
            - symbol="QQQ" → Nasdaq-100 ETF holdings (tech-heavy)
            - symbol="SOXS" → 3x leveraged semiconductor inverse ETF
            - symbol="SPY" → S&P 500 ETF holdings
        """
        try:
            data = await service.get_etf_profile(symbol)

            if not data:
                return f"No ETF profile data available for {symbol} (verify it's an ETF)"

            return formatter.format_etf_profile(
                raw_data=data,
                symbol=symbol,
                invoked_at=datetime.now(UTC).isoformat(),
            )
        except Exception as e:
            logger.error("ETF holdings tool failed", symbol=symbol, error=str(e))
            return f"ETF holdings error for {symbol}: {str(e)}"

    @tool
    async def get_copper_commodity(interval: str = "monthly") -> str:
        """
        Get global copper prices (key indicator for AI infrastructure demand).

        Copper is essential for AI data center construction and electricity
        infrastructure. Rising copper prices indicate growing AI/tech demand.

        Args:
            interval: Price interval - "daily", "weekly", or "monthly"

        Returns:
            Formatted copper price history with trend analysis

        Examples:
            - interval="monthly" → Long-term copper price trends
            - interval="weekly" → Recent copper price movements

        Note:
            Copper demand correlates with AI infrastructure growth due to
            massive electricity requirements for GPU clusters and data centers.
        """
        try:
            df = await service.get_commodity_price(commodity="COPPER", interval=interval)

            if df.empty:
                return f"No copper price data available for interval: {interval}"

            return formatter.format_commodity_price(
                df=df,
                commodity="COPPER",
                interval=interval,
                invoked_at=datetime.now(UTC).isoformat(),
            )
        except Exception as e:
            logger.error("Copper commodity tool failed", interval=interval, error=str(e))
            return f"Copper commodity error: {str(e)}"

    @tool
    async def get_trend_indicator(
        symbol: str,
        indicator: str,
        interval: str = "daily",
        time_period: int = 10,
    ) -> str:
        """
        Get trend indicators: SMA, EMA, VWAP.

        Use for identifying price trends and support/resistance levels.
        Moving averages smooth price data to show trend direction.

        Args:
            symbol: Stock ticker symbol (e.g., "AAPL", "NVDA")
            indicator: Indicator name - "SMA", "EMA", or "VWAP"
            interval: Time interval - 1min, 5min, 15min, 30min, 60min, daily, weekly, monthly
            time_period: Period for calculation (default: 10 for SMA/EMA)

        Returns:
            Formatted trend indicator with current value and interpretation

        Examples:
            - symbol="AAPL", indicator="SMA" → 10-period SMA on daily chart
            - symbol="NVDA", indicator="EMA", interval="60min", time_period=20 → 20-period EMA hourly
            - symbol="TSLA", indicator="VWAP", interval="1min" → Intraday VWAP
        """
        try:
            supported = ["SMA", "EMA", "VWAP"]
            indicator_upper = indicator.upper()

            if indicator_upper not in supported:
                return f"Unsupported trend indicator: {indicator}. Use one of: {', '.join(supported)}"

            df = await service.get_technical_indicator(
                symbol=symbol,
                function=indicator_upper,
                interval=interval,
                time_period=time_period if indicator_upper != "VWAP" else None,
                series_type="close",
            )

            if df.empty:
                return f"No {indicator} data available for {symbol}"

            return formatter.format_technical_indicator(
                df=df,
                symbol=symbol,
                function=indicator_upper,
                interval=interval,
                invoked_at=datetime.now(UTC).isoformat(),
            )
        except Exception as e:
            logger.error(
                "Trend indicator tool failed",
                symbol=symbol,
                indicator=indicator,
                error=str(e)
            )
            return f"Trend indicator error for {symbol} ({indicator}): {str(e)}"

    @tool
    async def get_momentum_indicator(
        symbol: str,
        indicator: str,
        interval: str = "daily",
        time_period: int = 14,
    ) -> str:
        """
        Get momentum indicators: RSI, MACD, STOCH.

        Use for identifying overbought/oversold conditions and trend reversals.
        Momentum indicators measure the speed of price changes.

        Args:
            symbol: Stock ticker symbol (e.g., "AAPL", "NVDA")
            indicator: Indicator name - "RSI", "MACD", or "STOCH"
            interval: Time interval - 1min, 5min, 15min, 30min, 60min, daily, weekly, monthly
            time_period: Period for calculation (default: 14 for RSI)

        Returns:
            Formatted momentum indicator with current value and trading signal

        Examples:
            - symbol="AAPL", indicator="RSI" → 14-period RSI (overbought >70, oversold <30)
            - symbol="NVDA", indicator="MACD", interval="60min" → Hourly MACD crossover signals
            - symbol="TSLA", indicator="STOCH" → Stochastic oscillator for reversal signals
        """
        try:
            supported = ["RSI", "MACD", "STOCH"]
            indicator_upper = indicator.upper()

            if indicator_upper not in supported:
                return f"Unsupported momentum indicator: {indicator}. Use one of: {', '.join(supported)}"

            df = await service.get_technical_indicator(
                symbol=symbol,
                function=indicator_upper,
                interval=interval,
                time_period=time_period if indicator_upper == "RSI" else None,
                series_type="close",
            )

            if df.empty:
                return f"No {indicator} data available for {symbol}"

            return formatter.format_technical_indicator(
                df=df,
                symbol=symbol,
                function=indicator_upper,
                interval=interval,
                invoked_at=datetime.now(UTC).isoformat(),
            )
        except Exception as e:
            logger.error(
                "Momentum indicator tool failed",
                symbol=symbol,
                indicator=indicator,
                error=str(e)
            )
            return f"Momentum indicator error for {symbol} ({indicator}): {str(e)}"

    @tool
    async def get_volume_indicator(
        symbol: str,
        indicator: str,
        interval: str = "daily",
        time_period: int = 14,
    ) -> str:
        """
        Get volume/volatility indicators: AD, OBV, ADX, AROON, BBANDS.

        Use for confirming trends and measuring volatility.
        Volume indicators show buying/selling pressure and trend strength.

        Args:
            symbol: Stock ticker symbol (e.g., "AAPL", "NVDA")
            indicator: Indicator name - "AD", "OBV", "ADX", "AROON", or "BBANDS"
            interval: Time interval - 1min, 5min, 15min, 30min, 60min, daily, weekly, monthly
            time_period: Period for calculation (default: 14 for ADX/AROON, 20 for BBANDS)

        Returns:
            Formatted volume/volatility indicator with current value and interpretation

        Examples:
            - symbol="AAPL", indicator="AD" → Accumulation/Distribution Line
            - symbol="NVDA", indicator="OBV" → On-Balance Volume for trend confirmation
            - symbol="TSLA", indicator="ADX" → Trend strength (>25 = strong trend)
            - symbol="AAPL", indicator="BBANDS", time_period=20 → Bollinger Bands volatility
            - symbol="NVDA", indicator="AROON" → Aroon Up/Down for trend identification
        """
        try:
            supported = ["AD", "OBV", "ADX", "AROON", "BBANDS"]
            indicator_upper = indicator.upper()

            if indicator_upper not in supported:
                return f"Unsupported volume indicator: {indicator}. Use one of: {', '.join(supported)}"

            # Adjust default time_period for BBANDS
            if indicator_upper == "BBANDS" and time_period == 14:
                time_period = 20

            df = await service.get_technical_indicator(
                symbol=symbol,
                function=indicator_upper,
                interval=interval,
                time_period=time_period if indicator_upper not in ["AD", "OBV"] else None,
                series_type="close" if indicator_upper not in ["AD", "OBV"] else None,
            )

            if df.empty:
                return f"No {indicator} data available for {symbol}"

            return formatter.format_technical_indicator(
                df=df,
                symbol=symbol,
                function=indicator_upper,
                interval=interval,
                invoked_at=datetime.now(UTC).isoformat(),
            )
        except Exception as e:
            logger.error(
                "Volume indicator tool failed",
                symbol=symbol,
                indicator=indicator,
                error=str(e)
            )
            return f"Volume indicator error for {symbol} ({indicator}): {str(e)}"

    # Return all tools
    return [
        search_ticker,
        get_company_overview,
        get_news_sentiment,
        get_financial_statements,
        get_market_movers,
        # NEW TOOLS (6)
        get_insider_activity,
        get_etf_holdings,
        get_copper_commodity,
        get_trend_indicator,
        get_momentum_indicator,
        get_volume_indicator,
    ]
