"""
Alpha Vantage market data service (backward compatibility layer).

This module re-exports from the modular market_data package for backward compatibility.
New code should import from market_data package directly.

Example:
    # Old import (still works)
    from src.services.alphavantage_market_data import AlphaVantageMarketDataService

    # New import (preferred)
    from src.services.market_data import AlphaVantageMarketDataService
"""

# Re-export all public APIs from the modular package
from .market_data import (
    AlphaVantageMarketDataService,
    get_market_session,
    validate_date_range,
)

__all__ = [
    "AlphaVantageMarketDataService",
    "get_market_session",
    "validate_date_range",
]
