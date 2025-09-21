"""
Macro market sentiment analysis engine.
Analyzes VIX, major indices, and sector performance for market sentiment assessment.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import structlog

from ...api.models import MacroSentimentResponse

logger = structlog.get_logger()


class MacroAnalyzer:
    """Macro market sentiment analyzer."""

    def __init__(self):
        self.vix_data: Optional[pd.DataFrame] = None
        self.indices_data: Dict[str, pd.DataFrame] = {}
        self.sectors_data: Dict[str, pd.DataFrame] = {}

    async def analyze(self, include_sectors: bool = True, include_indices: bool = True) -> MacroSentimentResponse:
        """
        Analyze macro market sentiment.

        Args:
            include_sectors: Include sector rotation analysis
            include_indices: Include major indices analysis

        Returns:
            MacroSentimentResponse with complete sentiment analysis
        """
        try:
            logger.info("Starting macro sentiment analysis")

            # Get VIX data for fear/greed analysis
            vix_level, vix_interpretation, fear_greed_score = await self._analyze_vix()

            # Get major indices performance
            major_indices = {}
            if include_indices:
                major_indices = await self._analyze_major_indices()

            # Get sector performance
            sector_performance = {}
            if include_sectors:
                sector_performance = await self._analyze_sector_performance()

            # Overall sentiment assessment
            market_sentiment = self._assess_overall_sentiment(fear_greed_score, major_indices)
            confidence_level = self._calculate_confidence(vix_level, major_indices, sector_performance)

            # Generate insights
            sentiment_summary, market_outlook, key_factors = self._generate_macro_insights(
                vix_level, vix_interpretation, major_indices, sector_performance
            )

            response = MacroSentimentResponse(
                analysis_date=datetime.now().isoformat(),
                vix_level=vix_level,
                vix_interpretation=vix_interpretation,
                fear_greed_score=fear_greed_score,
                major_indices=major_indices,
                sector_performance=sector_performance,
                market_sentiment=market_sentiment,
                confidence_level=confidence_level,
                sentiment_summary=sentiment_summary,
                market_outlook=market_outlook,
                key_factors=key_factors
            )

            logger.info("Macro sentiment analysis completed", sentiment=market_sentiment)
            return response

        except Exception as e:
            logger.error("Macro sentiment analysis failed", error=str(e))
            raise

    async def _analyze_vix(self) -> Tuple[float, str, int]:
        """Analyze VIX for fear/greed sentiment."""
        try:
            vix_ticker = yf.Ticker("^VIX")
            vix_data = vix_ticker.history(period="5d")

            if vix_data.empty:
                # Fallback values if VIX data unavailable
                return 20.0, "neutral", 50

            current_vix = float(vix_data['Close'].iloc[-1])

            # VIX interpretation
            if current_vix > 30:
                interpretation = "fearful"
                fear_greed_score = max(0, 50 - int((current_vix - 30) * 2))
            elif current_vix < 15:
                interpretation = "greedy"
                fear_greed_score = min(100, 50 + int((15 - current_vix) * 3))
            else:
                interpretation = "neutral"
                fear_greed_score = 50

            return current_vix, interpretation, fear_greed_score

        except Exception as e:
            logger.warning("Failed to fetch VIX data", error=str(e))
            return 20.0, "neutral", 50

    async def _analyze_major_indices(self) -> Dict[str, float]:
        """Analyze major market indices performance."""
        indices = {
            "S&P 500": "^GSPC",
            "NASDAQ": "^IXIC",
            "DOW": "^DJI",
            "Russell 2000": "^RUT"
        }

        performance = {}
        for name, symbol in indices.items():
            try:
                ticker = yf.Ticker(symbol)
                data = ticker.history(period="5d")

                if not data.empty and len(data) >= 2:
                    change = ((data['Close'].iloc[-1] - data['Close'].iloc[-2]) / data['Close'].iloc[-2]) * 100
                    performance[name] = float(change)
                else:
                    performance[name] = 0.0

            except Exception as e:
                logger.warning(f"Failed to fetch {name} data", error=str(e))
                performance[name] = 0.0

        return performance

    async def _analyze_sector_performance(self) -> Dict[str, float]:
        """Analyze sector ETF performance."""
        sectors = {
            "Technology": "XLK",
            "Healthcare": "XLV",
            "Financial": "XLF",
            "Energy": "XLE",
            "Consumer Discretionary": "XLY",
            "Industrials": "XLI",
            "Communication": "XLC",
            "Consumer Staples": "XLP",
            "Utilities": "XLU",
            "Real Estate": "XLRE"
        }

        performance = {}
        for name, symbol in sectors.items():
            try:
                ticker = yf.Ticker(symbol)
                data = ticker.history(period="5d")

                if not data.empty and len(data) >= 2:
                    change = ((data['Close'].iloc[-1] - data['Close'].iloc[-2]) / data['Close'].iloc[-2]) * 100
                    performance[name] = float(change)
                else:
                    performance[name] = 0.0

            except Exception as e:
                logger.warning(f"Failed to fetch {name} sector data", error=str(e))
                performance[name] = 0.0

        return performance

    def _assess_overall_sentiment(self, fear_greed_score: int, major_indices: Dict[str, float]) -> str:
        """Assess overall market sentiment."""
        # Weight fear/greed score and market performance
        if major_indices:
            avg_performance = sum(major_indices.values()) / len(major_indices)
            if avg_performance > 1.0 and fear_greed_score > 60:
                return "greedy"
            elif avg_performance < -1.0 and fear_greed_score < 40:
                return "fearful"
            else:
                return "neutral"
        else:
            # Fallback to VIX-only assessment
            if fear_greed_score > 60:
                return "greedy"
            elif fear_greed_score < 40:
                return "fearful"
            else:
                return "neutral"

    def _calculate_confidence(self, vix_level: float, major_indices: Dict[str, float],
                             sector_performance: Dict[str, float]) -> float:
        """Calculate confidence in sentiment analysis."""
        data_quality = 0.7  # Base confidence

        # Boost confidence if we have good data coverage
        if major_indices and len(major_indices) > 3:
            data_quality += 0.1
        if sector_performance and len(sector_performance) > 5:
            data_quality += 0.1

        # Reduce confidence for extreme VIX readings (potential data issues)
        if vix_level > 50 or vix_level < 10:
            data_quality -= 0.2

        return min(1.0, max(0.0, data_quality))

    def _generate_macro_insights(self, vix_level: float, vix_interpretation: str,
                                major_indices: Dict[str, float],
                                sector_performance: Dict[str, float]) -> Tuple[str, str, List[str]]:
        """Generate human-readable macro insights."""

        # Sentiment summary
        sentiment_summary = f"Market sentiment is currently {vix_interpretation} with VIX at {vix_level:.1f}. "

        if major_indices:
            avg_performance = sum(major_indices.values()) / len(major_indices)
            if avg_performance > 0:
                sentiment_summary += f"Major indices are up an average of {avg_performance:.1f}% today."
            else:
                sentiment_summary += f"Major indices are down an average of {abs(avg_performance):.1f}% today."

        # Market outlook
        if vix_level > 25:
            outlook = "Elevated volatility suggests caution is warranted in the near term."
        elif vix_level < 15:
            outlook = "Low volatility environment may indicate complacency or strong confidence."
        else:
            outlook = "Moderate volatility suggests balanced market conditions."

        # Key factors
        key_factors = [
            f"VIX at {vix_level:.1f} indicates {vix_interpretation} sentiment",
        ]

        if major_indices:
            best_index = max(major_indices.items(), key=lambda x: x[1])
            worst_index = min(major_indices.items(), key=lambda x: x[1])
            key_factors.extend([
                f"Best performing index: {best_index[0]} ({best_index[1]:+.1f}%)",
                f"Worst performing index: {worst_index[0]} ({worst_index[1]:+.1f}%)"
            ])

        if sector_performance:
            sector_items = list(sector_performance.items())
            if sector_items:
                best_sector = max(sector_items, key=lambda x: x[1])
                key_factors.append(f"Leading sector: {best_sector[0]} ({best_sector[1]:+.1f}%)")

        return sentiment_summary, outlook, key_factors