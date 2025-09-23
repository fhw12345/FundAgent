"""
Advanced Fibonacci pressure level analysis engine.
Provides timeframe-adaptive technical analysis using multi-trend detection and golden ratio pressure zones.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from scipy.signal import find_peaks
import structlog

from ...api.models import (
    FibonacciAnalysisResponse, FibonacciLevel, MarketStructure, PricePoint
)

logger = structlog.get_logger()

@dataclass
class SwingPoint:
    """Represents a swing high or low point."""
    index: int
    type: str  # 'high' or 'low'
    price: float
    date: date

@dataclass
class TimeframeConfig:
    """Configuration for different timeframes."""
    interval: str
    swing_lookback: int
    prominence: float
    single_leg_min_magnitude: float
    rolling_window_size: int
    rolling_min_magnitude: float

class FibonacciAnalyzer:
    """Advanced Fibonacci pressure level analyzer with timeframe adaptation."""

    # Standard Fibonacci levels
    FIBONACCI_LEVELS = [0.0, 0.236, 0.382, 0.5, 0.615, 0.618, 0.786, 1.0]
    KEY_LEVELS = [0.382, 0.5, 0.618]  # Most important levels
    GOLDEN_RATIO = 0.618
    GOLDEN_ZONE_START = 0.615  # Golden pressure zone
    GOLDEN_ZONE_END = 0.618

    # Timeframe configurations - adapted for different market scales
    TIMEFRAME_CONFIGS = {
        '1d': TimeframeConfig('1d', 3, 0.5, 15, 10, 25),      # Daily: sensitive to short-term moves
        '1w': TimeframeConfig('1wk', 2, 1.0, 20, 10, 30),     # Weekly: very sensitive
        '1M': TimeframeConfig('1mo', 1, 1.5, 15, 4, 25)       # Monthly: very sensitive
    }

    def __init__(self):
        self.data: Optional[pd.DataFrame] = None
        self.symbol: str = ""
        self.timeframe: str = "1d"
        self.config: TimeframeConfig = self.TIMEFRAME_CONFIGS['1d']

    async def analyze(self, symbol: str, start_date: Optional[str] = None, end_date: Optional[str] = None, timeframe: str = '1d') -> FibonacciAnalysisResponse:
        """
        Perform advanced Fibonacci pressure level analysis with timeframe adaptation.

        Args:
            symbol: Stock symbol to analyze
            start_date: Start date for analysis (YYYY-MM-DD format)
            end_date: End date for analysis (YYYY-MM-DD format)
            timeframe: Timeframe for analysis ('1d', '1w', '1M')

        Returns:
            FibonacciAnalysisResponse with advanced pressure level analysis
        """
        try:
            logger.info("Starting advanced Fibonacci pressure analysis",
                       symbol=symbol, timeframe=timeframe, start_date=start_date, end_date=end_date)

            self.symbol = symbol.upper()
            self.timeframe = timeframe
            self.config = self.TIMEFRAME_CONFIGS.get(timeframe, self.TIMEFRAME_CONFIGS['1d'])

            # Fetch stock data with timeframe-appropriate interval
            stock_data = await self._fetch_stock_data_advanced(start_date, end_date)
            if stock_data is None or stock_data.empty:
                raise ValueError(f"'{symbol}' is not a valid stock symbol or the stock may be delisted.")

            self.data = stock_data

            # Find swing points with timeframe-adaptive parameters
            swing_points = self._find_swing_points_advanced()

            # Detect top 3 most significant trends
            top_trends = self._detect_top_trends(swing_points)

            # Use the most significant trend for main analysis
            primary_trend = top_trends[0] if top_trends else None

            if not primary_trend:
                raise ValueError("Could not identify any significant trends in the data.")

            # Create market structure from primary trend
            market_structure = self._create_market_structure(primary_trend)

            # Calculate Fibonacci levels for primary trend
            fibonacci_levels = self._calculate_fibonacci_levels_advanced(primary_trend)

            # Current price and confidence
            current_price = float(stock_data['Close'].iloc[-1])
            confidence_score = self._calculate_confidence_score_advanced(top_trends, current_price)

            # Generate enhanced insights with pressure levels
            analysis_summary, key_insights = self._generate_pressure_insights(
                top_trends, fibonacci_levels, current_price
            )

            # Calculate golden ratio pressure zone (61.5% - 61.8%)
            pressure_zone = self._calculate_golden_pressure_zone(primary_trend)

            # Enhanced raw data with top 3 trends
            raw_data = {
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
                        "fibonacci_levels": self._get_fibonacci_levels_for_trend(trend)
                    }
                    for i, trend in enumerate(top_trends[:3])
                ],
                "pressure_zones": [
                    {
                        **self._calculate_golden_pressure_zone(trend),
                        "trend_type": trend["Trend Type"]  # Include trend type in raw_data only
                    }
                    for trend in top_trends[:3]
                ],
                "calculation_method": "advanced_multi_trend_detection"
            }

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
                trend_strength=self._assess_trend_strength_advanced(top_trends),
                analysis_summary=analysis_summary,
                key_insights=key_insights,
                raw_data=raw_data
            )

            logger.info("Advanced Fibonacci pressure analysis completed",
                       symbol=symbol,
                       timeframe=timeframe,
                       top_trends_count=len(top_trends),
                       confidence=confidence_score)

            return response

        except Exception as e:
            logger.error("Advanced Fibonacci analysis failed", symbol=symbol, error=str(e))
            raise

    async def _fetch_stock_data_advanced(self, start_date: Optional[str], end_date: Optional[str]) -> pd.DataFrame:
        """Fetch stock data with timeframe-appropriate settings."""
        try:
            ticker = yf.Ticker(self.symbol)

            # Default to 1 year if no dates provided
            if not start_date or not end_date:
                data = ticker.history(period="1y", interval=self.config.interval)
            else:
                data = ticker.history(start=start_date, end=end_date, interval=self.config.interval)

            if data.empty:
                raise ValueError(f"No data available for {self.symbol}")

            return data.dropna()

        except Exception as e:
            logger.error("Failed to fetch stock data", symbol=self.symbol, error=str(e))
            raise

    def _find_swing_points_advanced(self) -> List[SwingPoint]:
        """Find swing points using timeframe-adaptive parameters."""
        if self.data is None or self.data.empty:
            return []

        # Find peaks and troughs using scipy with adaptive parameters
        high_peaks, _ = find_peaks(
            self.data['High'],
            distance=self.config.swing_lookback,
            prominence=self.config.prominence
        )
        low_peaks, _ = find_peaks(
            -self.data['Low'],
            distance=self.config.swing_lookback,
            prominence=self.config.prominence
        )

        swing_points = []

        # Add high points
        for i in high_peaks:
            swing_points.append(SwingPoint(
                index=i,
                type='high',
                price=self.data['High'].iloc[i],
                date=self.data.index[i].date()
            ))

        # Add low points
        for i in low_peaks:
            swing_points.append(SwingPoint(
                index=i,
                type='low',
                price=self.data['Low'].iloc[i],
                date=self.data.index[i].date()
            ))

        # Sort by index
        swing_points.sort(key=lambda x: x.index)

        logger.info("Found swing points",
                   high_count=len(high_peaks),
                   low_count=len(low_peaks),
                   total=len(swing_points))

        return swing_points

    def _detect_top_trends(self, swing_points: List[SwingPoint]) -> List[Dict[str, Any]]:
        """Detect and rank the top trending moves."""
        all_trends = []

        # 1. Traditional swing-based trends
        swing_trends = self._detect_swing_based_trends(swing_points)
        all_trends.extend(swing_trends)

        # 2. Single-leg moves between swing points
        single_leg_trends = self._detect_single_leg_moves(swing_points)
        all_trends.extend(single_leg_trends)

        # 3. Rolling window significant moves
        rolling_trends = self._detect_rolling_window_moves()
        all_trends.extend(rolling_trends)

        # Remove overlapping trends
        unique_trends = self._remove_overlapping_trends(all_trends)

        # Sort by magnitude and return top trends
        unique_trends.sort(key=lambda x: x['Magnitude'], reverse=True)

        logger.info("Detected trends",
                   total_detected=len(all_trends),
                   unique_trends=len(unique_trends),
                   top_3_magnitudes=[t['Magnitude'] for t in unique_trends[:3]])

        return unique_trends

    def _detect_swing_based_trends(self, swing_points: List[SwingPoint]) -> List[Dict[str, Any]]:
        """Detect trends based on higher highs/higher lows patterns."""
        trends = []
        i = 0

        while i < len(swing_points) - 2:
            p1, p2, p3 = swing_points[i], swing_points[i + 1], swing_points[i + 2]

            # Uptrend: Low -> High -> Higher Low
            if (p1.type == 'low' and p2.type == 'high' and p3.type == 'low' and
                p3.price > p1.price):

                trend_end, next_i = self._find_trend_continuation(swing_points, i, is_uptrend=True)
                data_slice = self.data.iloc[p1.index:trend_end.index + 1]

                trends.append(self._create_trend_dict(
                    "Uptrend", p1.date, trend_end.date, data_slice))
                i = next_i
                continue

            # Downtrend: High -> Low -> Lower High
            elif (p1.type == 'high' and p2.type == 'low' and p3.type == 'high' and
                  p3.price < p1.price):

                trend_end, next_i = self._find_trend_continuation(swing_points, i, is_uptrend=False)
                data_slice = self.data.iloc[p1.index:trend_end.index + 1]

                trends.append(self._create_trend_dict(
                    "Downtrend", p1.date, trend_end.date, data_slice))
                i = next_i
                continue

            i += 1

        return trends

    def _find_trend_continuation(self, swing_points: List[SwingPoint], start_idx: int, is_uptrend: bool) -> Tuple[SwingPoint, int]:
        """Find where a trend pattern ends."""
        current_high = swing_points[start_idx + 1] if is_uptrend else swing_points[start_idx]
        current_low = swing_points[start_idx + 2] if is_uptrend else swing_points[start_idx + 1]

        j = start_idx + 3
        while j < len(swing_points) - 1:
            next_point1 = swing_points[j]
            next_point2 = swing_points[j + 1]

            if is_uptrend:
                if (next_point1.type == 'high' and next_point2.type == 'low' and
                    next_point1.price > current_high.price and next_point2.price > current_low.price):
                    current_high = next_point1
                    current_low = next_point2
                    j += 2
                else:
                    break
            else:
                if (next_point1.type == 'low' and next_point2.type == 'high' and
                    next_point1.price < current_low.price and next_point2.price < current_high.price):
                    current_low = next_point1
                    current_high = next_point2
                    j += 2
                else:
                    break

        trend_end = current_high if is_uptrend else current_low
        return trend_end, j - 1

    def _detect_single_leg_moves(self, swing_points: List[SwingPoint]) -> List[Dict[str, Any]]:
        """Detect single-leg moves between consecutive swing points."""
        trends = []

        for i in range(len(swing_points) - 1):
            current = swing_points[i]
            next_swing = swing_points[i + 1]

            magnitude = abs(current.price - next_swing.price)
            if magnitude < self.config.single_leg_min_magnitude:
                continue

            data_slice = self.data.iloc[current.index:next_swing.index + 1]

            if current.type == 'high' and next_swing.type == 'low':
                trend_type = "Downtrend (Single-leg)"
            elif current.type == 'low' and next_swing.type == 'high':
                trend_type = "Uptrend (Single-leg)"
            else:
                continue

            trends.append(self._create_trend_dict(
                trend_type, current.date, next_swing.date, data_slice))

        return trends

    def _detect_rolling_window_moves(self) -> List[Dict[str, Any]]:
        """Detect moves using rolling windows."""
        trends = []
        window_size = self.config.rolling_window_size

        for i in range(len(self.data) - window_size + 1):
            window_data = self.data.iloc[i:i + window_size]

            high_idx = window_data['High'].idxmax()
            low_idx = window_data['Low'].idxmin()
            magnitude = window_data['High'].max() - window_data['Low'].min()

            if magnitude < self.config.rolling_min_magnitude:
                continue

            # Determine trend direction
            high_pos = window_data.index.get_loc(high_idx)
            low_pos = window_data.index.get_loc(low_idx)

            if high_pos < low_pos:
                trend_type = "Downtrend (Rolling)"
                start_date, end_date = high_idx.date(), low_idx.date()
            else:
                trend_type = "Uptrend (Rolling)"
                start_date, end_date = low_idx.date(), high_idx.date()

            # Check for duplicates
            is_duplicate = any(
                existing["Start Date"] == start_date and
                existing["End Date"] == end_date and
                abs(existing["Magnitude"] - magnitude) < 1.0
                for existing in trends
            )

            if not is_duplicate:
                trends.append(self._create_trend_dict(
                    trend_type, start_date, end_date, window_data))

        return trends

    def _create_trend_dict(self, trend_type: str, start_date: date, end_date: date, data_slice: pd.DataFrame) -> Dict[str, Any]:
        """Create standardized trend dictionary."""
        low_price = float(data_slice['Low'].min())
        high_price = float(data_slice['High'].max())
        # Calculate magnitude as price difference
        magnitude_price = high_price - low_price

        return {
            "Trend Type": trend_type,
            "Start Date": start_date,
            "End Date": end_date,
            "Absolute Low": low_price,
            "Absolute High": high_price,
            "Magnitude": magnitude_price  # Now as price difference
        }

    def _remove_overlapping_trends(self, trends: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove overlapping trends, keeping the largest magnitude."""
        if not trends:
            return trends

        # Sort by magnitude (largest first)
        sorted_trends = sorted(trends, key=lambda x: x['Magnitude'], reverse=True)
        unique_trends = []

        for trend in sorted_trends:
            if not any(self._trends_overlap(trend, existing) for existing in unique_trends):
                unique_trends.append(trend)

        return unique_trends

    def _trends_overlap(self, trend1: Dict[str, Any], trend2: Dict[str, Any]) -> bool:
        """Check if two trends overlap significantly."""
        # Date overlap check
        start1, end1 = str(trend1["Start Date"]), str(trend1["End Date"])
        start2, end2 = str(trend2["Start Date"]), str(trend2["End Date"])

        if end1 < start2 or end2 < start1:
            return False

        # Price range overlap check
        high1, low1 = trend1["Absolute High"], trend1["Absolute Low"]
        high2, low2 = trend2["Absolute High"], trend2["Absolute Low"]

        overlap_high = min(high1, high2)
        overlap_low = max(low1, low2)

        if overlap_high <= overlap_low:
            return False

        # Calculate overlap ratios
        overlap_range = overlap_high - overlap_low
        range1, range2 = high1 - low1, high2 - low2

        if range1 == 0 or range2 == 0:
            return False

        overlap_ratio1 = overlap_range / range1
        overlap_ratio2 = overlap_range / range2

        return overlap_ratio1 > 0.7 or overlap_ratio2 > 0.7

    def _create_market_structure(self, primary_trend: Dict[str, Any]) -> MarketStructure:
        """Create market structure from primary trend."""
        trend_direction = "uptrend" if "Uptrend" in primary_trend["Trend Type"] else "downtrend"

        # Assess structure quality based on magnitude and timeframe
        magnitude = primary_trend["Magnitude"]
        current_price = float(self.data['Close'].iloc[-1])
        magnitude_pct = (magnitude / current_price) * 100

        if magnitude_pct > 20:
            structure_quality = "high"
        elif magnitude_pct > 10:
            structure_quality = "medium"
        else:
            structure_quality = "low"

        # Determine current market phase
        high_price = primary_trend["Absolute High"]
        low_price = primary_trend["Absolute Low"]
        price_range = high_price - low_price
        position_in_range = (current_price - low_price) / price_range if price_range > 0 else 0.5

        if position_in_range > 0.8:
            phase = "Near swing high - potential resistance"
        elif position_in_range < 0.2:
            phase = "Near swing low - potential support"
        elif 0.35 <= position_in_range <= 0.65:
            phase = "Middle range - watch for direction"
        else:
            phase = "In retracement zone"

        return MarketStructure(
            trend_direction=trend_direction,
            swing_high=PricePoint(
                price=high_price,
                date=str(primary_trend["End Date"] if "Uptrend" in primary_trend["Trend Type"] else primary_trend["Start Date"])
            ),
            swing_low=PricePoint(
                price=low_price,
                date=str(primary_trend["Start Date"] if "Uptrend" in primary_trend["Trend Type"] else primary_trend["End Date"])
            ),
            structure_quality=structure_quality,
            phase=phase
        )

    def _calculate_fibonacci_levels_advanced(self, primary_trend: Dict[str, Any]) -> List[FibonacciLevel]:
        """Calculate Fibonacci levels for the primary trend."""
        try:
            high_price = primary_trend["Absolute High"]
            low_price = primary_trend["Absolute Low"]
            price_range = high_price - low_price
            is_uptrend = "Uptrend" in primary_trend["Trend Type"]

            fibonacci_levels = []

            for level in self.FIBONACCI_LEVELS:
                if is_uptrend:
                    # For uptrends, retracements are levels below the high
                    fib_price = high_price - (price_range * level)
                else:
                    # For downtrends, retracements are levels above the low
                    fib_price = low_price + (price_range * level)

                fibonacci_levels.append(FibonacciLevel(
                    level=level,
                    price=fib_price,
                    percentage=f"{level * 100:.1f}%",
                    is_key_level=level in self.KEY_LEVELS
                ))

            logger.info("Calculated Fibonacci levels",
                       trend_type=primary_trend["Trend Type"],
                       levels_count=len(fibonacci_levels),
                       key_levels_count=len([l for l in fibonacci_levels if l.is_key_level]))
            return fibonacci_levels
        except Exception as e:
            logger.error("Failed to calculate Fibonacci levels",
                        trend=primary_trend, error=str(e))
            return []

    def _get_fibonacci_levels_for_trend(self, trend: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get Fibonacci levels for a trend with detailed error handling."""
        try:
            logger.info(f"Calculating Fibonacci levels for trend: {trend.get('Trend Type', 'Unknown')}")

            # Log the trend data structure
            logger.info(f"Trend fields: {list(trend.keys())}")
            logger.info(f"High: {trend.get('Absolute High')}, Low: {trend.get('Absolute Low')}")

            fib_levels = self._calculate_fibonacci_levels_advanced(trend)

            result = [
                {
                    "level": level.level,
                    "price": level.price,
                    "percentage": level.percentage,
                    "is_key_level": level.is_key_level
                }
                for level in fib_levels
            ]

            logger.info(f"Successfully calculated {len(result)} Fibonacci levels")
            return result

        except Exception as e:
            logger.error(f"Error in _get_fibonacci_levels_for_trend: {str(e)}")
            logger.error(f"Trend data: {trend}")
            return []

    def _calculate_golden_pressure_zone(self, trend: Dict[str, Any]) -> Dict[str, float]:
        """Calculate the golden ratio pressure zone (61.5% - 61.8%)."""
        high_price = trend["Absolute High"]
        low_price = trend["Absolute Low"]
        price_range = high_price - low_price
        is_uptrend = "Uptrend" in trend["Trend Type"]

        if is_uptrend:
            # For uptrends, golden zone is below the high
            upper_level = high_price - (price_range * self.GOLDEN_ZONE_START)  # 61.5%
            lower_level = high_price - (price_range * self.GOLDEN_ZONE_END)    # 61.8%
        else:
            # For downtrends, golden zone is above the low
            lower_level = low_price + (price_range * self.GOLDEN_ZONE_START)   # 61.5%
            upper_level = low_price + (price_range * self.GOLDEN_ZONE_END)     # 61.8%

        return {
            "center_price": (upper_level + lower_level) / 2,
            "upper_bound": max(upper_level, lower_level),
            "lower_bound": min(upper_level, lower_level),
            "zone_width": abs(upper_level - lower_level)
        }

    def _calculate_confidence_score_advanced(self, top_trends: List[Dict[str, Any]], current_price: float) -> float:
        """Calculate confidence score based on trend analysis."""
        if not top_trends:
            return 0.0

        primary_trend = top_trends[0]
        score = 0.5  # Base score

        # Trend magnitude significance
        magnitude_pct = (primary_trend["Magnitude"] / current_price) * 100
        if magnitude_pct > 20:
            score += 0.3
        elif magnitude_pct > 10:
            score += 0.2
        elif magnitude_pct > 5:
            score += 0.1

        # Multiple confirming trends
        if len(top_trends) >= 3:
            score += 0.1

        # Data sufficiency
        if len(self.data) > 50:
            score += 0.1

        return min(score, 1.0)

    def _assess_trend_strength_advanced(self, top_trends: List[Dict[str, Any]]) -> str:
        """Assess overall trend strength."""
        if not top_trends:
            return "Weak"

        primary_magnitude = top_trends[0]["Magnitude"]
        current_price = float(self.data['Close'].iloc[-1])
        magnitude_pct = (primary_magnitude / current_price) * 100

        if magnitude_pct > 25:
            return "Very Strong"
        elif magnitude_pct > 15:
            return "Strong"
        elif magnitude_pct > 8:
            return "Moderate"
        else:
            return "Weak"

    def _generate_pressure_insights(self, top_trends: List[Dict[str, Any]],
                                  fibonacci_levels: List[FibonacciLevel],
                                  current_price: float) -> Tuple[str, List[str]]:
        """Generate enhanced insights with pressure level analysis."""
        if not top_trends:
            return "No significant trends detected.", []

        primary_trend = top_trends[0]
        trend_type = primary_trend["Trend Type"]
        magnitude = primary_trend["Magnitude"]

        # Find current position relative to Fibonacci levels
        current_position = self._find_current_fib_position(fibonacci_levels, current_price)

        # Generate summary
        summary = (
            f"{self.symbol} shows a significant {trend_type.lower()} with ${magnitude:.2f} magnitude "
            f"on {self.timeframe} timeframe. Current price is {current_position}. "
            f"Golden ratio pressure zone (61.5%-61.8%) provides key support/resistance levels."
        )

        # Generate key insights
        key_insights = [
            f"🔹 Primary Trend: {trend_type} (${magnitude:.2f} magnitude)",
            f"🔹 Period: {primary_trend['Start Date']} to {primary_trend['End Date']}",
            f"🔹 Price Range: ${primary_trend['Absolute Low']:.2f} - ${primary_trend['Absolute High']:.2f}",
            f"🔹 Current Position: {current_position}",
            f"🔹 Timeframe: {self.timeframe} analysis with adaptive parameters"
        ]

        # Add golden ratio insight
        golden_ratio_level = next((level for level in fibonacci_levels if abs(level.level - self.GOLDEN_RATIO) < 0.001), None)
        if golden_ratio_level:
            distance_to_golden = abs(current_price - golden_ratio_level.price) / current_price * 100
            if distance_to_golden < 3:  # Within 3% of golden ratio
                key_insights.append(f"⚡ Near Golden Ratio (61.8%) at ${golden_ratio_level.price:.2f} - critical pressure zone!")

        # Add multiple trend confirmation
        if len(top_trends) >= 2:
            second_trend = top_trends[1]
            key_insights.append(f"🔹 Secondary Trend: {second_trend['Trend Type']} (${second_trend['Magnitude']:.2f})")

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