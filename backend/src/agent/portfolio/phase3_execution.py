"""
Phase 3: Execution - Order placement and execution.

This module orchestrates order execution via OrderOptimizer.
"""

from typing import Any

import structlog

from ...models.trading_decision import SymbolAnalysisResult

logger = structlog.get_logger()


class Phase3ExecutionMixin:
    """Mixin providing Phase 3 execution capabilities."""

    async def _run_phase3_execution(
        self,
        trading_decisions: list[Any],
        all_analysis_results: list[SymbolAnalysisResult],
        portfolio_context: dict[str, Any],
        user_id: str,
        result_summary: dict[str, Any],
    ) -> None:
        """
        Run Phase 3: Execute orders (SELLs first for liquidity, then BUYs).

        Args:
            trading_decisions: Trading decisions from Phase 2
            all_analysis_results: Symbol analyses from Phase 1
            portfolio_context: Portfolio state
            user_id: User ID for tracking
            result_summary: Result summary dict to update
        """
        if not trading_decisions:
            logger.info("Phase 2: No trading decisions made")
            return

        logger.info(
            "Phase 3: Converting decisions to execution plan",
            decisions_count=len(trading_decisions),
        )

        # Convert TradingDecisions to OrderExecutionPlan via optimizer
        execution_plan = await self.order_optimizer.optimize_trading_decisions(
            analysis_results=all_analysis_results,
            portfolio_context=portfolio_context,
            user_id=user_id,
            trading_decisions=trading_decisions,  # Pass pre-made decisions
        )

        if execution_plan and execution_plan.orders:
            logger.info(
                "Phase 3: Executing orders",
                orders_count=len(execution_plan.orders),
                scaling_applied=execution_plan.scaling_applied,
            )

            execution_result = await self.order_optimizer.execute_order_plan(
                plan=execution_plan,
                user_id=user_id,
                analysis_results=all_analysis_results,
            )

            result_summary["orders_executed"] = execution_result.get("executed", 0)
            result_summary["orders_failed"] = execution_result.get("failed", 0)
            result_summary["orders_skipped"] = execution_result.get("skipped", 0)

            logger.info(
                "Phase 3 complete: Order execution finished",
                executed=result_summary["orders_executed"],
                failed=result_summary["orders_failed"],
                skipped=result_summary["orders_skipped"],
            )
        else:
            logger.info("Phase 3: No actionable orders after optimization")
