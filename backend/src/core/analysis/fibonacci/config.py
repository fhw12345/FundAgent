"""
Fibonacci analysis configuration and constants.
Contains timeframe-specific parameters and standard Fibonacci ratios used across the analysis engine.
"""

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class SwingPoint:
    """Represents a swing high or low point in price data."""
    index: int
    type: str  # 'high' or 'low'
    price: float
    date: object  # date object


@dataclass
class TimeframeConfig:
    """Configuration parameters for different timeframes."""
    interval: str
    swing_lookback: int
    prominence: float
    single_leg_min_magnitude: float
    rolling_window_size: int
    rolling_min_magnitude: float


class FibonacciConstants:
    """Standard Fibonacci levels and ratios used in technical analysis."""

    # Standard Fibonacci retracement levels
    FIBONACCI_LEVELS: List[float] = [0.0, 0.236, 0.382, 0.5, 0.615, 0.618, 0.786, 1.0]

    # Most important levels for trading decisions
    KEY_LEVELS: List[float] = [0.382, 0.5, 0.618]

    # Golden ratio and pressure zone boundaries
    GOLDEN_RATIO: float = 0.618
    GOLDEN_ZONE_START: float = 0.615
    GOLDEN_ZONE_END: float = 0.618


class TimeframeConfigs:
    """Timeframe-specific configuration parameters for trend detection."""

    # Configurations adapted for different market scales and volatility
    CONFIGS: Dict[str, TimeframeConfig] = {
        '1d': TimeframeConfig('1d', 3, 0.5, 15, 10, 25),      # Daily: sensitive to short-term moves
        '1w': TimeframeConfig('1wk', 2, 1.0, 20, 10, 30),     # Weekly: very sensitive
        '1M': TimeframeConfig('1mo', 1, 1.5, 15, 4, 25)       # Monthly: very sensitive
    }

    @classmethod
    def get_config(cls, timeframe: str) -> TimeframeConfig:
        """Get configuration for specified timeframe, defaulting to daily."""
        return cls.CONFIGS.get(timeframe, cls.CONFIGS['1d'])