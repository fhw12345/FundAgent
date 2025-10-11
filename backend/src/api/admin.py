"""
Admin-only API endpoints for system monitoring and health checks.
"""

from datetime import datetime

import structlog
from fastapi import APIRouter, Depends

from ..database.mongodb import MongoDB
from ..models.user import User
from ..services.database_stats_service import DatabaseStatsService
from ..services.kubernetes_metrics_service import KubernetesMetricsService
from .dependencies.auth import get_current_user, get_mongodb, require_admin
from .schemas.admin_models import HealthResponse, SystemMetrics

logger = structlog.get_logger()

router = APIRouter(prefix="/api/admin", tags=["admin"])


def get_database_stats_service(
    mongodb: MongoDB = Depends(get_mongodb),
) -> DatabaseStatsService:
    """Get database statistics service instance."""
    return DatabaseStatsService(mongodb.database)


def get_kubernetes_metrics_service() -> KubernetesMetricsService:
    """Get Kubernetes metrics service instance."""
    return KubernetesMetricsService(namespace="klinematrix-test")


@router.get("/health", response_model=HealthResponse)
async def get_system_health(
    _: None = Depends(require_admin),  # Admin access required
    current_user: User = Depends(get_current_user),  # Get user info
    db_stats_service: DatabaseStatsService = Depends(get_database_stats_service),
    k8s_service: KubernetesMetricsService = Depends(get_kubernetes_metrics_service),
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

    # Collect Kubernetes metrics
    pods = None
    nodes = None
    kubernetes_available = k8s_service.available

    if kubernetes_available:
        try:
            pods = await k8s_service.get_pod_metrics()
            nodes = await k8s_service.get_node_metrics()
            logger.info(
                "Kubernetes metrics collected",
                pod_count=len(pods) if pods else 0,
                node_count=len(nodes) if nodes else 0,
            )
        except Exception as e:
            logger.warning("Failed to collect Kubernetes metrics", error=str(e))
            kubernetes_available = False

    # Determine health status based on metrics
    health_status = "healthy"

    # Check for critical resource usage
    if pods:
        for pod in pods:
            if pod.cpu_percentage > 90 or pod.memory_percentage > 90:
                health_status = "critical"
                logger.warning(
                    "Critical resource usage detected",
                    pod=pod.name,
                    cpu=pod.cpu_percentage,
                    memory=pod.memory_percentage,
                )
                break
            elif pod.cpu_percentage > 70 or pod.memory_percentage > 70:
                health_status = "warning"
                logger.info(
                    "High resource usage detected",
                    pod=pod.name,
                    cpu=pod.cpu_percentage,
                    memory=pod.memory_percentage,
                )

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
        pod_count=len(pods) if pods else 0,
        node_count=len(nodes) if nodes else 0,
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
