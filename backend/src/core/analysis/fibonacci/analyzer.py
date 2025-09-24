"""
Main Fibonacci analysis engine with modular architecture.
Orchestrates trend detection, level calculation, and pressure zone analysis using specialized components.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime
from typing import Optional
import structlog

from ....api.models import FibonacciAnalysisResponse
from ...utils import map_timeframe_to_yfinance_interval
from .config import TimeframeConfigs
from .trend_detector import TrendDetector
from .level_calculator import LevelCalculator

logger = structlog.get_logger()


class FibonacciAnalyzer:
    """Advanced Fibonacci pressure level analyzer with modular architecture."""

    def __init__(self):
        """Initialize analyzer with modular components."""
        self.data: Optional[pd.DataFrame] = None
        self.symbol: str = ""
        self.timeframe: str = "1d"
        self.config = None
        self.trend_detector: Optional[TrendDetector] = None
        self.level_calculator = LevelCalculator()

    async def analyze(self, symbol: str, start_date: Optional[str] = None,
                     end_date: Optional[str] = None, timeframe: str = '1d') -> FibonacciAnalysisResponse:
        """
        Perform advanced Fibonacci pressure level analysis with timeframe adaptation.

        Args:
            symbol: Stock symbol to analyze
            start_date: Start date for analysis (YYYY-MM-DD format)
            end_date: End date for analysis (YYYY-MM-DD format)
            timeframe: Timeframe for analysis ('1h', '1d', '1w', '1M')

        Returns:
            FibonacciAnalysisResponse with advanced pressure level analysis
        """
        try:
            logger.info("Starting advanced Fibonacci pressure analysis",
                       symbol=symbol, timeframe=timeframe, start_date=start_date, end_date=end_date)

            # Initialize components
            self.symbol = symbol.upper()
            self.timeframe = timeframe
            self.config = TimeframeConfigs.get_config(timeframe)
            self.trend_detector = TrendDetector(self.config)

            # Fetch stock data with timeframe-appropriate interval
            stock_data = await self._fetch_stock_data(start_date, end_date)
            if stock_data is None or stock_data.empty:
                raise ValueError(f"'{symbol}' is not a valid stock symbol or the stock may be delisted.")

            self.data = stock_data

            # Find swing points using trend detector
            swing_points = self.trend_detector.find_swing_points(self.data)

            # Detect top 3 most significant trends
            top_trends = self.trend_detector.detect_top_trends(self.data, swing_points)

            # Use the most significant trend for main analysis
            primary_trend = top_trends[0] if top_trends else None
            if not primary_trend:
                raise ValueError("Could not identify any significant trends in the data.")

            # Calculate analysis components
            current_price = float(stock_data['Close'].iloc[-1])

            # Create market structure from primary trend
            market_structure = self.level_calculator.create_market_structure(primary_trend, current_price)

            # Calculate Fibonacci levels for primary trend
            fibonacci_levels = self.level_calculator.calculate_fibonacci_levels(primary_trend)

            # Calculate confidence score
            confidence_score = self.level_calculator.calculate_confidence_score(top_trends, current_price)

            # Calculate golden ratio pressure zone
            pressure_zone = self.level_calculator.calculate_golden_pressure_zone(primary_trend)

            # Generate enhanced insights with pressure levels
            analysis_summary, key_insights = self._generate_pressure_insights(
                top_trends, fibonacci_levels, current_price
            )

            # Enhanced raw data with top 3 trends
            raw_data = self._build_raw_data(stock_data, top_trends, timeframe)

            response = FibonacciAnalysisResponse(
                symbol=self.symbol,
                start_date=start_date,
                end_date=end_date,
                timeframe=timeframe,
                current_price=current_price,
                analysis_date=datetime.now().isoformat(),
                fibonacci_levels=fibonacci_levels,
                market_structure=market_structure,
                confidence_score=confidence_score,
                pressure_zone=pressure_zone,
                trend_strength=self.level_calculator.assess_trend_strength(top_trends),
                analysis_summary=analysis_summary,
                key_insights=key_insights,
                raw_data=raw_data
            )

            logger.info("Advanced Fibonacci pressure analysis completed",
                       symbol=self.symbol, timeframe=timeframe,
                       top_trends_count=len(top_trends), confidence=confidence_score)

            return response

        except Exception as e:
            logger.error("Fibonacci analysis failed", symbol=symbol, error=str(e))
            raise

    async def _fetch_stock_data(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
        """Fetch stock data with timeframe-appropriate interval."""
        try:
            ticker = yf.Ticker(self.symbol)

            # Convert our timeframe to yfinance-compatible interval
            interval = map_timeframe_to_yfinance_interval(self.timeframe)

            if start_date and end_date:
                data = ticker.history(start=start_date, end=end_date, interval=interval)
            else:
                # Default periods for different timeframes
                period_map = {
                    '1h': '60d',  # 60 days max for hourly data
                    '1d': '6mo',
                    '1w': '2y',
                    '1M': '5y'
                }
                period = period_map.get(self.timeframe, '6mo')
                data = ticker.history(period=period, interval=interval)

            if data.empty:
                logger.error("No data returned for symbol", symbol=self.symbol)
                return pd.DataFrame()

            logger.info("Fetched stock data",
                       symbol=self.symbol, timeframe=self.timeframe,
                       data_points=len(data), start=data.index[0], end=data.index[-1])

            return data.dropna()

        except Exception as e:
            logger.error("Failed to fetch stock data", symbol=self.symbol, error=str(e))
            raise

    def _generate_pressure_insights(self, trends, fibonacci_levels, current_price):
        """Generate analysis insights focused on pressure zones and trend strength."""
        if not trends:
            return "No significant trends detected.", []

        primary_trend = trends[0]
        trend_type = primary_trend["Trend Type"]
        magnitude = primary_trend["Magnitude"]

        # Generate concise summary
        summary = f"Primary {trend_type.lower()} with ${magnitude:.0f} magnitude detected. "

        if len(trends) > 1:
            summary += f"Multiple trends identified ({len(trends)} total). "

        if "golden" in str(self.level_calculator.calculate_golden_pressure_zone(primary_trend)).lower():
            summary += "Golden ratio pressure zone active."

        # Generate key insights
        insights = [
            f"Strongest trend: {trend_type} (${magnitude:.0f} range)",
            f"Current price: ${current_price:.2f}",
            f"Key Fibonacci levels: {', '.join([f'{l.percentage}' for l in fibonacci_levels if l.is_key_level])}"
        ]

        if len(trends) >= 2:
            insights.append(f"Multiple timeframe confirmation with {len(trends)} significant trends")

        return summary, insights

    def _build_raw_data(self, stock_data, top_trends, timeframe):
        """Build comprehensive raw data for debugging and agent use."""
        return {
            "timeframe": timeframe,
            "data_points": len(stock_data),
            "date_range": {
                "start": stock_data.index[0].strftime('%Y-%m-%d'),
                "end": stock_data.index[-1].strftime('%Y-%m-%d')
            },
            "price_range": {
                "high": float(stock_data['High'].max()),
                "low": float(stock_data['Low'].min())
            },
            "swing_detection_params": {
                "lookback": self.config.swing_lookback,
                "prominence": self.config.prominence,
                "window_size": self.config.rolling_window_size
            },
            "top_trends": [
                {
                    "rank": i + 1,
                    "type": trend["Trend Type"],
                    "period": f"{trend['Start Date']} to {trend['End Date']}",
                    "magnitude": trend["Magnitude"],
                    "high": trend["Absolute High"],
                    "low": trend["Absolute Low"],
                    "fibonacci_levels": self.level_calculator.get_fibonacci_levels_for_trend(trend)
                }
                for i, trend in enumerate(top_trends[:3])
            ],
            "pressure_zones": [
                self.level_calculator.calculate_golden_pressure_zone(trend)
                for trend in top_trends[:3]
            ],
            "calculation_method": "advanced_multi_trend_detection"
        }