"""
Market Data API module.

Aggregates all market data endpoints into a single router.
Maintains backward compatibility with the original market_data.py module.
"""

from fastapi import APIRouter

from . import fundamentals, prices, search, status

# Create main router with common prefix and tags
router = APIRouter(prefix="/api/market", tags=["Market Data"])

# Include all sub-routers
router.include_router(prices.router)
router.include_router(search.router)
router.include_router(status.router)
router.include_router(fundamentals.router)

# Export router for backward compatibility
__all__ = ["router"]
