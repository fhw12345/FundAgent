"""
Fibonacci retracement analysis engine.
Provides technical analysis using Fibonacci levels for market structure analysis.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import structlog

from ...api.models import (
    FibonacciAnalysisResponse, FibonacciLevel, MarketStructure, PricePoint
)

logger = structlog.get_logger()


class FibonacciAnalyzer:
    """Fibonacci retracement analysis engine."""

    # Standard Fibonacci levels
    FIBONACCI_LEVELS = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
    KEY_LEVELS = [0.382, 0.5, 0.618]  # Most important levels
    GOLDEN_RATIO = 0.618
    PRESSURE_ZONE_TOLERANCE = 0.025  # ±2.5% around 61.8%

    def __init__(self):
        self.data: Optional[pd.DataFrame] = None
        self.symbol: str = ""
        self.start_date: Optional[str] = None
        self.end_date: Optional[str] = None

    async def analyze(self, symbol: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> FibonacciAnalysisResponse:
        """
        Perform complete Fibonacci analysis on a stock symbol.

        Args:
            symbol: Stock symbol to analyze
            start_date: Start date for analysis (YYYY-MM-DD format)
            end_date: End date for analysis (YYYY-MM-DD format)

        Returns:
            FibonacciAnalysisResponse with complete analysis
        """
        try:
            logger.info("Starting Fibonacci analysis", symbol=symbol, start_date=start_date, end_date=end_date)

            self.symbol = symbol.upper()
            self.start_date = start_date
            self.end_date = end_date

            # Fetch stock data
            stock_data = await self._fetch_stock_data()
            if stock_data is None or stock_data.empty:
                raise ValueError(f"'{symbol}' is not a valid stock symbol or the stock may be delisted. Please check the symbol and try again.")

            self.data = stock_data

            # Perform market structure analysis
            market_structure = self._analyze_market_structure()

            # Calculate Fibonacci levels
            fibonacci_levels = self._calculate_fibonacci_levels(market_structure)

            # Get current price and analysis metrics
            current_price = float(stock_data['Close'].iloc[-1])
            confidence_score = self._calculate_confidence_score(market_structure, fibonacci_levels)

            # Generate insights and summary
            analysis_summary, key_insights = self._generate_analysis_insights(
                market_structure, fibonacci_levels, current_price
            )

            # Calculate pressure zone around Golden Ratio
            pressure_zone = self._calculate_pressure_zone(fibonacci_levels)

            # Prepare raw data for debugging/agent use
            raw_data = {
                "data_points": len(stock_data),
                "date_range": {
                    "start": self._format_date_safe(stock_data.index[0]),
                    "end": self._format_date_safe(stock_data.index[-1])
                },
                "price_range": {
                    "high": float(stock_data['High'].max()),
                    "low": float(stock_data['Low'].min())
                },
                "volume_avg": float(stock_data['Volume'].mean()),
                "calculation_method": "swing_point_detection"
            }

            response = FibonacciAnalysisResponse(
                symbol=self.symbol,
                start_date=self.start_date,
                end_date=self.end_date,
                current_price=current_price,
                analysis_date=datetime.now().isoformat(),
                fibonacci_levels=fibonacci_levels,
                market_structure=market_structure,
                confidence_score=confidence_score,
                pressure_zone=pressure_zone,
                trend_strength=self._assess_trend_strength(market_structure),
                analysis_summary=analysis_summary,
                key_insights=key_insights,
                raw_data=raw_data
            )

            logger.info("Fibonacci analysis completed",
                       symbol=symbol,
                       confidence=confidence_score,
                       trend=market_structure.trend_direction)

            return response

        except Exception as e:
            logger.error("Fibonacci analysis failed", symbol=symbol, error=str(e))
            raise

    async def _fetch_stock_data(self) -> Optional[pd.DataFrame]:
        """Fetch stock data using yfinance."""
        try:
            ticker = yf.Ticker(self.symbol)

            # Only use specified date range for Fibonacci analysis
            if not self.start_date or not self.end_date:
                raise ValueError("Both start_date and end_date are required for Fibonacci analysis")

            data = ticker.history(start=self.start_date, end=self.end_date)

            if data.empty:
                return None

            # Clean data
            data = data.dropna()
            return data

        except Exception as e:
            logger.error("Failed to fetch stock data", symbol=self.symbol, error=str(e))
            raise

    def _analyze_market_structure(self) -> MarketStructure:
        """Analyze market structure to identify swing points and trend."""
        if self.data is None:
            raise ValueError("No data available for market structure analysis")

        # Find significant swing points
        swing_high, swing_low = self._find_swing_points()

        # Determine trend direction
        trend_direction = self._determine_trend_direction(swing_high, swing_low)

        # Assess structure quality
        structure_quality = self._assess_structure_quality(swing_high, swing_low)

        # Determine market phase
        current_price = float(self.data['Close'].iloc[-1])
        phase = self._determine_market_phase(current_price, swing_high, swing_low)

        return MarketStructure(
            trend_direction=trend_direction,
            swing_high=PricePoint(
                price=swing_high['price'],
                date=swing_high['date']  # Already formatted as string by format_date_safe
            ),
            swing_low=PricePoint(
                price=swing_low['price'],
                date=swing_low['date']  # Already formatted as string by format_date_safe
            ),
            structure_quality=structure_quality,
            phase=phase
        )

    def _find_swing_points(self) -> Tuple[Dict, Dict]:
        """Find significant swing high and low points."""
        high_prices = self.data['High']
        low_prices = self.data['Low']

        # Use rolling windows to find local extremes
        window = max(5, len(self.data) // 20)  # Adaptive window size

        # Find swing high (highest high in recent period)
        try:
            rolling_highs = high_prices.rolling(window=window, center=True).max()
            if rolling_highs.isna().all():
                # Fallback: use overall max
                swing_high_idx = high_prices.idxmax()
            else:
                swing_high_idx = rolling_highs.idxmax()

            swing_high = {
                'price': float(high_prices[swing_high_idx]),
                'date': self._format_date_safe(swing_high_idx)
            }
        except (ValueError, TypeError):
            # Emergency fallback
            swing_high_idx = high_prices.idxmax()
            swing_high = {
                'price': float(high_prices[swing_high_idx]),
                'date': self._format_date_safe(swing_high_idx)
            }

        # Find swing low (lowest low in recent period)
        try:
            rolling_lows = low_prices.rolling(window=window, center=True).min()
            if rolling_lows.isna().all():
                # Fallback: use overall min
                swing_low_idx = low_prices.idxmin()
            else:
                swing_low_idx = rolling_lows.idxmin()

            swing_low = {
                'price': float(low_prices[swing_low_idx]),
                'date': self._format_date_safe(swing_low_idx)
            }
        except (ValueError, TypeError):
            # Emergency fallback
            swing_low_idx = low_prices.idxmin()
            swing_low = {
                'price': float(low_prices[swing_low_idx]),
                'date': self._format_date_safe(swing_low_idx)
            }

        # Ensure we have a meaningful range
        if swing_high['price'] <= swing_low['price']:
            # Fallback to period high/low
            swing_high = {
                'price': float(high_prices.max()),
                'date': self._format_date_safe(high_prices.idxmax())
            }
            swing_low = {
                'price': float(low_prices.min()),
                'date': self._format_date_safe(low_prices.idxmin())
            }

        return swing_high, swing_low

    def _format_date_safe(self, date_idx):
        """Safely format date index to YYYY-MM-DD string"""
        try:
            if hasattr(date_idx, 'strftime'):
                return date_idx.strftime('%Y-%m-%d')
            elif hasattr(date_idx, 'date'):
                return date_idx.date().strftime('%Y-%m-%d')
            else:
                # Already a string or other format
                date_str = str(date_idx)
                # If it's already in YYYY-MM-DD format, keep it
                if len(date_str) >= 10 and date_str[4] == '-' and date_str[7] == '-':
                    return date_str[:10]
                return date_str
        except:
            return str(date_idx)

    def _determine_trend_direction(self, swing_high: Dict, swing_low: Dict) -> str:
        """Determine overall trend direction."""
        # Simple trend analysis based on recent price action
        recent_data = self.data.tail(20)  # Last 20 periods

        if len(recent_data) < 10:
            return "sideways"

        start_price = float(recent_data['Close'].iloc[0])
        end_price = float(recent_data['Close'].iloc[-1])
        price_change_pct = (end_price - start_price) / start_price * 100

        if price_change_pct > 2:
            return "uptrend"
        elif price_change_pct < -2:
            return "downtrend"
        else:
            return "sideways"

    def _assess_structure_quality(self, swing_high: Dict, swing_low: Dict) -> str:
        """Assess the quality of market structure."""
        price_range = swing_high['price'] - swing_low['price']
        current_price = float(self.data['Close'].iloc[-1])

        # Quality based on range significance and data points
        range_pct = price_range / current_price * 100
        data_length = len(self.data)

        if range_pct > 15 and data_length > 100:
            return "high"
        elif range_pct > 8 and data_length > 50:
            return "medium"
        else:
            return "low"

    def _determine_market_phase(self, current_price: float, swing_high: Dict, swing_low: Dict) -> str:
        """Determine current market phase."""
        price_range = swing_high['price'] - swing_low['price']
        position_in_range = (current_price - swing_low['price']) / price_range

        if position_in_range > 0.8:
            return "Near swing high - potential resistance"
        elif position_in_range < 0.2:
            return "Near swing low - potential support"
        elif 0.35 <= position_in_range <= 0.65:
            return "Middle range - watch for direction"
        else:
            return "In retracement zone"

    def _calculate_fibonacci_levels(self, market_structure: MarketStructure) -> List[FibonacciLevel]:
        """Calculate Fibonacci retracement levels."""
        high_price = market_structure.swing_high.price
        low_price = market_structure.swing_low.price
        price_range = high_price - low_price

        fibonacci_levels = []

        for level in self.FIBONACCI_LEVELS:
            # Calculate price at this Fibonacci level
            if market_structure.trend_direction == "downtrend":
                # For downtrends, calculate from high down
                fib_price = high_price - (price_range * level)
            else:
                # For uptrends, calculate from low up
                fib_price = low_price + (price_range * level)

            fibonacci_levels.append(FibonacciLevel(
                level=level,
                price=fib_price,
                percentage=f"{level * 100:.1f}%",
                is_key_level=level in self.KEY_LEVELS
            ))

        return fibonacci_levels

    def _calculate_confidence_score(self, market_structure: MarketStructure, fibonacci_levels: List[FibonacciLevel]) -> float:
        """Calculate confidence score for the analysis."""
        score = 0.5  # Base score

        # Adjust based on structure quality
        if market_structure.structure_quality == "high":
            score += 0.3
        elif market_structure.structure_quality == "medium":
            score += 0.1

        # Adjust based on data length
        if len(self.data) > 100:
            score += 0.1

        # Adjust based on price range significance
        current_price = float(self.data['Close'].iloc[-1])
        price_range = market_structure.swing_high.price - market_structure.swing_low.price
        range_pct = price_range / current_price * 100

        if range_pct > 20:
            score += 0.1

        return min(score, 1.0)

    def _calculate_pressure_zone(self, fibonacci_levels: List[FibonacciLevel]) -> Optional[Dict[str, float]]:
        """Calculate pressure zone around the Golden Ratio level."""
        golden_ratio_level = None

        for level in fibonacci_levels:
            if abs(level.level - self.GOLDEN_RATIO) < 0.001:  # Find 61.8% level
                golden_ratio_level = level
                break

        if golden_ratio_level is None:
            return None

        price_tolerance = golden_ratio_level.price * self.PRESSURE_ZONE_TOLERANCE

        return {
            "center_price": golden_ratio_level.price,
            "upper_bound": golden_ratio_level.price + price_tolerance,
            "lower_bound": golden_ratio_level.price - price_tolerance,
            "tolerance_percent": self.PRESSURE_ZONE_TOLERANCE * 100
        }

    def _assess_trend_strength(self, market_structure: MarketStructure) -> str:
        """Assess the strength of the current trend."""
        if market_structure.structure_quality == "high":
            return "Strong"
        elif market_structure.structure_quality == "medium":
            return "Moderate"
        else:
            return "Weak"

    def _generate_analysis_insights(self, market_structure: MarketStructure, fibonacci_levels: List[FibonacciLevel], current_price: float) -> Tuple[str, List[str]]:
        """Generate human-readable analysis summary and key insights."""

        # Find current price position relative to Fibonacci levels
        current_position = self._find_current_fib_position(fibonacci_levels, current_price)

        # Generate summary
        summary = (
            f"{self.symbol} is currently in a {market_structure.trend_direction} with {market_structure.structure_quality} "
            f"quality market structure. The stock is trading {current_position} and shows "
            f"{self._assess_trend_strength(market_structure).lower()} trend characteristics."
        )

        # Generate key insights
        key_insights = [
            f"Market Structure: {market_structure.structure_quality.title()} quality {market_structure.trend_direction}",
            f"Current Phase: {market_structure.phase}",
            f"Price Position: {current_position}",
            f"Swing High: ${market_structure.swing_high.price:.2f} ({market_structure.swing_high.date})",
            f"Swing Low: ${market_structure.swing_low.price:.2f} ({market_structure.swing_low.date})"
        ]

        # Add pressure zone insight if applicable
        golden_ratio_level = next((level for level in fibonacci_levels if level.level == self.GOLDEN_RATIO), None)
        if golden_ratio_level:
            distance_to_golden = abs(current_price - golden_ratio_level.price) / current_price * 100
            if distance_to_golden < 5:  # Within 5% of golden ratio
                key_insights.append(f"⚠️ Near Golden Ratio (61.8%) at ${golden_ratio_level.price:.2f} - key decision point")

        return summary, key_insights

    def _find_current_fib_position(self, fibonacci_levels: List[FibonacciLevel], current_price: float) -> str:
        """Determine where current price sits relative to Fibonacci levels."""
        sorted_levels = sorted(fibonacci_levels, key=lambda x: x.price)

        for i, level in enumerate(sorted_levels):
            if current_price <= level.price:
                if i == 0:
                    return f"below the {level.percentage} level at ${level.price:.2f}"
                else:
                    prev_level = sorted_levels[i-1]
                    return f"between {prev_level.percentage} (${prev_level.price:.2f}) and {level.percentage} (${level.price:.2f})"

        return f"above the {sorted_levels[-1].percentage} level at ${sorted_levels[-1].price:.2f}"