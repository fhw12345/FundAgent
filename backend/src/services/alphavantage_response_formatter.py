"""
Alpha Vantage Response Formatter (backward compatibility layer).

This module re-exports from the modular formatters package for backward compatibility.
New code should import from src.services.formatters directly.

Example:
    # Old import (still works)
    from src.services.alphavantage_response_formatter import AlphaVantageResponseFormatter

    # New import (preferred)
    from src.services.formatters import AlphaVantageResponseFormatter
"""

# Re-export from the modular package
from .formatters import AlphaVantageResponseFormatter

__all__ = ["AlphaVantageResponseFormatter"]
