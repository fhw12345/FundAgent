"""
News Sentiment Analysis Tools.

Provides tools for fetching news articles with sentiment analysis.
"""

from datetime import UTC, datetime

import structlog
from langchain_core.tools import tool

from src.services.alphavantage_market_data import AlphaVantageMarketDataService
from src.services.alphavantage_response_formatter import AlphaVantageResponseFormatter

logger = structlog.get_logger()


def create_news_tools(
    service: AlphaVantageMarketDataService, formatter: AlphaVantageResponseFormatter
) -> list:
    """
    Create news sentiment analysis tools.

    Args:
        service: Initialized AlphaVantageMarketDataService instance
        formatter: AlphaVantageResponseFormatter for consistent markdown output

    Returns:
        List of news analysis LangChain tools
    """

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

    return [get_news_sentiment]
