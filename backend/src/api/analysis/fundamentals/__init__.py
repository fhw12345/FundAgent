"""
Stock fundamentals analysis endpoints.

Provides fundamental analysis data including company overview, financial statements,
and key metrics for equity analysis and valuation.

This module aggregates company and financial statement routers into a single
main fundamentals router.
"""

from fastapi import APIRouter

from .company import router as company_router
from .financials import router as financials_router

# Create main fundamentals router
router = APIRouter()

# Include all sub-routers
router.include_router(company_router)
router.include_router(financials_router)

# Export router for backward compatibility
__all__ = ["router"]
