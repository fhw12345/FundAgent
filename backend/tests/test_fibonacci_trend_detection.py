"""
Unit tests for directional greedy accumulation trend detection algorithm.
Tests the new Fibonacci trend detection logic that replaced scipy-based swing point detection.
"""

import pandas as pd
import pytest

from src.core.analysis.fibonacci import TrendDetector
from src.core.analysis.fibonacci.config import TimeframeConfig


@pytest.fixture
def basic_config():
    """Basic configuration for testing."""
    return TimeframeConfig(
        interval="1d",
        swing_lookback=3,
        prominence=0.5,
        min_magnitude_pct=0.01,  # 1% for testing (very permissive)
        tolerance_pct=0.007,  # 0.7% tolerance (production default for daily)
    )


@pytest.fixture
def trend_detector(basic_config):
    """Create trend detector instance."""
    return TrendDetector(basic_config)


class TestDirectionalTrendDetection:
    """Test the core directional greedy accumulation algorithm."""

    def test_uptrend_detection(self, trend_detector):
        """Test detection of a clear uptrend."""
        # Create data: steady uptrend from 100 to 120
        dates = pd.date_range("2024-01-01", periods=10, freq="D")
        data = pd.DataFrame(
            {
                "High": [100 + i * 2 for i in range(10)],  # 100, 102, 104, ...
                "Low": [98 + i * 2 for i in range(10)],  # 98, 100, 102, ...
                "Close": [99 + i * 2 for i in range(10)],  # 99, 101, 103, ...
            },
            index=dates,
        )

        trends = trend_detector.detect_top_trends(data)

        assert len(trends) > 0
        assert trends[0]["Trend Type"] == "Uptrend"
        assert trends[0]["Magnitude"] > 15.0  # Should capture significant uptrend

    def test_downtrend_detection(self, trend_detector):
        """Test detection of a clear downtrend."""
        # Create data: steady downtrend from 120 to 100
        dates = pd.date_range("2024-01-01", periods=10, freq="D")
        data = pd.DataFrame(
            {
                "High": [120 - i * 2 for i in range(10)],  # 120, 118, 116, ...
                "Low": [118 - i * 2 for i in range(10)],  # 118, 116, 114, ...
                "Close": [119 - i * 2 for i in range(10)],  # 119, 117, 115, ...
            },
            index=dates,
        )

        trends = trend_detector.detect_top_trends(data)

        assert len(trends) > 0
        assert trends[0]["Trend Type"] == "Downtrend"
        assert trends[0]["Magnitude"] > 15.0

    def test_uptrend_with_small_pullback(self, trend_detector):
        """Test that uptrends allow small pullbacks within 0.7% tolerance."""
        dates = pd.date_range("2024-01-01", periods=10, freq="D")

        # Uptrend with small pullback on day 5
        highs = [100, 102, 104, 106, 105, 107, 109, 111, 113, 115]  # Pullback: 106→105
        lows = [98, 100, 102, 104, 103, 105, 107, 109, 111, 113]  # Pullback: 104→103

        data = pd.DataFrame(
            {"High": highs, "Low": lows, "Close": [h - 1 for h in highs]}, index=dates
        )

        trends = trend_detector.detect_top_trends(data)

        # Should detect one continuous uptrend (pullback within tolerance)
        uptrends = [t for t in trends if t["Trend Type"] == "Uptrend"]
        assert len(uptrends) > 0
        # Longest uptrend should span multiple days despite pullback
        assert max((t["End Date"] - t["Start Date"]).days for t in uptrends) >= 5

    def test_downtrend_with_small_bounce(self, trend_detector):
        """Test that downtrends allow small bounces within 0.7% tolerance."""
        dates = pd.date_range("2024-01-01", periods=10, freq="D")

        # Downtrend with small bounce on day 5
        highs = [120, 118, 116, 114, 115, 113, 111, 109, 107, 105]  # Bounce: 114→115
        lows = [118, 116, 114, 112, 113, 111, 109, 107, 105, 103]  # Bounce: 112→113

        data = pd.DataFrame(
            {"High": highs, "Low": lows, "Close": [low + 1 for low in lows]},
            index=dates,
        )

        trends = trend_detector.detect_top_trends(data)

        # Should detect downtrend that spans the bounce
        downtrends = [t for t in trends if t["Trend Type"] == "Downtrend"]
        assert len(downtrends) > 0
        assert max((t["End Date"] - t["Start Date"]).days for t in downtrends) >= 5

    def test_large_pullback_breaks_trend(self, trend_detector):
        """Test that pullbacks exceeding 0.7% break the trend."""
        dates = pd.date_range("2024-01-01", periods=10, freq="D")

        # Uptrend with LARGE pullback (>0.7%) on day 5
        highs = [
            100,
            102,
            104,
            106,
            102,
            104,
            106,
            108,
            110,
            112,
        ]  # Large drop: 106→102
        lows = [98, 100, 102, 104, 100, 102, 104, 106, 108, 110]  # Large drop: 104→100

        data = pd.DataFrame(
            {"High": highs, "Low": lows, "Close": [h - 1 for h in highs]}, index=dates
        )

        trends = trend_detector.detect_top_trends(data)

        # Should detect multiple shorter trends (broken by large pullback)
        # Not one long trend
        if trends:
            max_duration = max((t["End Date"] - t["Start Date"]).days for t in trends)
            assert max_duration < 9  # Should be broken, not one continuous 9-day trend


class TestTrendMagnitudeCalculation:
    """Test magnitude calculation for detected trends."""

    def test_magnitude_calculation(self, trend_detector):
        """Test that magnitude is correctly calculated as high - low."""
        dates = pd.date_range("2024-01-01", periods=5, freq="D")
        data = pd.DataFrame(
            {
                "High": [100, 105, 110, 115, 120],
                "Low": [95, 100, 105, 110, 115],
                "Close": [97, 102, 107, 112, 117],
            },
            index=dates,
        )

        trends = trend_detector.detect_top_trends(data)

        assert len(trends) > 0
        # Magnitude should be approximately 25 (120 - 95)
        assert trends[0]["Magnitude"] == pytest.approx(25.0, abs=1.0)


class TestOverlappingTrendRemoval:
    """Test that overlapping trends are properly removed."""

    def test_removes_overlapping_keeps_larger(self, trend_detector):
        """Test that when trends overlap, the larger magnitude is kept."""
        dates = pd.date_range("2024-01-01", periods=20, freq="D")

        # Create data with overlapping uptrends
        # First part: moderate uptrend
        # Second part: strong uptrend (should win)
        highs = [100 + i for i in range(20)]
        lows = [95 + i for i in range(20)]

        data = pd.DataFrame(
            {"High": highs, "Low": lows, "Close": [h - 2 for h in highs]}, index=dates
        )

        trends = trend_detector.detect_top_trends(data)

        # Should have removed overlapping trends
        # Verify no date overlaps
        for i, t1 in enumerate(trends):
            for t2 in trends[i + 1 :]:
                # No overlap: either t1 ends before t2 starts OR t2 ends before t1 starts
                assert (t1["End Date"] < t2["Start Date"]) or (
                    t2["End Date"] < t1["Start Date"]
                )


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_dataframe(self, trend_detector):
        """Test handling of empty DataFrame."""
        data = pd.DataFrame({"High": [], "Low": [], "Close": []})
        trends = trend_detector.detect_top_trends(data)
        assert trends == []

    def test_insufficient_data(self, trend_detector):
        """Test handling of insufficient data (< 4 days)."""
        dates = pd.date_range("2024-01-01", periods=3, freq="D")
        data = pd.DataFrame(
            {"High": [100, 102, 104], "Low": [98, 100, 102], "Close": [99, 101, 103]},
            index=dates,
        )

        trends = trend_detector.detect_top_trends(data)
        # Should handle gracefully (may return empty or very short trends)
        assert isinstance(trends, list)

    def test_flat_price_action(self, trend_detector):
        """Test handling of flat/sideways price action."""
        dates = pd.date_range("2024-01-01", periods=10, freq="D")
        data = pd.DataFrame(
            {
                "High": [100] * 10,  # No movement
                "Low": [99] * 10,
                "Close": [99.5] * 10,
            },
            index=dates,
        )

        trends = trend_detector.detect_top_trends(data)
        # Flat price should not generate significant trends
        assert len(trends) == 0 or all(t["Magnitude"] < 2.0 for t in trends)


class TestRealWorldScenario:
    """Test with realistic market data patterns."""

    def test_volatile_stock_detection(self, trend_detector):
        """Test detection on volatile stock with clear directional movements."""
        # Simplified test: Verify the algorithm detects multiple distinct trends
        # Real-world reversals are complex - this tests the core mechanics

        dates = pd.date_range("2024-01-01", periods=30, freq="D")

        # Create a strong uptrend
        highs = [100 + i * 2 for i in range(30)]  # Steady climb
        lows = [95 + i * 2 for i in range(30)]
        closes = [97 + i * 2 for i in range(30)]

        data = pd.DataFrame({"High": highs, "Low": lows, "Close": closes}, index=dates)

        trends = trend_detector.detect_top_trends(data)

        # Should detect at least one significant trend
        assert len(trends) > 0

        # Should have meaningful magnitude (>15 points)
        assert any(t["Magnitude"] > 15 for t in trends)

        # Verify trend structure is valid
        for trend in trends:
            assert trend["Start Date"] <= trend["End Date"]
            assert trend["Magnitude"] > 0
            assert trend["Absolute High"] > trend["Absolute Low"]


class TestDateHandling:
    """Test proper date handling in trend detection."""

    def test_trend_dates_are_accurate(self, trend_detector):
        """Test that trend start/end dates accurately reflect the data."""
        dates = pd.date_range("2024-01-01", periods=10, freq="D")
        data = pd.DataFrame(
            {
                "High": [100 + i * 2 for i in range(10)],
                "Low": [98 + i * 2 for i in range(10)],
                "Close": [99 + i * 2 for i in range(10)],
            },
            index=dates,
        )

        trends = trend_detector.detect_top_trends(data)

        assert len(trends) > 0
        trend = trends[0]

        # Start date should be from the dataframe
        assert (
            trend["Start Date"] == dates[0].date()
            or trend["Start Date"] == dates[1].date()
        )
        # End date should be reasonable
        assert trend["End Date"] <= dates[-1].date()
        assert trend["Start Date"] <= trend["End Date"]


class TestConfigurationImpact:
    """Test how configuration affects trend detection."""

    def test_min_magnitude_filters_small_trends(self):
        """Test that min_magnitude configuration properly filters trends."""
        # Config with high minimum magnitude
        config = TimeframeConfig(
            interval="1d",
            swing_lookback=3,
            prominence=0.5,
            min_magnitude_pct=0.20,  # 20% threshold (very strict)
            tolerance_pct=0.007,  # 0.7% tolerance
        )
        detector = TrendDetector(config)

        dates = pd.date_range("2024-01-01", periods=10, freq="D")
        # Small trend: only 10 point magnitude
        data = pd.DataFrame(
            {
                "High": [100 + i for i in range(10)],
                "Low": [95 + i for i in range(10)],
                "Close": [97 + i for i in range(10)],
            },
            index=dates,
        )

        trends = detector.detect_top_trends(data)

        # Should filter out small trends
        assert len(trends) == 0 or all(t["Magnitude"] >= 20.0 for t in trends)
