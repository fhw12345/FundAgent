"""Market Insights API endpoints.

Provides REST API for accessing insight categories, metrics,
and composite scores with caching support.
"""

import time

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from ...services.insights import InsightsCategoryRegistry
from ..schemas.insights_models import (
    CategoriesListResponse,
    CategoryMetadataResponse,
    CompositeScoreResponse,
    InsightCategoryResponse,
    InsightMetricResponse,
    RefreshResponse,
)

logger = structlog.get_logger()
router = APIRouter()

# Rate limiting
limiter = Limiter(key_func=get_remote_address)


def get_insights_registry(request: Request) -> InsightsCategoryRegistry:
    """Get insights registry singleton from app state.

    The registry is initialized once at application startup in main.py lifespan,
    ensuring consistent caching and avoiding per-request instantiation overhead.
    """
    return request.app.state.insights_registry


@router.get("/categories", response_model=CategoriesListResponse)
@limiter.limit("60/minute")
async def list_categories(
    request: Request,
    registry: InsightsCategoryRegistry = Depends(get_insights_registry),
) -> CategoriesListResponse:
    """
    List all available insight categories.

    Returns metadata for each category including name, icon, description,
    and metric count. Use the category ID to fetch full category data.

    **Rate Limit**: 60 requests per minute
    """
    request_start = time.time()

    try:
        categories = registry.list_categories()

        response = CategoriesListResponse(
            categories=[
                CategoryMetadataResponse(
                    id=cat.id,
                    name=cat.name,
                    icon=cat.icon,
                    description=cat.description,
                    metric_count=cat.metric_count,
                    last_updated=cat.last_updated,
                )
                for cat in categories
            ],
            count=len(categories),
        )

        duration = time.time() - request_start
        logger.info(
            "Categories listed",
            category_count=len(categories),
            duration_ms=round(duration * 1000, 2),
        )

        return response

    except Exception as e:
        logger.error("Failed to list categories", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list categories") from e


@router.get("/{category_id}", response_model=InsightCategoryResponse)
@limiter.limit("30/minute")
async def get_category(
    category_id: str,
    request: Request,
    force_refresh: bool = False,
    registry: InsightsCategoryRegistry = Depends(get_insights_registry),
) -> InsightCategoryResponse:
    """
    Get complete data for a category including all metrics.

    Returns all metrics with scores, explanations, and the composite score.
    Results are cached for 30 minutes unless force_refresh=true.

    **Rate Limit**: 30 requests per minute (API-heavy operation)

    Args:
        category_id: The category identifier (e.g., 'ai_sector_risk')
        force_refresh: If true, bypass cache and recalculate

    Returns:
        Complete category data with all metrics
    """
    request_start = time.time()

    try:
        logger.info(
            "Category data requested",
            category_id=category_id,
            force_refresh=force_refresh,
        )

        data = await registry.get_category_data(
            category_id, force_refresh=force_refresh
        )

        if data is None:
            raise HTTPException(
                status_code=404,
                detail=f"Category '{category_id}' not found",
            )

        # Convert to response model
        response = InsightCategoryResponse(
            id=data.id,
            name=data.name,
            icon=data.icon,
            description=data.description,
            metrics=[
                InsightMetricResponse(
                    id=m.id,
                    name=m.name,
                    score=m.score,
                    status=m.status.value,
                    explanation=m.explanation.model_dump(),  # type: ignore
                    data_sources=m.data_sources,
                    last_updated=m.last_updated,
                    raw_data=m.raw_data,
                )
                for m in data.metrics
            ],
            composite=(
                CompositeScoreResponse(
                    score=data.composite.score,
                    status=data.composite.status.value,
                    weights=data.composite.weights,
                    breakdown=data.composite.breakdown,
                    interpretation=data.composite.interpretation,
                )
                if data.composite
                else None
            ),
            last_updated=data.last_updated,
        )

        duration = time.time() - request_start
        logger.info(
            "Category data returned",
            category_id=category_id,
            metric_count=len(data.metrics),
            duration_ms=round(duration * 1000, 2),
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get category data", category_id=category_id, error=str(e)
        )
        raise HTTPException(
            status_code=500, detail="Failed to get category data"
        ) from e


@router.get("/{category_id}/composite", response_model=CompositeScoreResponse)
@limiter.limit("60/minute")
async def get_composite(
    category_id: str,
    request: Request,
    registry: InsightsCategoryRegistry = Depends(get_insights_registry),
) -> CompositeScoreResponse:
    """
    Get just the composite score for a category.

    Returns the weighted composite score with breakdown by metric.
    Useful for quick overview without full metric details.

    **Rate Limit**: 60 requests per minute
    """
    request_start = time.time()

    try:
        instance = registry.get_category_instance(category_id)

        if instance is None:
            raise HTTPException(
                status_code=404,
                detail=f"Category '{category_id}' not found",
            )

        composite = await instance.get_composite()

        response = CompositeScoreResponse(
            score=composite.score,
            status=composite.status.value,
            weights=composite.weights,
            breakdown=composite.breakdown,
            interpretation=composite.interpretation,
        )

        duration = time.time() - request_start
        logger.info(
            "Composite score returned",
            category_id=category_id,
            score=composite.score,
            duration_ms=round(duration * 1000, 2),
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get composite", category_id=category_id, error=str(e))
        raise HTTPException(
            status_code=500, detail="Failed to get composite score"
        ) from e


@router.get("/{category_id}/{metric_id}", response_model=InsightMetricResponse)
@limiter.limit("60/minute")
async def get_metric(
    category_id: str,
    metric_id: str,
    request: Request,
    registry: InsightsCategoryRegistry = Depends(get_insights_registry),
) -> InsightMetricResponse:
    """
    Get a single metric with full explanation.

    Returns detailed metric data including score, explanation,
    methodology, and raw calculation data.

    **Rate Limit**: 60 requests per minute
    """
    request_start = time.time()

    try:
        instance = registry.get_category_instance(category_id)

        if instance is None:
            raise HTTPException(
                status_code=404,
                detail=f"Category '{category_id}' not found",
            )

        metric = await instance.get_metric(metric_id)

        if metric is None:
            raise HTTPException(
                status_code=404,
                detail=f"Metric '{metric_id}' not found in category '{category_id}'",
            )

        response = InsightMetricResponse(
            id=metric.id,
            name=metric.name,
            score=metric.score,
            status=metric.status.value,
            explanation=metric.explanation.model_dump(),  # type: ignore
            data_sources=metric.data_sources,
            last_updated=metric.last_updated,
            raw_data=metric.raw_data,
        )

        duration = time.time() - request_start
        logger.info(
            "Metric returned",
            category_id=category_id,
            metric_id=metric_id,
            score=metric.score,
            duration_ms=round(duration * 1000, 2),
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get metric",
            category_id=category_id,
            metric_id=metric_id,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail="Failed to get metric") from e


@router.post("/{category_id}/refresh", response_model=RefreshResponse)
@limiter.limit("5/minute")
async def refresh_category(
    category_id: str,
    request: Request,
    registry: InsightsCategoryRegistry = Depends(get_insights_registry),
) -> RefreshResponse:
    """
    Force refresh a category's data.

    Clears the cache and recalculates all metrics from fresh API data.
    Use sparingly as this makes multiple Alpha Vantage API calls.

    **Rate Limit**: 5 requests per minute (API-heavy operation)
    """
    request_start = time.time()

    try:
        logger.info("Category refresh requested", category_id=category_id)

        data = await registry.refresh_category(category_id)

        if data is None:
            raise HTTPException(
                status_code=404,
                detail=f"Category '{category_id}' not found",
            )

        duration = time.time() - request_start
        logger.info(
            "Category refreshed",
            category_id=category_id,
            duration_ms=round(duration * 1000, 2),
        )

        return RefreshResponse(
            success=True,
            category_id=category_id,
            message=f"Category '{category_id}' refreshed successfully",
            last_updated=data.last_updated,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to refresh category", category_id=category_id, error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to refresh category") from e
