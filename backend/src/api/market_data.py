"""
Market Data API - Backward compatibility layer.

This module re-exports from the modular market package for backward compatibility.
The market_data.py file has been split into a modular structure:

    backend/src/api/market/
    ├── __init__.py           # Router aggregation
    ├── prices.py             # Price endpoints: get_price_data, get_quote
    ├── search.py             # Search endpoints: search_symbols, market_movers
    ├── status.py             # Status endpoints: market_status
    └── fundamentals.py       # Fundamentals: overview, news, financials

New code should import from the market package directly:
    from src.api.market import router
    from src.api.market.prices import PriceDataResponse
    from src.api.market.search import SymbolSearchResult

This file maintains compatibility with existing imports:
    from src.api.market_data import router  # Still works
"""

# Re-export router for backward compatibility
from .market import router

# Re-export models for backward compatibility
from .market.prices import PriceDataPoint, PriceDataResponse, QuoteResponse
from .market.search import SymbolSearchResponse, SymbolSearchResult
from .market.status import MarketStatusResponse

__all__ = [
    "router",
    "PriceDataPoint",
    "PriceDataResponse",
    "QuoteResponse",
    "SymbolSearchResult",
    "SymbolSearchResponse",
    "MarketStatusResponse",
]
