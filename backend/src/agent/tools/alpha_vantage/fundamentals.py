"""
Fundamental Analysis Tools.

Provides tools for company fundamentals, financial statements, insider activity, and ETF holdings.
"""

from datetime import UTC, datetime

import structlog
from langchain_core.tools import tool

from src.services.alphavantage_market_data import AlphaVantageMarketDataService
from src.services.alphavantage_response_formatter import AlphaVantageResponseFormatter

logger = structlog.get_logger()


def create_fundamental_tools(
    service: AlphaVantageMarketDataService, formatter: AlphaVantageResponseFormatter
) -> list:
    """
    Create fundamental analysis tools.

    Args:
        service: Initialized AlphaVantageMarketDataService instance
        formatter: AlphaVantageResponseFormatter for consistent markdown output

    Returns:
        List of fundamental analysis LangChain tools
    """

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
                return (
                    f"No ETF profile data available for {symbol} (verify it's an ETF)"
                )

            return formatter.format_etf_profile(
                raw_data=data,
                symbol=symbol,
                invoked_at=datetime.now(UTC).isoformat(),
            )
        except Exception as e:
            logger.error("ETF holdings tool failed", symbol=symbol, error=str(e))
            return f"ETF holdings error for {symbol}: {str(e)}"

    return [
        get_company_overview,
        get_financial_statements,
        get_insider_activity,
        get_etf_holdings,
    ]
