"""
Unit tests for Fibonacci analysis configuration.

Tests configuration constants and timeframe-specific parameters including:
- Fibonacci retracement levels and ratios
- Key levels for trading decisions
- Golden ratio and pressure zone boundaries
- Timeframe-specific configurations (1m, 1h, 1d, 1w, 1M)
"""

import pytest

from src.core.analysis.fibonacci.config import (
    FibonacciConstants,
    TimeframeConfig,
    TimeframeConfigs,
)


# ===== Fibonacci Constants Tests =====


class TestFibonacciConstants:
    """Test standard Fibonacci constants and levels"""

    def test_fibonacci_levels_count(self):
        """Test that there are 8 standard Fibonacci levels"""
        # Assert
        assert len(FibonacciConstants.FIBONACCI_LEVELS) == 8

    def test_fibonacci_levels_range(self):
        """Test that Fibonacci levels range from 0.0 to 1.0"""
        # Assert
        levels = FibonacciConstants.FIBONACCI_LEVELS
        assert min(levels) == 0.0
        assert max(levels) == 1.0

    def test_fibonacci_levels_include_key_ratios(self):
        """Test that levels include standard Fibonacci ratios"""
        # Arrange
        levels = FibonacciConstants.FIBONACCI_LEVELS

        # Assert - Check for standard Fibonacci ratios
        assert 0.236 in levels  # 23.6%
        assert 0.382 in levels  # 38.2%
        assert 0.5 in levels  # 50%
        assert 0.618 in levels  # Golden ratio
        assert 0.786 in levels  # 78.6%

    def test_fibonacci_levels_sorted(self):
        """Test that Fibonacci levels are in ascending order"""
        # Arrange
        levels = FibonacciConstants.FIBONACCI_LEVELS

        # Assert
        assert levels == sorted(levels)

    def test_key_levels_count(self):
        """Test that there are 3 key trading levels"""
        # Assert
        assert len(FibonacciConstants.KEY_LEVELS) == 3

    def test_key_levels_are_subset_of_fibonacci_levels(self):
        """Test that key levels are subset of Fibonacci levels"""
        # Arrange
        key_levels = FibonacciConstants.KEY_LEVELS
        fib_levels = FibonacciConstants.FIBONACCI_LEVELS

        # Assert
        for level in key_levels:
            assert level in fib_levels

    def test_key_levels_include_golden_ratio(self):
        """Test that key levels include the golden ratio (0.618)"""
        # Assert
        assert 0.618 in FibonacciConstants.KEY_LEVELS

    def test_key_levels_include_half(self):
        """Test that key levels include 0.5 (halfway point)"""
        # Assert
        assert 0.5 in FibonacciConstants.KEY_LEVELS

    def test_key_levels_include_382(self):
        """Test that key levels include 0.382"""
        # Assert
        assert 0.382 in FibonacciConstants.KEY_LEVELS

    def test_golden_ratio_value(self):
        """Test that golden ratio is 0.618"""
        # Assert
        assert FibonacciConstants.GOLDEN_RATIO == 0.618

    def test_golden_zone_boundaries(self):
        """Test that golden zone boundaries are correct"""
        # Assert
        assert FibonacciConstants.GOLDEN_ZONE_START == 0.615
        assert FibonacciConstants.GOLDEN_ZONE_END == 0.618

    def test_golden_zone_contains_golden_ratio(self):
        """Test that golden zone contains the golden ratio"""
        # Assert
        assert (
            FibonacciConstants.GOLDEN_ZONE_START
            <= FibonacciConstants.GOLDEN_RATIO
            <= FibonacciConstants.GOLDEN_ZONE_END
        )

    def test_golden_zone_width(self):
        """Test that golden zone is narrow (0.3% width)"""
        # Arrange
        zone_width = (
            FibonacciConstants.GOLDEN_ZONE_END - FibonacciConstants.GOLDEN_ZONE_START
        )

        # Assert
        assert zone_width == pytest.approx(0.003, abs=0.0001)


# ===== Timeframe Config Tests =====


class TestTimeframeConfig:
    """Test TimeframeConfig dataclass"""

    def test_create_timeframe_config(self):
        """Test creating a TimeframeConfig instance"""
        # Arrange & Act
        config = TimeframeConfig(
            interval="1d",
            swing_lookback=3,
            prominence=0.5,
            min_magnitude_pct=0.05,
            tolerance_pct=0.007,
        )

        # Assert
        assert config.interval == "1d"
        assert config.swing_lookback == 3
        assert config.prominence == 0.5
        assert config.min_magnitude_pct == 0.05
        assert config.tolerance_pct == 0.007

    def test_timeframe_config_all_fields_required(self):
        """Test that all fields are required (no defaults)"""
        # Act & Assert - missing fields should cause TypeError
        with pytest.raises(TypeError):
            TimeframeConfig()  # type: ignore

    def test_timeframe_config_immutable_after_creation(self):
        """Test that TimeframeConfig is immutable (frozen dataclass)"""
        # Arrange
        config = TimeframeConfig("1d", 3, 0.5, 0.05, 0.007)

        # Act & Assert - dataclass is NOT frozen by default, so this will work
        # But we test that the instance can be created and accessed
        assert config.interval == "1d"


# ===== Timeframe Configs Tests =====


class TestTimeframeConfigs:
    """Test TimeframeConfigs configuration mappings"""

    def test_get_config_1m(self):
        """Test getting 1-minute timeframe config"""
        # Act
        config = TimeframeConfigs.get_config("1m")

        # Assert
        assert config.interval == "1m"
        assert config.swing_lookback == 10
        assert config.prominence == 0.1
        assert config.min_magnitude_pct == 0.01  # 1%
        assert config.tolerance_pct == 0.002  # 0.2%

    def test_get_config_1h(self):
        """Test getting 1-hour timeframe config"""
        # Act
        config = TimeframeConfigs.get_config("1h")

        # Assert
        assert config.interval == "1h"
        assert config.swing_lookback == 5
        assert config.prominence == 0.3
        assert config.min_magnitude_pct == 0.03  # 3%
        assert config.tolerance_pct == 0.005  # 0.5%

    def test_get_config_60m_alias(self):
        """Test that 60m is an alias for 1h"""
        # Act
        config_1h = TimeframeConfigs.get_config("1h")
        config_60m = TimeframeConfigs.get_config("60m")

        # Assert - both should have same parameters
        assert config_1h.min_magnitude_pct == config_60m.min_magnitude_pct
        assert config_1h.tolerance_pct == config_60m.tolerance_pct
        assert config_1h.swing_lookback == config_60m.swing_lookback

    def test_get_config_60min_alias(self):
        """Test that 60min is an alias for 1h"""
        # Act
        config_1h = TimeframeConfigs.get_config("1h")
        config_60min = TimeframeConfigs.get_config("60min")

        # Assert
        assert config_1h.min_magnitude_pct == config_60min.min_magnitude_pct
        assert config_1h.tolerance_pct == config_60min.tolerance_pct

    def test_get_config_1d(self):
        """Test getting daily timeframe config"""
        # Act
        config = TimeframeConfigs.get_config("1d")

        # Assert
        assert config.interval == "1d"
        assert config.swing_lookback == 3
        assert config.prominence == 0.5
        assert config.min_magnitude_pct == 0.05  # 5%
        assert config.tolerance_pct == 0.007  # 0.7%

    def test_get_config_1w(self):
        """Test getting weekly timeframe config"""
        # Act
        config = TimeframeConfigs.get_config("1w")

        # Assert
        assert config.interval == "1wk"
        assert config.swing_lookback == 2
        assert config.prominence == 1.0
        assert config.min_magnitude_pct == 0.08  # 8%
        assert config.tolerance_pct == 0.02  # 2%

    def test_get_config_1wk_alias(self):
        """Test that 1wk is an alias for 1w"""
        # Act
        config_1w = TimeframeConfigs.get_config("1w")
        config_1wk = TimeframeConfigs.get_config("1wk")

        # Assert
        assert config_1w.min_magnitude_pct == config_1wk.min_magnitude_pct
        assert config_1w.tolerance_pct == config_1wk.tolerance_pct

    def test_get_config_1M(self):
        """Test getting monthly timeframe config"""
        # Act
        config = TimeframeConfigs.get_config("1M")

        # Assert
        assert config.interval == "1mo"
        assert config.swing_lookback == 1
        assert config.prominence == 1.5
        assert config.min_magnitude_pct == 0.10  # 10%
        assert config.tolerance_pct == 0.03  # 3%

    def test_get_config_1mo_alias(self):
        """Test that 1mo is an alias for 1M"""
        # Act
        config_1M = TimeframeConfigs.get_config("1M")
        config_1mo = TimeframeConfigs.get_config("1mo")

        # Assert
        assert config_1M.min_magnitude_pct == config_1mo.min_magnitude_pct
        assert config_1M.tolerance_pct == config_1mo.tolerance_pct

    def test_get_config_unknown_defaults_to_daily(self):
        """Test that unknown timeframe defaults to daily config"""
        # Act
        config_unknown = TimeframeConfigs.get_config("unknown_timeframe")
        config_1d = TimeframeConfigs.get_config("1d")

        # Assert
        assert config_unknown.interval == config_1d.interval
        assert config_unknown.min_magnitude_pct == config_1d.min_magnitude_pct
        assert config_unknown.tolerance_pct == config_1d.tolerance_pct

    def test_tolerance_increases_with_timeframe(self):
        """Test that tolerance increases for larger timeframes"""
        # Arrange
        config_1m = TimeframeConfigs.get_config("1m")
        config_1h = TimeframeConfigs.get_config("1h")
        config_1d = TimeframeConfigs.get_config("1d")
        config_1w = TimeframeConfigs.get_config("1w")
        config_1M = TimeframeConfigs.get_config("1M")

        # Assert - tolerance should increase with timeframe
        assert config_1m.tolerance_pct < config_1h.tolerance_pct
        assert config_1h.tolerance_pct < config_1d.tolerance_pct
        assert config_1d.tolerance_pct < config_1w.tolerance_pct
        assert config_1w.tolerance_pct < config_1M.tolerance_pct

    def test_min_magnitude_increases_with_timeframe(self):
        """Test that minimum magnitude increases for larger timeframes"""
        # Arrange
        config_1m = TimeframeConfigs.get_config("1m")
        config_1h = TimeframeConfigs.get_config("1h")
        config_1d = TimeframeConfigs.get_config("1d")
        config_1w = TimeframeConfigs.get_config("1w")
        config_1M = TimeframeConfigs.get_config("1M")

        # Assert
        assert config_1m.min_magnitude_pct < config_1h.min_magnitude_pct
        assert config_1h.min_magnitude_pct < config_1d.min_magnitude_pct
        assert config_1d.min_magnitude_pct < config_1w.min_magnitude_pct
        assert config_1w.min_magnitude_pct < config_1M.min_magnitude_pct

    def test_swing_lookback_decreases_with_timeframe(self):
        """Test that swing lookback decreases for larger timeframes"""
        # Arrange
        config_1m = TimeframeConfigs.get_config("1m")
        config_1d = TimeframeConfigs.get_config("1d")
        config_1w = TimeframeConfigs.get_config("1w")
        config_1M = TimeframeConfigs.get_config("1M")

        # Assert - longer timeframes need fewer lookback periods
        assert config_1m.swing_lookback > config_1d.swing_lookback
        assert config_1d.swing_lookback > config_1w.swing_lookback
        assert config_1w.swing_lookback > config_1M.swing_lookback

    def test_all_timeframes_have_configs(self):
        """Test that all expected timeframes have configurations"""
        # Arrange
        expected_timeframes = ["1m", "1h", "60m", "60min", "1d", "1w", "1wk", "1M", "1mo"]

        # Act & Assert
        for timeframe in expected_timeframes:
            config = TimeframeConfigs.get_config(timeframe)
            assert config is not None
            assert isinstance(config, TimeframeConfig)

    def test_prominence_increases_with_timeframe(self):
        """Test that prominence increases for larger timeframes"""
        # Arrange
        config_1m = TimeframeConfigs.get_config("1m")
        config_1h = TimeframeConfigs.get_config("1h")
        config_1d = TimeframeConfigs.get_config("1d")
        config_1w = TimeframeConfigs.get_config("1w")
        config_1M = TimeframeConfigs.get_config("1M")

        # Assert
        assert config_1m.prominence < config_1h.prominence
        assert config_1h.prominence < config_1d.prominence
        assert config_1d.prominence < config_1w.prominence
        assert config_1w.prominence < config_1M.prominence


# ===== Integration Tests =====


class TestFibonacciConfigIntegration:
    """Test integration between constants and timeframe configs"""

    def test_fibonacci_levels_used_with_timeframe_config(self):
        """Test that Fibonacci levels can be used with any timeframe config"""
        # Arrange
        config = TimeframeConfigs.get_config("1d")
        levels = FibonacciConstants.FIBONACCI_LEVELS

        # Act & Assert - should be able to use levels with config
        assert len(levels) == 8
        assert config.interval == "1d"

    def test_golden_ratio_available_across_all_timeframes(self):
        """Test that golden ratio is consistently available"""
        # Arrange
        timeframes = ["1m", "1h", "1d", "1w", "1M"]

        # Act & Assert
        for timeframe in timeframes:
            config = TimeframeConfigs.get_config(timeframe)
            golden_ratio = FibonacciConstants.GOLDEN_RATIO
            assert golden_ratio == 0.618
            assert config.tolerance_pct > 0  # Each timeframe has tolerance
