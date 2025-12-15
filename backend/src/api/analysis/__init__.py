"""
Financial Analysis API module.

Provides REST API access to core financial analysis functionality including:
- Fibonacci retracement analysis
- Macro sentiment analysis
- Stock fundamentals and company overview
- Technical analysis (Stochastic oscillator, charts)
- News sentiment and market movers
- Analysis history tracking

This module aggregates all analysis sub-routers into a single main router.
"""

from fastapi import APIRouter

from .fibonacci import router as fibonacci_router
from .fundamentals import router as fundamentals_router
from .history import router as history_router
from .macro import router as macro_router
from .news import router as news_router
from .shared import TOOL_REGISTRY, create_tool_call
from .technical import router as technical_router

# Create main analysis router
router = APIRouter(prefix="/api/analysis", tags=["Financial Analysis"])

# Include all sub-routers
router.include_router(fibonacci_router)
router.include_router(macro_router)
router.include_router(fundamentals_router)
router.include_router(technical_router)
router.include_router(news_router)
router.include_router(history_router)

# Export commonly used utilities for backward compatibility
__all__ = [
    "router",
    "TOOL_REGISTRY",
    "create_tool_call",
]
