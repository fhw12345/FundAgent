"""
Portfolio Analysis Agent - Autonomous portfolio analysis.

Runs periodically (CronJob) to analyze all active user portfolios.
"""

from datetime import datetime
from typing import Any

import structlog

from ..core.config import Settings
from ..database.mongodb import MongoDB
from ..database.redis import RedisCache
from ..database.repositories.user_repository import UserRepository
from .langgraph_react_agent import FinancialAnalysisReActAgent

logger = structlog.get_logger()


class PortfolioAnalysisAgent:
    """
    Autonomous agent for portfolio analysis.

    Features:
    - Analyzes all active user portfolios
    - Uses ReAct agent with 120 tools (2 local + 118 MCP)
    - Stores analysis results in MongoDB
    - Handles errors gracefully
    """

    def __init__(
        self,
        mongodb: MongoDB,
        redis_cache: RedisCache,
        react_agent: FinancialAnalysisReActAgent,
        settings: Settings,
    ):
        """
        Initialize portfolio analysis agent.

        Args:
            mongodb: MongoDB connection
            redis_cache: Redis cache connection
            react_agent: ReAct agent with MCP tools
            settings: Application settings
        """
        self.mongodb = mongodb
        self.redis_cache = redis_cache
        self.react_agent = react_agent
        self.settings = settings

        # Repositories
        self.user_repo = UserRepository(mongodb.get_collection("users"))

    async def analyze_all_portfolios(self, dry_run: bool = False) -> dict[str, Any]:
        """
        Run analysis for all active user portfolios.

        Args:
            dry_run: If True, don't write results to DB

        Returns:
            Execution summary with metrics
        """
        run_id = f"run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        started_at = datetime.utcnow()

        logger.info(
            "Portfolio analysis started",
            run_id=run_id,
            dry_run=dry_run,
        )

        # Get all active users with portfolios
        # TODO: Implement get_active_users_with_portfolios in UserRepository
        # For now, return mock data
        users_to_analyze = []

        results = {
            "run_id": run_id,
            "started_at": started_at.isoformat(),
            "dry_run": dry_run,
            "users_to_analyze": len(users_to_analyze),
            "users_analyzed": 0,
            "portfolios_analyzed": 0,
            "errors": [],
            "metrics": {},
        }

        if not users_to_analyze:
            logger.info("No users with portfolios to analyze", run_id=run_id)
            results["completed_at"] = datetime.utcnow().isoformat()
            return results

        # Analyze each user's portfolio
        for user in users_to_analyze:
            try:
                user_result = await self.analyze_user_portfolio(
                    user_id=user["user_id"],
                    dry_run=dry_run,
                )

                results["users_analyzed"] += 1
                results["portfolios_analyzed"] += user_result.get("portfolios_count", 0)

            except Exception as e:
                logger.error(
                    "Failed to analyze user portfolio",
                    run_id=run_id,
                    user_id=user.get("user_id"),
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True,
                )

                results["errors"].append(
                    {
                        "user_id": user.get("user_id"),
                        "error": str(e),
                        "error_type": type(e).__name__,
                    }
                )

        # Calculate metrics
        completed_at = datetime.utcnow()
        duration_seconds = (completed_at - started_at).total_seconds()

        results["completed_at"] = completed_at.isoformat()
        results["metrics"] = {
            "total_duration_seconds": duration_seconds,
            "avg_duration_per_user_seconds": (
                duration_seconds / results["users_analyzed"]
                if results["users_analyzed"] > 0
                else 0
            ),
        }

        # Store execution record in MongoDB
        if not dry_run:
            await self._store_execution_record(results)

        logger.info(
            "Portfolio analysis completed",
            run_id=run_id,
            users_analyzed=results["users_analyzed"],
            portfolios_analyzed=results["portfolios_analyzed"],
            errors_count=len(results["errors"]),
            duration_seconds=duration_seconds,
        )

        return results

    async def analyze_user_portfolio(
        self, user_id: str, dry_run: bool = False
    ) -> dict[str, Any]:
        """
        Run analysis for single user's portfolio.

        Args:
            user_id: User identifier
            dry_run: If True, don't write results to DB

        Returns:
            Analysis result summary
        """
        logger.info("Analyzing user portfolio", user_id=user_id, dry_run=dry_run)

        # TODO: Implement portfolio analysis
        # 1. Get user's active portfolio holdings
        # 2. For each holding, run analysis using ReAct agent
        # 3. Store analysis results
        # 4. Generate summary

        # Mock result for now
        result = {
            "user_id": user_id,
            "portfolios_count": 0,
            "holdings_analyzed": 0,
            "analysis_summary": "Portfolio analysis not yet implemented",
        }

        logger.info(
            "User portfolio analysis completed",
            user_id=user_id,
            holdings_analyzed=result["holdings_analyzed"],
        )

        return result

    async def _store_execution_record(self, execution_data: dict[str, Any]) -> None:
        """
        Store execution record in MongoDB.

        Args:
            execution_data: Execution result data
        """
        try:
            collection = self.mongodb.get_collection("portfolio_analysis_runs")
            await collection.insert_one(execution_data)

            logger.info(
                "Execution record stored",
                run_id=execution_data["run_id"],
            )

        except Exception as e:
            logger.error(
                "Failed to store execution record",
                run_id=execution_data.get("run_id"),
                error=str(e),
                error_type=type(e).__name__,
            )
            # Don't raise - execution succeeded even if record storage failed
