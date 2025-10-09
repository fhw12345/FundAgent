"""
Admin-only API endpoints for system monitoring and health checks.
"""

from datetime import datetime

import structlog
from fastapi import APIRouter, Depends

from ..database.mongodb import MongoDB
from ..models.user import User
from ..services.database_stats_service import DatabaseStatsService
from .dependencies.auth import get_current_user, get_mongodb, require_admin
from .schemas.admin_models import HealthResponse, SystemMetrics

logger = structlog.get_logger()

router = APIRouter(prefix="/api/admin", tags=["admin"])


def get_database_stats_service(
    mongodb: MongoDB = Depends(get_mongodb),
) -> DatabaseStatsService:
    """Get database statistics service instance."""
    return DatabaseStatsService(mongodb.database)


@router.get("/health", response_model=HealthResponse)
async def get_system_health(
    _: None = Depends(require_admin),  # Admin access required
    current_user: User = Depends(get_current_user),  # Get user info
    db_stats_service: DatabaseStatsService = Depends(get_database_stats_service),
) -> SystemMetrics:
    """
    Get comprehensive system health metrics.

    **Admin only**: Requires admin privileges (username: allenpan or is_admin=True).

    Returns:
        SystemMetrics with database statistics and Kubernetes metrics (if available)
    """
    logger.info(
        "Admin health check requested",
        user_id=current_user.user_id,
        username=current_user.username,
    )

    # Collect database statistics
    database_stats = await db_stats_service.get_collection_stats()

    # Kubernetes metrics placeholder (to be implemented)
    pods = None
    nodes = None
    kubernetes_available = False

    # TODO: Add Kubernetes metrics service
    # try:
    #     k8s_service = KubernetesMetricsService()
    #     pods = await k8s_service.get_pod_metrics()
    #     nodes = await k8s_service.get_node_metrics()
    #     kubernetes_available = True
    # except Exception as e:
    #     logger.warning("Kubernetes metrics unavailable", error=str(e))

    # Determine health status
    health_status = "healthy"  # Basic health check for now

    # TODO: Add health checks:
    # - If any pod CPU/memory > 90%: critical
    # - If any pod CPU/memory > 70%: warning
    # - If database size growing rapidly: warning

    metrics = SystemMetrics(
        timestamp=datetime.utcnow(),
        database=database_stats,
        pods=pods,
        nodes=nodes,
        health_status=health_status,
        kubernetes_available=kubernetes_available,
    )

    logger.info(
        "System health metrics collected",
        db_collections=len(database_stats),
        k8s_available=kubernetes_available,
        status=health_status,
    )

    return metrics


@router.get("/database", response_model=list)
async def get_database_stats(
    _: None = Depends(require_admin),
    db_stats_service: DatabaseStatsService = Depends(get_database_stats_service),
):
    """
    Get database collection statistics only.

    **Admin only**: Requires admin privileges.

    Returns:
        List of database collection statistics
    """
    return await db_stats_service.get_collection_stats()
