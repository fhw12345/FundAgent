"""Admin API endpoints — simplified for FundAgent."""

import structlog
from fastapi import APIRouter, Depends

from ..database.mongodb import MongoDB
from ..database.redis import RedisCache
from ..services.database_stats_service import DatabaseStatsService
from .dependencies.auth import get_current_user, get_mongodb, get_redis_cache, require_admin
from .dependencies.timing_middleware import TimingMiddleware

logger = structlog.get_logger()

router = APIRouter(prefix="/api/admin", tags=["admin"])


def get_database_stats_service(
    mongodb: MongoDB = Depends(get_mongodb),
) -> DatabaseStatsService:
    return DatabaseStatsService(mongodb.database)


@router.get("/health")
async def get_system_health(
    _: None = Depends(require_admin),
    db_stats_service: DatabaseStatsService = Depends(get_database_stats_service),
):
    database_stats = await db_stats_service.get_collection_stats()
    return {
        "health_status": "healthy",
        "database": database_stats,
    }


@router.get("/database")
async def get_database_stats(
    _: None = Depends(require_admin),
    db_stats_service: DatabaseStatsService = Depends(get_database_stats_service),
):
    return await db_stats_service.get_collection_stats()


@router.get("/timing-metrics")
async def get_timing_metrics(_: None = Depends(require_admin)):
    metrics = TimingMiddleware.get_all_metrics()
    return dict(
        sorted(metrics.items(), key=lambda x: x[1].get("p95") or 0, reverse=True)
    )


@router.get("/cache/stats")
async def get_cache_stats(
    _: None = Depends(require_admin),
    redis_cache: RedisCache = Depends(get_redis_cache),
):
    try:
        return await redis_cache.get_cache_stats()
    except Exception as e:
        logger.error("Failed to get cache stats", error=str(e))
        return {"status": "error", "message": str(e)}
