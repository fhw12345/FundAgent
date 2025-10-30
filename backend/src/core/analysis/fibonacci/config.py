"""
Fibonacci analysis configuration and constants.
Contains timeframe-specific parameters and standard Fibonacci ratios used across the analysis engine.
"""

from dataclasses import dataclass


@dataclass
class TimeframeConfig:
    """Configuration parameters for different timeframes."""

    interval: str
    swing_lookback: int
    prominence: float
    min_magnitude_pct: float  # Percentage of median price (e.g., 0.05 = 5%)
    tolerance_pct: float  # Pullback tolerance percentage (e.g., 0.01 = 1%)


class FibonacciConstants:
    """Standard Fibonacci levels and ratios used in technical analysis."""

    # Standard Fibonacci retracement levels
    FIBONACCI_LEVELS: list[float] = [0.0, 0.236, 0.382, 0.5, 0.615, 0.618, 0.786, 1.0]

    # Most important levels for trading decisions
    KEY_LEVELS: list[float] = [0.382, 0.5, 0.618]

    # Golden ratio and pressure zone boundaries
    GOLDEN_RATIO: float = 0.618
    GOLDEN_ZONE_START: float = 0.615
    GOLDEN_ZONE_END: float = 0.618


class TimeframeConfigs:
    """Timeframe-specific configuration parameters for trend detection."""

    # Configurations adapted for different market scales and volatility
    CONFIGS: dict[str, TimeframeConfig] = {
        "1h": TimeframeConfig("1h", 5, 0.3, 0.03, 0.005),  # Hourly: 3% min magnitude, 0.5% tolerance
        "1d": TimeframeConfig("1d", 3, 0.5, 0.05, 0.007),  # Daily: 5% min magnitude, 0.7% tolerance
        "1w": TimeframeConfig("1wk", 2, 1.0, 0.08, 0.02),  # Weekly: 8% min magnitude, 2% tolerance
        "1M": TimeframeConfig("1mo", 1, 1.5, 0.10, 0.03),  # Monthly: 10% min magnitude, 3% tolerance
    }

    @classmethod
    def get_config(cls, timeframe: str) -> TimeframeConfig:
        """Get configuration for specified timeframe, defaulting to daily."""
        return cls.CONFIGS.get(timeframe, cls.CONFIGS["1d"])
