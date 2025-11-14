"""
Alpha Vantage Agent Tools for LLM Access.

Provides compressed tool outputs (2-3 lines) for efficient context usage.
All tools use AlphaVantageMarketDataService for market data access.
"""

import structlog
from langchain_core.tools import tool

from ...services.alphavantage_market_data import AlphaVantageMarketDataService

logger = structlog.get_logger()


def create_alpha_vantage_tools(service: AlphaVantageMarketDataService) -> list:
    """
    Create Alpha Vantage agent tools with service dependency injection.

    Args:
        service: Initialized AlphaVantageMarketDataService instance

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

            # Helper function for safe float conversion
            def safe_float(value, default="N/A"):
                try:
                    return float(value) if value and value != "None" else default
                except (ValueError, TypeError):
                    return default

            # Extract company info
            name = data.get("Name", "N/A")
            description = data.get("Description", "N/A")
            industry = data.get("Industry", "N/A")
            sector = data.get("Sector", "N/A")
            exchange = data.get("Exchange", "N/A")
            country = data.get("Country", "N/A")

            # Extract key metrics
            market_cap = safe_float(data.get("MarketCapitalization"))
            pe_ratio = safe_float(data.get("PERatio"))
            eps = safe_float(data.get("EPS"))
            profit_margin = safe_float(data.get("ProfitMargin"))
            revenue_ttm = safe_float(data.get("RevenueTTM"))
            dividend_yield = safe_float(data.get("DividendYield"))
            beta = safe_float(data.get("Beta"))

            # Ownership metrics
            percent_insiders = safe_float(data.get("PercentInsiders"))
            percent_institutions = safe_float(data.get("PercentInstitutions"))

            # Price metrics
            week_52_high = safe_float(data.get("52WeekHigh"))
            week_52_low = safe_float(data.get("52WeekLow"))

            # Format output with Key Metrics table
            output_lines = [
                f"## {symbol} - {name}",
                "",
                f"**Industry**: {industry} | **Sector**: {sector}",
                f"**Exchange**: {exchange} | **Country**: {country}",
                "",
                f"**Description**: {description}",
                "",
                "### Key Metrics",
                "",
            ]

            # Build metrics table
            metrics = []

            if market_cap != "N/A":
                metrics.append(f"**Market Cap**: ${market_cap/1e9:.2f}B")
            if pe_ratio != "N/A":
                metrics.append(f"**P/E Ratio**: {pe_ratio:.2f}")
            if eps != "N/A":
                metrics.append(f"**EPS**: ${eps:.2f}")
            if profit_margin != "N/A":
                metrics.append(f"**Profit Margin**: {profit_margin*100:.2f}%")
            if revenue_ttm != "N/A":
                metrics.append(f"**Revenue (TTM)**: ${revenue_ttm/1e9:.2f}B")
            if dividend_yield != "N/A":
                metrics.append(f"**Dividend Yield**: {dividend_yield*100:.2f}%")
            if beta != "N/A":
                metrics.append(f"**Beta**: {beta:.2f}")
            if percent_insiders != "N/A":
                metrics.append(f"**% Insiders**: {percent_insiders:.2f}%")
            if percent_institutions != "N/A":
                metrics.append(f"**% Institutions**: {percent_institutions:.2f}%")
            if week_52_high != "N/A":
                metrics.append(f"**52W High**: ${week_52_high:.2f}")
            if week_52_low != "N/A":
                metrics.append(f"**52W Low**: ${week_52_low:.2f}")

            # Format in table-like structure (2 columns)
            for i in range(0, len(metrics), 2):
                if i + 1 < len(metrics):
                    output_lines.append(f"{metrics[i]} | {metrics[i+1]}")
                else:
                    output_lines.append(metrics[i])

            return "\n".join(output_lines)

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

            feed = data.get("feed", [])
            if not feed:
                return f"No news sentiment data available for {symbol}"

            # Filter and sort by sentiment
            positive_news = [
                item for item in feed if item.get("overall_sentiment_score", 0) > 0.15
            ]
            negative_news = [
                item for item in feed if item.get("overall_sentiment_score", 0) < -0.15
            ]

            # Sort and limit
            positive_news = sorted(
                positive_news,
                key=lambda x: x.get("overall_sentiment_score", 0),
                reverse=True,
            )[:max_positive]

            negative_news = sorted(
                negative_news, key=lambda x: x.get("overall_sentiment_score", 0)
            )[:max_negative]

            # Format output
            output_lines = [f"News Sentiment for {symbol}:"]

            if positive_news:
                output_lines.append(f"\n✅ POSITIVE ({len(positive_news)}):")
                for item in positive_news:
                    score = item.get("overall_sentiment_score", 0)
                    title = item.get("title", "")[:80]
                    source = item.get("source", "Unknown")
                    output_lines.append(f"  • [{score:+.2f}] {title}... ({source})")

            if negative_news:
                output_lines.append(f"\n❌ NEGATIVE ({len(negative_news)}):")
                for item in negative_news:
                    score = item.get("overall_sentiment_score", 0)
                    title = item.get("title", "")[:80]
                    source = item.get("source", "Unknown")
                    output_lines.append(f"  • [{score:+.2f}] {title}... ({source})")

            if not positive_news and not negative_news:
                output_lines.append("No strongly positive or negative news found")

            return "\n".join(output_lines)

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
            else:
                data = await service.get_balance_sheet(symbol)

            annual = data.get("annualReports", [])
            quarterly = data.get("quarterlyReports", [])

            if not annual and not quarterly:
                return f"No {statement_type} data available for {symbol}"

            # Format latest reports
            output_lines = [f"{symbol} - {statement_type.replace('_', ' ').title()}:"]

            if annual:
                latest_annual = annual[0]
                fiscal_date = latest_annual.get("fiscalDateEnding", "N/A")
                output_lines.append(f"\n📊 Latest Annual ({fiscal_date}):")

                if statement_type == "cash_flow":
                    operating = latest_annual.get("operatingCashflow", "N/A")
                    capex = latest_annual.get("capitalExpenditures", "N/A")
                    try:
                        fcf = int(operating) - abs(int(capex))
                        output_lines.append(
                            f"  Operating CF: ${int(operating)/1e6:.0f}M, "
                            f"CapEx: ${abs(int(capex))/1e6:.0f}M, Free CF: ${fcf/1e6:.0f}M"
                        )
                    except (ValueError, TypeError):
                        output_lines.append(
                            f"  Operating CF: {operating}, CapEx: {capex}"
                        )
                else:  # balance_sheet
                    assets = latest_annual.get("totalAssets", "N/A")
                    liabilities = latest_annual.get("totalLiabilities", "N/A")
                    equity = latest_annual.get("totalShareholderEquity", "N/A")
                    try:
                        output_lines.append(
                            f"  Assets: ${int(assets)/1e6:.0f}M, "
                            f"Liabilities: ${int(liabilities)/1e6:.0f}M, "
                            f"Equity: ${int(equity)/1e6:.0f}M"
                        )
                    except (ValueError, TypeError):
                        output_lines.append(
                            f"  Assets: {assets}, Liabilities: {liabilities}, Equity: {equity}"
                        )

            if quarterly:
                latest_quarterly = quarterly[0]
                fiscal_date = latest_quarterly.get("fiscalDateEnding", "N/A")
                output_lines.append(f"\n📈 Latest Quarterly ({fiscal_date}):")

                if statement_type == "cash_flow":
                    operating = latest_quarterly.get("operatingCashflow", "N/A")
                    output_lines.append(f"  Operating CF: ${int(operating)/1e6:.0f}M")
                else:
                    assets = latest_quarterly.get("totalAssets", "N/A")
                    output_lines.append(f"  Total Assets: ${int(assets)/1e6:.0f}M")

            return "\n".join(output_lines)

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

            gainers = data.get("top_gainers", [])[:5]
            losers = data.get("top_losers", [])[:5]
            active = data.get("most_actively_traded", [])[:5]

            output_lines = ["📊 Today's Market Movers:"]

            if gainers:
                output_lines.append("\n📈 TOP GAINERS:")
                for stock in gainers:
                    ticker = stock.get("ticker", "N/A")
                    price = stock.get("price", "N/A")
                    change = stock.get("change_percentage", "N/A")
                    output_lines.append(f"  • {ticker}: ${price} ({change})")

            if losers:
                output_lines.append("\n📉 TOP LOSERS:")
                for stock in losers:
                    ticker = stock.get("ticker", "N/A")
                    price = stock.get("price", "N/A")
                    change = stock.get("change_percentage", "N/A")
                    output_lines.append(f"  • {ticker}: ${price} ({change})")

            if active:
                output_lines.append("\n🔥 MOST ACTIVE:")
                for stock in active:
                    ticker = stock.get("ticker", "N/A")
                    price = stock.get("price", "N/A")
                    volume = stock.get("volume", "N/A")
                    try:
                        vol_str = f"{int(volume)/1e6:.1f}M"
                    except (ValueError, TypeError):
                        vol_str = str(volume)
                    output_lines.append(f"  • {ticker}: ${price} (Vol: {vol_str})")

            return "\n".join(output_lines)

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
