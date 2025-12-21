"""Market Insights API router module.

Provides REST endpoints for the Market Insights Platform,
including category listing, metric retrieval, and data refresh.
"""

from fastapi import APIRouter

from .endpoints import router as insights_router

router = APIRouter(prefix="/api/insights", tags=["Market Insights"])
router.include_router(insights_router)

__all__ = ["router"]
