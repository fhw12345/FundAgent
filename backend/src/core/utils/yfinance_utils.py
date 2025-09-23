"""
yfinance utility functions for interval mapping and data handling.
Centralizes yfinance-specific logic to avoid duplication across the codebase.
"""

from typing import Dict


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
    interval_map: Dict[str, str] = {
        # Most intervals work as-is
        '1m': '1m',
        '2m': '2m',
        '5m': '5m',
        '15m': '15m',
        '30m': '30m',
        '60m': '60m',
        '90m': '90m',
        '1h': '1h',
        '1d': '1d',
        '5d': '5d',
        '3mo': '3mo',

        # These require mapping for yfinance compatibility
        '1w': '1wk',   # Weekly: Frontend '1w' → yfinance '1wk' (required)
        '1M': '1mo',   # Monthly: Frontend '1M' → yfinance '1mo' (required)
        '1mo': '1mo',  # Monthly: Frontend '1mo' → yfinance '1mo' (already compatible)
    }

    return interval_map.get(frontend_interval, frontend_interval)


def get_valid_frontend_intervals() -> list[str]:
    """Get list of valid frontend interval formats."""
    return ['1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h', '1d', '5d', '1w', '1M', '1mo', '3mo']


def get_valid_yfinance_intervals() -> list[str]:
    """Get list of valid yfinance interval formats."""
    return ['1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h', '1d', '5d', '1wk', '1mo', '3mo']