"""
Trend detection logic for Fibonacci analysis.
Uses directional greedy accumulation to detect major trends with pullback tolerance.
"""

from datetime import date
from typing import Any

import pandas as pd
import structlog

from .config import TimeframeConfig

logger = structlog.get_logger()


class TrendDetector:
    """Detects trends using directional greedy accumulation with pullback tolerance."""

    def __init__(self, config: TimeframeConfig):
        """Initialize with timeframe-specific configuration."""
        self.config = config

    def detect_top_trends(self, data: pd.DataFrame) -> list[dict[str, Any]]:
        """
        Detect top trending moves using directional greedy accumulation.

        Algorithm:
        1. Start from every data point
        2. Use first N days (lookback) to determine trend direction
        3. Continue accumulating while price moves in trend direction or pulls back within tolerance
        4. For uptrends: Allow high/low to go up, or pullback ≤ 3%
        5. For downtrends: Allow high/low to go down, or pullback ≤ 3%
        """
        # Calculate dynamic tolerance (3% of median price)
        tolerance_pct = 0.03

        # Calculate minimum magnitude based on percentage of median price
        median_price = data["Close"].median()
        min_magnitude = median_price * self.config.min_magnitude_pct

        # Detect all trend candidates
        all_trends = self._detect_directional_trends(
            data, tolerance_pct, min_magnitude, lookback=3
        )

        # Remove overlapping trends
        unique_trends = self._remove_overlapping_trends(all_trends)

        # Sort by magnitude and return
        unique_trends.sort(key=lambda x: x["Magnitude"], reverse=True)

        logger.info(
            "Detected trends",
            total_detected=len(all_trends),
            unique_trends=len(unique_trends),
            top_3_magnitudes=[t["Magnitude"] for t in unique_trends[:3]],
            tolerance_pct=f"{tolerance_pct * 100:.0f}%",
        )

        return unique_trends

    def _detect_directional_trends(
        self,
        data: pd.DataFrame,
        tolerance_pct: float,
        min_magnitude: float,
        lookback: int,
    ) -> list[dict[str, Any]]:
        """
        Detect trends by determining direction first, then accumulating.

        Key insight: In uptrends, both high AND low going up is EXPECTED.
        In downtrends, both high AND low going down is EXPECTED.
        Only break when pullbacks exceed tolerance.
        """
        trends = []

        for i in range(len(data) - lookback - 1):
            start_date = data.index[i].date()
            start_close = data["Close"].iloc[i]

            # Determine direction using lookback period
            lookback_close = data["Close"].iloc[i + lookback]
            close_change = lookback_close - start_close

            if abs(close_change) < 0.01:  # Too flat, skip
                continue

            is_uptrend = close_change > 0

            # Track extremes during lookback
            lookback_high = data["High"].iloc[i : i + lookback + 1].max()
            lookback_low = data["Low"].iloc[i : i + lookback + 1].min()

            # Continue accumulating from lookback point
            highest_high = lookback_high
            lowest_low = lookback_low
            current_high = data["High"].iloc[i + lookback]
            current_low = data["Low"].iloc[i + lookback]
            end_index = i + lookback

            # Greedy accumulation with directional tolerance
            for j in range(i + lookback + 1, len(data)):
                next_high = data["High"].iloc[j]
                next_low = data["Low"].iloc[j]

                # Calculate thresholds based on current prices
                high_threshold = current_high * tolerance_pct
                low_threshold = current_low * tolerance_pct

                if is_uptrend:
                    # In uptrend: Allow high/low to go up (expected) or small pullback
                    high_change = next_high - current_high
                    low_change = next_low - current_low

                    high_ok = (high_change >= 0) or (abs(high_change) <= high_threshold)
                    low_ok = (low_change >= 0) or (abs(low_change) <= low_threshold)

                    if not (high_ok and low_ok):
                        break  # Pullback too large

                else:  # Downtrend
                    # In downtrend: Allow high/low to go down (expected) or small pullback
                    high_change = next_high - current_high
                    low_change = next_low - current_low

                    low_ok = (low_change <= 0) or (abs(low_change) <= low_threshold)
                    high_ok = (high_change <= 0) or (abs(high_change) <= high_threshold)

                    if not (high_ok and low_ok):
                        break  # Pullback too large

                # Continue - update tracking
                end_index = j
                current_high = next_high
                current_low = next_low

                if next_high > highest_high:
                    highest_high = next_high
                if next_low < lowest_low:
                    lowest_low = next_low

            # Save if meets minimum requirements
            total_magnitude = highest_high - lowest_low
            if end_index - i >= 3 and total_magnitude >= min_magnitude:
                trend_type = "Uptrend" if is_uptrend else "Downtrend"
                trends.append(
                    {
                        "Trend Type": trend_type,
                        "Start Date": start_date,
                        "End Date": data.index[end_index].date(),
                        "Absolute High": float(highest_high),
                        "Absolute Low": float(lowest_low),
                        "Magnitude": float(total_magnitude),
                    }
                )

        return trends

    def _remove_overlapping_trends(
        self, trends: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Remove overlapping trends, keeping the one with larger magnitude."""
        if not trends:
            return []

        # Sort by magnitude (descending) to prioritize larger trends
        trends_sorted = sorted(trends, key=lambda x: x["Magnitude"], reverse=True)
        unique_trends: list[dict[str, Any]] = []

        for current_trend in trends_sorted:
            is_overlapping = False

            for existing_trend in unique_trends:
                # Check for date overlap
                if self._dates_overlap(
                    current_trend["Start Date"],
                    current_trend["End Date"],
                    existing_trend["Start Date"],
                    existing_trend["End Date"],
                ):
                    is_overlapping = True
                    break

            if not is_overlapping:
                unique_trends.append(current_trend)

        return unique_trends

    def _dates_overlap(
        self, start1: date, end1: date, start2: date, end2: date
    ) -> bool:
        """Check if two date ranges overlap."""
        return not (end1 < start2 or end2 < start1)
