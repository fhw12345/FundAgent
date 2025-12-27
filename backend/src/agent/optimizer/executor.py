"""
Order Execution Engine.

Handles:
1. Order placement via Alpaca trading service
2. Batch persistence to database
3. Metadata updates for messages
"""

import uuid
from typing import Any

import structlog

from src.core.utils.date_utils import utcnow

from ...database.repositories.message_repository import MessageRepository
from ...database.repositories.portfolio_order_repository import PortfolioOrderRepository
from ...models.message import MessageMetadata
from ...models.portfolio import PortfolioOrder
from ...models.trading_decision import (
    OrderExecutionPlan,
    SymbolAnalysisResult,
)

logger = structlog.get_logger()


class OrderExecutor:
    """
    Executes optimized order plans via trading service.

    Handles order placement, persistence, and metadata updates with batching
    for efficiency.
    """

    def __init__(
        self,
        trading_service: Any,
        order_repo: PortfolioOrderRepository,
        message_repo: MessageRepository,
    ):
        """
        Initialize order executor.

        Args:
            trading_service: Alpaca trading service for order placement
            order_repo: Repository for persisting orders
            message_repo: Repository for updating message metadata
        """
        self.trading_service = trading_service
        self.order_repo = order_repo
        self.message_repo = message_repo

    async def execute_order_plan(
        self,
        plan: OrderExecutionPlan,
        user_id: str,
        analysis_results: list[SymbolAnalysisResult],
    ) -> dict[str, Any]:
        """
        Execute the optimized order plan via Alpaca trading service.

        Orders are executed in priority order (SELLs first, then BUYs).
        Database persistence is batched for efficiency.

        Args:
            plan: OrderExecutionPlan from aggregation hook
            user_id: User ID for the trades
            analysis_results: Original analysis results (for linking orders to messages)

        Returns:
            Execution summary with success/failure counts
        """
        if not self.trading_service:
            logger.warning("Trading service not available - skipping order execution")
            return {
                "executed": 0,
                "failed": 0,
                "skipped": 0,
                "reason": "trading_service_unavailable",
            }

        if not plan.orders:
            logger.info("No orders to execute")
            return {"executed": 0, "failed": 0, "skipped": 0, "reason": "no_orders"}

        # Sort by priority (already sorted, but ensure)
        sorted_orders = sorted(plan.orders, key=lambda o: o.priority)

        executed = 0
        failed = 0
        skipped = 0

        # Collect orders for batch persistence (both successful and failed)
        executed_orders = []
        failed_orders = []
        metadata_updates: list[tuple[str, MessageMetadata]] = []

        # Build lookup for analysis results by symbol
        analysis_by_symbol = {r.symbol: r for r in analysis_results}

        for order in sorted_orders:
            if order.skip_reason:
                logger.info(
                    "Skipping order",
                    symbol=order.symbol,
                    reason=order.skip_reason,
                )
                skipped += 1
                continue

            try:
                # Get analysis result for this symbol (for linking)
                analysis = analysis_by_symbol.get(order.symbol)
                analysis_id = analysis.analysis_id if analysis else None
                chat_id = analysis.chat_id if analysis else None
                message_id = analysis.message_id if analysis else None

                logger.info(
                    "Executing order",
                    symbol=order.symbol,
                    side=order.side,
                    shares=order.shares,
                    priority=order.priority,
                    estimated_cost=order.estimated_cost,
                    is_cover=order.is_cover,
                )

                # Place order via Alpaca (must be sequential - affects buying power)
                alpaca_order = await self.trading_service.place_market_order(
                    symbol=order.symbol,
                    quantity=order.shares,
                    side=order.side,
                    analysis_id=analysis_id,
                    chat_id=chat_id,
                    user_id=user_id,
                    message_id=message_id,
                )

                # Collect for batch persistence
                executed_orders.append(alpaca_order)

                logger.info(
                    "Order executed successfully",
                    symbol=order.symbol,
                    alpaca_order_id=alpaca_order.alpaca_order_id,
                    side=order.side,
                    shares=order.shares,
                )

                # Collect metadata update for batch processing
                if message_id:
                    metadata = MessageMetadata(
                        symbol=order.symbol,
                        order_placed=True,
                        order_id=alpaca_order.alpaca_order_id,
                    )
                    metadata_updates.append((message_id, metadata))

                executed += 1

            except Exception as e:
                error_message = str(e)
                logger.error(
                    "Order execution failed",
                    symbol=order.symbol,
                    side=order.side,
                    shares=order.shares,
                    error=error_message,
                    error_type=type(e).__name__,
                )

                # Create failed order record for audit trail
                analysis = analysis_by_symbol.get(order.symbol)
                failed_order = PortfolioOrder(
                    order_id=f"order_{uuid.uuid4().hex[:12]}",
                    chat_id=analysis.chat_id if analysis else "unknown",
                    user_id=user_id,
                    message_id=analysis.message_id if analysis else None,
                    alpaca_order_id=None,  # No Alpaca ID for failed orders
                    analysis_id=(
                        analysis.analysis_id if analysis else f"failed_{order.symbol}"
                    ),
                    symbol=order.symbol,
                    order_type="market",
                    side=order.side,
                    quantity=float(order.shares),
                    limit_price=None,
                    stop_price=None,
                    time_in_force="day",
                    status="failed",
                    filled_qty=0.0,
                    filled_avg_price=None,
                    filled_at=None,
                    error_message=error_message,
                    created_at=utcnow(),
                )
                failed_orders.append(failed_order)
                failed += 1

        # Batch persist orders to MongoDB (single DB call instead of N calls)
        if executed_orders:
            try:
                await self.order_repo.create_many(executed_orders)
            except Exception as e:
                logger.error(
                    "Batch order persistence failed",
                    error=str(e),
                    order_count=len(executed_orders),
                )

        # Batch persist failed orders (for audit trail and UI display)
        if failed_orders:
            try:
                await self.order_repo.create_many(failed_orders)
                logger.info(
                    "Failed orders persisted for audit trail",
                    count=len(failed_orders),
                    symbols=[o.symbol for o in failed_orders],
                )
            except Exception as e:
                logger.error(
                    "Batch failed order persistence failed",
                    error=str(e),
                    order_count=len(failed_orders),
                )

        # Batch update message metadata (single DB call instead of N calls)
        if metadata_updates:
            try:
                await self.message_repo.update_metadata_batch(metadata_updates)
            except Exception as e:
                logger.error(
                    "Batch metadata update failed",
                    error=str(e),
                    update_count=len(metadata_updates),
                )

        logger.info(
            "Order execution completed",
            executed=executed,
            failed=failed,
            skipped=skipped,
            total_orders=len(sorted_orders),
        )

        return {
            "executed": executed,
            "failed": failed,
            "skipped": skipped,
            "total_orders": len(sorted_orders),
        }
