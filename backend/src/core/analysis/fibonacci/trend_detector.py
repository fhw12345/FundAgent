"""
Trend detection logic for Fibonacci analysis.
Identifies swing-based trends, single-leg moves, and rolling window patterns in price data.
"""

import pandas as pd
from datetime import date
from typing import Dict, List, Optional, Tuple, Any
from scipy.signal import find_peaks
import structlog

from .config import SwingPoint, TimeframeConfig

logger = structlog.get_logger()


class TrendDetector:
    """Detects various types of trends in price data using multiple detection methods."""

    def __init__(self, config: TimeframeConfig):
        """Initialize with timeframe-specific configuration."""
        self.config = config

    def find_swing_points(self, data: pd.DataFrame) -> List[SwingPoint]:
        """Find swing points using timeframe-adaptive parameters."""
        if data is None or data.empty:
            return []

        # Find peaks and troughs using scipy with adaptive parameters
        high_peaks, _ = find_peaks(
            data['High'],
            distance=self.config.swing_lookback,
            prominence=self.config.prominence
        )
        low_peaks, _ = find_peaks(
            -data['Low'],
            distance=self.config.swing_lookback,
            prominence=self.config.prominence
        )

        swing_points = []

        # Add high points
        for i in high_peaks:
            swing_points.append(SwingPoint(
                index=i,
                type='high',
                price=data['High'].iloc[i],
                date=data.index[i].date()
            ))

        # Add low points
        for i in low_peaks:
            swing_points.append(SwingPoint(
                index=i,
                type='low',
                price=data['Low'].iloc[i],
                date=data.index[i].date()
            ))

        # Sort by index
        swing_points.sort(key=lambda x: x.index)

        logger.info("Found swing points",
                   high_count=len(high_peaks),
                   low_count=len(low_peaks),
                   total=len(swing_points))

        return swing_points

    def detect_top_trends(self, data: pd.DataFrame, swing_points: List[SwingPoint]) -> List[Dict[str, Any]]:
        """Detect and rank the top trending moves using multiple detection methods."""
        all_trends = []

        # 1. Traditional swing-based trends
        swing_trends = self._detect_swing_based_trends(data, swing_points)
        all_trends.extend(swing_trends)

        # 2. Single-leg moves between swing points
        single_leg_trends = self._detect_single_leg_moves(data, swing_points)
        all_trends.extend(single_leg_trends)

        # 3. Rolling window significant moves
        rolling_trends = self._detect_rolling_window_moves(data)
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

    def _detect_swing_based_trends(self, data: pd.DataFrame, swing_points: List[SwingPoint]) -> List[Dict[str, Any]]:
        """Detect trends based on higher highs/higher lows patterns."""
        trends = []
        i = 0

        while i < len(swing_points) - 2:
            p1, p2, p3 = swing_points[i], swing_points[i + 1], swing_points[i + 2]

            # Uptrend: Low -> High -> Higher Low
            if (p1.type == 'low' and p2.type == 'high' and p3.type == 'low' and
                p3.price > p1.price):

                trend_end, next_i = self._find_trend_continuation(swing_points, i, is_uptrend=True)
                data_slice = data.iloc[p1.index:trend_end.index + 1]

                trends.append(self._create_trend_dict(
                    data_slice, "Uptrend", p1.date, trend_end.date))
                i = next_i
                continue

            # Downtrend: High -> Low -> Lower High
            elif (p1.type == 'high' and p2.type == 'low' and p3.type == 'high' and
                  p3.price < p1.price):

                trend_end, next_i = self._find_trend_continuation(swing_points, i, is_uptrend=False)
                data_slice = data.iloc[p1.index:trend_end.index + 1]

                trends.append(self._create_trend_dict(
                    data_slice, "Downtrend", p1.date, trend_end.date))
                i = next_i
                continue

            i += 1

        return trends

    def _find_trend_continuation(self, swing_points: List[SwingPoint], start_idx: int, is_uptrend: bool) -> Tuple[SwingPoint, int]:
        """Find where a trend pattern ends by looking for continuation patterns."""
        current_high = swing_points[start_idx + 1] if is_uptrend else swing_points[start_idx]
        current_low = swing_points[start_idx + 2] if is_uptrend else swing_points[start_idx + 1]

        j = start_idx + 3
        while j < len(swing_points) - 1:
            next_point1 = swing_points[j]
            next_point2 = swing_points[j + 1]

            if is_uptrend:
                # Look for higher highs and higher lows
                if (next_point1.type == 'high' and next_point2.type == 'low' and
                    next_point1.price > current_high.price and next_point2.price > current_low.price):
                    current_high = next_point1
                    current_low = next_point2
                    j += 2
                else:
                    break
            else:
                # Look for lower lows and lower highs
                if (next_point1.type == 'low' and next_point2.type == 'high' and
                    next_point1.price < current_low.price and next_point2.price < current_high.price):
                    current_low = next_point1
                    current_high = next_point2
                    j += 2
                else:
                    break

        trend_end = current_high if is_uptrend else current_low
        return trend_end, j - 1

    def _detect_single_leg_moves(self, data: pd.DataFrame, swing_points: List[SwingPoint]) -> List[Dict[str, Any]]:
        """Detect single-leg moves between consecutive swing points."""
        trends = []

        for i in range(len(swing_points) - 1):
            current = swing_points[i]
            next_swing = swing_points[i + 1]

            magnitude = abs(current.price - next_swing.price)
            if magnitude < self.config.single_leg_min_magnitude:
                continue

            data_slice = data.iloc[current.index:next_swing.index + 1]

            if current.type == 'high' and next_swing.type == 'low':
                trend_type = "Downtrend (Single-leg)"
            elif current.type == 'low' and next_swing.type == 'high':
                trend_type = "Uptrend (Single-leg)"
            else:
                continue

            trends.append(self._create_trend_dict(
                data_slice, trend_type, current.date, next_swing.date))

        return trends

    def _detect_rolling_window_moves(self, data: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detect significant moves using rolling windows."""
        trends = []
        window_size = self.config.rolling_window_size

        for i in range(len(data) - window_size + 1):
            window_data = data.iloc[i:i + window_size]

            high_idx = window_data['High'].idxmax()
            low_idx = window_data['Low'].idxmin()
            magnitude = window_data['High'].max() - window_data['Low'].min()

            if magnitude < self.config.rolling_min_magnitude:
                continue

            # Determine trend direction based on timing of high and low
            high_pos = window_data.index.get_loc(high_idx)
            low_pos = window_data.index.get_loc(low_idx)

            if high_pos < low_pos:
                trend_type = "Downtrend (Rolling)"
                start_date, end_date = high_idx.date(), low_idx.date()
            else:
                trend_type = "Uptrend (Rolling)"
                start_date, end_date = low_idx.date(), high_idx.date()

            trends.append(self._create_trend_dict(
                window_data, trend_type, start_date, end_date))

        return trends

    def _create_trend_dict(self, data_slice: pd.DataFrame, trend_type: str, start_date: date, end_date: date) -> Dict[str, Any]:
        """Create standardized trend dictionary from data slice."""
        abs_high = float(data_slice['High'].max())
        abs_low = float(data_slice['Low'].min())
        magnitude = abs_high - abs_low

        return {
            "Trend Type": trend_type,
            "Start Date": start_date,
            "End Date": end_date,
            "Absolute High": abs_high,
            "Absolute Low": abs_low,
            "Magnitude": magnitude
        }

    def _remove_overlapping_trends(self, trends: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove overlapping trends, keeping the one with larger magnitude."""
        if not trends:
            return []

        # Sort by magnitude (descending) to prioritize larger trends
        trends_sorted = sorted(trends, key=lambda x: x['Magnitude'], reverse=True)
        unique_trends = []

        for current_trend in trends_sorted:
            is_overlapping = False

            for existing_trend in unique_trends:
                # Check for date overlap
                if (self._dates_overlap(current_trend['Start Date'], current_trend['End Date'],
                                      existing_trend['Start Date'], existing_trend['End Date'])):
                    is_overlapping = True
                    break

            if not is_overlapping:
                unique_trends.append(current_trend)

        return unique_trends

    def _dates_overlap(self, start1: date, end1: date, start2: date, end2: date) -> bool:
        """Check if two date ranges overlap."""
        return not (end1 < start2 or end2 < start1)