"""
Admin-only API endpoints for system monitoring and health checks.
"""

from datetime import datetime

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends

from ..agent.langgraph_react_agent import FinancialAnalysisReActAgent
from ..agent.portfolio_analysis_agent import PortfolioAnalysisAgent
from ..core.config import get_settings
from ..core.data.ticker_data_service import TickerDataService
from ..database.mongodb import MongoDB
from ..database.redis import RedisCache
from ..database.repositories.transaction_repository import TransactionRepository
from ..database.repositories.user_repository import UserRepository
from ..models.user import User
from ..services.alpaca_data_service import AlpacaDataService
from ..services.alpaca_trading_service import AlpacaTradingService
from ..services.alphavantage_market_data import AlphaVantageMarketDataService
from ..services.credit_service import CreditService
from ..services.database_stats_service import DatabaseStatsService
from ..services.kubernetes_metrics_service import KubernetesMetricsService
from .dependencies.auth import (
    get_current_user,
    get_mongodb,
    get_redis_cache,
    require_admin,
)
from .schemas.admin_models import DatabaseStats, HealthResponse, SystemMetrics

logger = structlog.get_logger()

router = APIRouter(prefix="/api/admin", tags=["admin"])


def get_database_stats_service(
    mongodb: MongoDB = Depends(get_mongodb),
) -> DatabaseStatsService:
    """Get database statistics service instance."""
    return DatabaseStatsService(mongodb.database)


def get_kubernetes_metrics_service() -> KubernetesMetricsService:
    """Get Kubernetes metrics service instance."""
    settings = get_settings()
    return KubernetesMetricsService(namespace=settings.kubernetes_namespace)


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
) -> list[DatabaseStats]:
    """
    Get database collection statistics only.

    **Admin only**: Requires admin privileges.

    Returns:
        List of database collection statistics
    """
    return await db_stats_service.get_collection_stats()


@router.post("/portfolio/trigger-analysis", status_code=202)
async def trigger_portfolio_analysis(
    background_tasks: BackgroundTasks,
    mongodb: MongoDB = Depends(get_mongodb),
    redis_cache: RedisCache = Depends(get_redis_cache),
    _: None = Depends(require_admin),  # Requires admin role
):
    """
    Trigger portfolio analysis for all active users (admin only).

    This endpoint is designed to be called by:
    1. Kubernetes CronJob (scheduled daily at 8 PM EST)
    2. Admin UI (manual trigger for testing)
    3. CLI tools (development/testing)

    Returns immediately with 202 Accepted. Analysis runs in background.

    **Admin only**: Requires admin privileges.

    Returns:
        dict: Status message with run_id

    Raises:
        HTTPException: 401 if not authenticated as admin
    """
    run_id = f"run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    logger.info(
        "Portfolio analysis triggered via API",
        run_id=run_id,
        trigger_source="admin_endpoint",
    )

    # Add background task (runs after response is sent)
    background_tasks.add_task(
        run_portfolio_analysis_background,
        mongodb=mongodb,
        redis_cache=redis_cache,
        run_id=run_id,
    )

    return {
        "status": "started",
        "run_id": run_id,
        "message": "Portfolio analysis running in background",
        "note": "Check backend logs for progress and results",
    }


async def run_portfolio_analysis_background(
    mongodb: MongoDB,
    redis_cache: RedisCache,
    run_id: str,
):
    """
    Background task for portfolio analysis.

    This is the same logic as scripts/run_portfolio_analysis.py,
    but runs within the FastAPI process.

    Args:
        mongodb: MongoDB connection (already connected)
        redis_cache: Redis cache connection (already connected)
        run_id: Unique run identifier
    """
    logger.info(
        "Portfolio analysis background task started",
        run_id=run_id,
    )

    try:
        # Get settings
        settings = get_settings()

        # Initialize Alpha Vantage market data service (required)
        logger.info("Initializing Alpha Vantage market data service")
        market_service = AlphaVantageMarketDataService(settings=settings)

        # Initialize Alpaca services (optional)
        alpaca_data_service = None
        trading_service = None
        if settings.alpaca_api_key and settings.alpaca_secret_key:
            try:
                alpaca_data_service = AlpacaDataService(settings=settings)
                trading_service = AlpacaTradingService(settings=settings)
                logger.info("Alpaca services initialized (data + trading)")
            except Exception as e:
                logger.warning(
                    "Alpaca services unavailable - continuing without order placement",
                    error=str(e),
                )
        else:
            logger.info("Alpaca API keys not configured - no order placement")

        ticker_service = (
            TickerDataService(
                redis_cache=redis_cache,
                alpaca_data_service=alpaca_data_service,
            )
            if alpaca_data_service
            else None
        )

        # Initialize ReAct agent
        logger.info("Initializing ReAct agent")
        react_agent = FinancialAnalysisReActAgent(
            settings=settings,
            ticker_data_service=ticker_service,
            market_service=market_service,
        )

        logger.info(
            "ReAct agent initialized",
            total_tools=len(react_agent.tools),
        )

        # Initialize credit service for usage tracking
        logger.info("Initializing credit service")
        user_repo = UserRepository(mongodb.get_collection("users"))
        transaction_repo = TransactionRepository(mongodb.get_collection("transactions"))
        credit_service = CreditService(
            user_repo=user_repo,
            transaction_repo=transaction_repo,
            mongodb=mongodb,
            settings=settings,
        )
        logger.info("Credit service initialized")

        # Initialize portfolio analysis agent
        portfolio_agent = PortfolioAnalysisAgent(
            mongodb=mongodb,
            redis_cache=redis_cache,
            react_agent=react_agent,
            settings=settings,
            market_service=market_service,
            trading_service=trading_service,
            credit_service=credit_service,
        )

        # Run analysis for all users
        logger.info("Analyzing all users", run_id=run_id)
        result = await portfolio_agent.analyze_all_portfolios(dry_run=False)

        # Log summary
        logger.info(
            "Portfolio analysis completed successfully",
            run_id=result.get("run_id", run_id),
            users_analyzed=result.get("users_analyzed", 0),
            portfolios_analyzed=result.get("portfolios_analyzed", 0),
            errors_count=len(result.get("errors", [])),
            duration_seconds=result.get("metrics", {}).get("total_duration_seconds", 0),
        )

        # Print summary (appears in pod logs)
        print("\n" + "=" * 60)
        print("PORTFOLIO ANALYSIS SUMMARY")
        print("=" * 60)
        print(f"Run ID: {result.get('run_id', run_id)}")
        print(f"Users Analyzed: {result.get('users_analyzed', 0)}")
        print(f"Portfolios Analyzed: {result.get('portfolios_analyzed', 0)}")
        print(f"Errors: {len(result.get('errors', []))}")
        print(
            f"Duration: {result.get('metrics', {}).get('total_duration_seconds', 0):.2f}s"
        )
        print("=" * 60)

    except Exception as e:
        logger.error(
            "Portfolio analysis background task failed",
            run_id=run_id,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        # Don't raise - background task failure shouldn't crash the API
