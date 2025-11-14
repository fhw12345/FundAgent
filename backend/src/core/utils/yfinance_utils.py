"""
Interval mapping utilities for multi-API support.

Centralizes interval format conversion across:
- Frontend/API (clean format: '1w', '1M')
- yfinance (legacy: '1wk', '1mo')
- Alpha Vantage MCP ('1min', 'daily', 'weekly')
- Alpaca ('1Min', '1Hour', '1Day')

MIGRATION NOTE: Consolidates interval_mapping.py into this file.
"""

try:
    from alpaca.data.timeframe import TimeFrame

    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False

    # Create mock TimeFrame for type hints when Alpaca not installed
    class TimeFrame:
        Minute = "1Min"
        Hour = "1Hour"
        Day = "1Day"
        Week = "1Week"
        Month = "1Month"


def map_timeframe_to_yfinance_interval(frontend_interval: str) -> str:
    """
    Map frontend/API interval to yfinance-compatible interval.

    WHY THIS MAPPING EXISTS:
    - Frontend/API uses clean format: '1w', '1M' for consistency
    - yfinance library requires specific format: '1wk', '1mo'
    - yfinance.history(interval='1w') fails, must be interval='1wk'
    - This centralizes the mapping to avoid duplication across services

    Args:
        frontend_interval: Frontend interval format ('1w', '1M', etc.)

    Returns:
        yfinance-compatible interval ('1wk', '1mo', etc.)
    """
    interval_map: dict[str, str] = {
        # Most intervals work as-is
        "1m": "1m",
        "2m": "2m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "60m": "60m",
        "90m": "90m",
        "1h": "1h",
        "1d": "1d",
        "5d": "5d",
        "3mo": "3mo",
        # These require mapping for yfinance compatibility
        "1w": "1wk",  # Weekly: Frontend '1w' → yfinance '1wk' (required)
        "1M": "1mo",  # Monthly: Frontend '1M' → yfinance '1mo' (required)
        "1mo": "1mo",  # Monthly: Frontend '1mo' → yfinance '1mo' (already compatible)
    }

    return interval_map.get(frontend_interval, frontend_interval)


def get_valid_frontend_intervals() -> list[str]:
    """Get list of valid frontend interval formats."""
    return [
        "1m",
        "2m",
        "5m",
        "15m",
        "30m",
        "60m",
        "90m",
        "1h",
        "1d",
        "5d",
        "1w",
        "1M",
        "1mo",
        "3mo",
    ]


def get_valid_yfinance_intervals() -> list[str]:
    """Get list of valid yfinance interval formats."""
    return [
        "1m",
        "2m",
        "5m",
        "15m",
        "30m",
        "60m",
        "90m",
        "1h",
        "1d",
        "5d",
        "1wk",
        "1mo",
        "3mo",
    ]


# ============================================================
# Multi-API Interval Mapping (Alpha Vantage, Alpaca)
# ============================================================


def map_frontend_to_alphavantage(frontend_interval: str) -> str:
    """
    Map frontend interval to Alpha Vantage MCP format.

    Alpha Vantage uses:
    - Intraday: '1min', '5min', '15min', '30min', '60min'
    - Daily/Weekly/Monthly: 'daily', 'weekly', 'monthly'

    Args:
        frontend_interval: Frontend interval format ('1m', '1h', '1d', '1w', '1M')

    Returns:
        Alpha Vantage-compatible interval

    Examples:
        >>> map_frontend_to_alphavantage('1m')
        '1min'
        >>> map_frontend_to_alphavantage('1d')
        'daily'
    """
    mapping = {
        "1m": "1min",
        "5m": "5min",
        "15m": "15min",
        "30m": "30min",
        "1h": "60min",
        "1d": "daily",
        "1w": "weekly",
        "1M": "monthly",
        "1mo": "monthly",
    }
    return mapping.get(frontend_interval, "daily")


def map_frontend_to_alpaca(frontend_interval: str) -> "TimeFrame":
    """
    Map frontend interval to Alpaca TimeFrame enum.

    Args:
        frontend_interval: Frontend interval format

    Returns:
        Alpaca TimeFrame enum

    Examples:
        >>> map_frontend_to_alpaca('1m')
        TimeFrame.Minute
        >>> map_frontend_to_alpaca('1d')
        TimeFrame.Day
    """
    mapping = {
        "1m": TimeFrame.Minute,
        "5m": TimeFrame.Minute,
        "15m": TimeFrame.Minute,
        "30m": TimeFrame.Minute,
        "1h": TimeFrame.Hour,
        "1d": TimeFrame.Day,
        "1w": TimeFrame.Week,
        "1M": TimeFrame.Month,
        "1mo": TimeFrame.Month,
    }
    return mapping.get(frontend_interval, TimeFrame.Day)


def map_yfinance_to_alphavantage(yfinance_interval: str) -> str:
    """
    Map yfinance interval to Alpha Vantage format.

    For migrating existing code from yfinance to Alpha Vantage.

    Args:
        yfinance_interval: yfinance interval ('1m', '1wk', '1mo')

    Returns:
        Alpha Vantage interval
    """
    mapping = {
        "1m": "1min",
        "5m": "5min",
        "15m": "15min",
        "30m": "30min",
        "60m": "60min",
        "90m": "60min",  # Alpha Vantage doesn't have 90min
        "1h": "60min",
        "1d": "daily",
        "1wk": "weekly",
        "1mo": "monthly",
    }
    return mapping.get(yfinance_interval, "daily")


def map_yfinance_to_alpaca(yfinance_interval: str) -> "TimeFrame":
    """
    Map yfinance interval to Alpaca TimeFrame.

    For migrating existing code from yfinance to Alpaca.

    Args:
        yfinance_interval: yfinance interval ('1m', '1wk', '1mo')

    Returns:
        Alpaca TimeFrame enum
    """
    mapping = {
        "1m": TimeFrame.Minute,
        "5m": TimeFrame.Minute,
        "15m": TimeFrame.Minute,
        "30m": TimeFrame.Minute,
        "60m": TimeFrame.Hour,
        "90m": TimeFrame.Hour,
        "1h": TimeFrame.Hour,
        "1d": TimeFrame.Day,
        "1wk": TimeFrame.Week,
        "1mo": TimeFrame.Month,
    }
    return mapping.get(yfinance_interval, TimeFrame.Day)


def get_valid_alphavantage_intervals() -> list[str]:
    """Get list of valid Alpha Vantage interval formats."""
    return [
        "1min",
        "5min",
        "15min",
        "30min",
        "60min",
        "daily",
        "weekly",
        "monthly",
    ]


def get_valid_alpaca_timeframes() -> list["TimeFrame"]:
    """Get list of valid Alpaca TimeFrame values."""
    return [
        TimeFrame.Minute,
        TimeFrame.Hour,
        TimeFrame.Day,
        TimeFrame.Week,
        TimeFrame.Month,
    ]
