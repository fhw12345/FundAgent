"""
Order Optimization Module - Phase 3 of Portfolio Analysis.

Converts TradingDecisions from Phase 2 into an optimized OrderExecutionPlan
and executes orders (SELLs first for liquidity, then BUYs).
"""

import uuid
from datetime import datetime
from typing import Any

import structlog

from ..database.repositories.message_repository import MessageRepository
from ..database.repositories.portfolio_order_repository import PortfolioOrderRepository
from ..models.message import MessageMetadata
from ..models.portfolio import PortfolioOrder
from ..models.trading_decision import (
    OptimizedOrder,
    OrderExecutionPlan,
    SymbolAnalysisResult,
    TradingAction,
    TradingDecision,
)

logger = structlog.get_logger()


class OrderOptimizer:
    """
    Phase 3: Order optimization and execution.

    Responsibilities:
    1. Convert TradingDecisions from Phase 2 into OrderExecutionPlan
    2. Calculate share quantities and apply liquidity constraints
    3. Execute orders (SELLs first for liquidity, then scaled BUYs)
    """

    def __init__(
        self,
        react_agent,
        trading_service,
        order_repo: PortfolioOrderRepository,
        message_repo: MessageRepository,
    ):
        """
        Initialize order optimizer.

        Args:
            react_agent: ReAct agent (for potential future use)
            trading_service: Alpaca trading service for order placement
            order_repo: Repository for persisting orders
            message_repo: Repository for updating message metadata
        """
        self.react_agent = react_agent
        self.trading_service = trading_service
        self.order_repo = order_repo
        self.message_repo = message_repo

    async def optimize_trading_decisions(
        self,
        analysis_results: list[SymbolAnalysisResult],
        portfolio_context: dict[str, Any],
        user_id: str,
        trading_decisions: list[TradingDecision] | None = None,
    ) -> OrderExecutionPlan | None:
        """
        Phase 3: Convert trading decisions into an optimized execution plan.

        Takes pre-made TradingDecisions from Phase 2 and builds an OrderExecutionPlan:
        1. SELLs first (to free up buying power / gain liquidity)
        2. Calculate available funds = current_buying_power + estimated_sell_proceeds
        3. Scale down BUYs proportionally if insufficient funds
        4. Return OrderExecutionPlan for execution

        Args:
            analysis_results: List of SymbolAnalysisResult from Phase 1 (for linking)
            portfolio_context: Portfolio state (equity, buying_power, positions)
            user_id: User ID for the portfolio
            trading_decisions: Pre-made decisions from Phase 2 (required in new flow)

        Returns:
            OrderExecutionPlan with optimized order sequence, or None if failed
        """
        # Validate inputs
        if not trading_decisions:
            logger.info("No trading decisions provided to optimize")
            return None

        # Filter to actionable decisions (exclude HOLD)
        actionable_decisions = [
            d for d in trading_decisions if d.decision != TradingAction.HOLD
        ]

        if not actionable_decisions:
            logger.info("All decisions are HOLD - no orders to execute")
            return OrderExecutionPlan(
                orders=[],
                total_sell_proceeds=0.0,
                total_buy_cost=0.0,
                available_buying_power=portfolio_context.get("buying_power", 0),
                scaling_applied=False,
                scaling_factor=None,
                orders_skipped=0,
                notes="All symbols analyzed resulted in HOLD decisions. No trading action required.",
            )

        # Extract portfolio state
        buying_power = portfolio_context.get("buying_power", 0)
        positions = portfolio_context.get("positions", [])

        # Build lookup for positions
        positions_by_symbol = {p["symbol"]: p for p in positions}

        logger.info(
            "Building execution plan from trading decisions",
            actionable_count=len(actionable_decisions),
            buying_power=buying_power,
            positions_count=len(positions),
        )

        # Separate SELLs and BUYs
        sell_decisions = [
            d for d in actionable_decisions if d.decision == TradingAction.SELL
        ]
        buy_decisions = [
            d for d in actionable_decisions if d.decision == TradingAction.BUY
        ]

        orders: list[OptimizedOrder] = []
        total_sell_proceeds = 0.0
        total_buy_cost = 0.0
        orders_skipped = 0
        priority = 1
        notes_parts = []

        # Track cover orders separately (highest priority - reduce risk first)
        cover_orders: list[OptimizedOrder] = []
        sell_orders: list[OptimizedOrder] = []

        # Process SELL orders (includes handling short positions)
        for decision in sell_decisions:
            pos = positions_by_symbol.get(decision.symbol)
            if not pos:
                logger.warning(
                    "SELL skipped: no position found",
                    symbol=decision.symbol,
                )
                orders_skipped += 1
                continue

            if not decision.position_size_percent:
                logger.warning(
                    "SELL skipped: no position_size_percent",
                    symbol=decision.symbol,
                )
                orders_skipped += 1
                continue

            position_qty = pos["quantity"]
            is_short_position = position_qty < 0

            if is_short_position:
                # SHORT POSITION: SELL decision means "close the short" → BUY to cover
                # Use absolute value for calculations
                abs_qty = abs(position_qty)
                shares_to_cover = int(abs_qty * decision.position_size_percent / 100)

                if shares_to_cover < 1:
                    logger.info(
                        "COVER skipped: less than 1 share",
                        symbol=decision.symbol,
                        position_qty=position_qty,
                        calculated_shares=shares_to_cover,
                    )
                    orders_skipped += 1
                    continue

                # Price from position (market_value / quantity gives positive price)
                estimated_price = abs(pos["market_value"]) / abs_qty
                estimated_cost = shares_to_cover * estimated_price

                logger.info(
                    "Converting SELL to BUY-to-cover for short position",
                    symbol=decision.symbol,
                    short_qty=position_qty,
                    shares_to_cover=shares_to_cover,
                    estimated_price=estimated_price,
                )

                cover_orders.append(
                    OptimizedOrder(
                        symbol=decision.symbol,
                        side="buy",  # BUY to cover
                        shares=shares_to_cover,
                        estimated_price=estimated_price,
                        estimated_cost=estimated_cost,
                        original_size_percent=decision.position_size_percent,
                        adjusted_size_percent=None,
                        priority=0,  # Will be set later (highest priority)
                        skip_reason=None,
                        is_cover=True,
                    )
                )
                notes_parts.append(
                    f"COVER: BUY {shares_to_cover} {decision.symbol} to close short position."
                )
            else:
                # LONG POSITION: Normal SELL
                shares_to_sell = int(
                    position_qty * decision.position_size_percent / 100
                )

                if shares_to_sell < 1:
                    logger.info(
                        "SELL skipped: less than 1 share",
                        symbol=decision.symbol,
                        calculated_shares=shares_to_sell,
                    )
                    orders_skipped += 1
                    continue

                # Estimate price from position
                estimated_price = (
                    pos["market_value"] / position_qty if position_qty > 0 else 0
                )
                estimated_proceeds = shares_to_sell * estimated_price
                total_sell_proceeds += estimated_proceeds

                sell_orders.append(
                    OptimizedOrder(
                        symbol=decision.symbol,
                        side="sell",
                        shares=shares_to_sell,
                        estimated_price=estimated_price,
                        estimated_cost=estimated_proceeds,
                        original_size_percent=decision.position_size_percent,
                        adjusted_size_percent=None,
                        priority=0,  # Will be set later
                        skip_reason=None,
                        is_cover=False,
                    )
                )

        # Set priorities: COVER orders first (risk reduction), then SELLs (liquidity)
        for cover_order in cover_orders:
            cover_order.priority = priority
            orders.append(cover_order)
            priority += 1

        for sell_order in sell_orders:
            sell_order.priority = priority
            orders.append(sell_order)
            priority += 1

        # Calculate available buying power after SELLs
        available_buying_power = buying_power + total_sell_proceeds

        if sell_orders and total_sell_proceeds > 0:
            notes_parts.append(
                f"SELLs will provide ${total_sell_proceeds:,.2f} in liquidity."
            )

        # Estimate total BUY cost (before scaling)
        buy_estimates = []
        for decision in buy_decisions:
            if not decision.position_size_percent:
                logger.warning(
                    "BUY skipped: no position_size_percent",
                    symbol=decision.symbol,
                )
                orders_skipped += 1
                continue

            # Calculate cost (% of buying power)
            estimated_cost = buying_power * decision.position_size_percent / 100

            # Get price estimate from position or use placeholder
            pos = positions_by_symbol.get(decision.symbol)
            if pos and pos["quantity"] > 0:
                estimated_price = pos["market_value"] / pos["quantity"]
            else:
                # No position, need to estimate price
                # For now, use a placeholder - actual price from market data
                # In production, we'd fetch current price from market service
                estimated_price = 100.0  # Placeholder, will be refined by execution

            shares_to_buy = (
                int(estimated_cost / estimated_price) if estimated_price > 0 else 0
            )

            buy_estimates.append(
                {
                    "decision": decision,
                    "estimated_price": estimated_price,
                    "original_cost": estimated_cost,
                    "original_shares": shares_to_buy,
                    "position_size_percent": decision.position_size_percent,  # Already validated not None
                }
            )
            total_buy_cost += estimated_cost

        # Apply scaling if total BUY cost exceeds available funds
        scaling_applied = False
        scaling_factor = None

        if total_buy_cost > available_buying_power and total_buy_cost > 0:
            scaling_factor = available_buying_power / total_buy_cost
            scaling_applied = True
            notes_parts.append(
                f"BUY orders scaled to {scaling_factor:.1%} due to limited buying power "
                f"(requested ${total_buy_cost:,.2f}, available ${available_buying_power:,.2f})."
            )

        # Build BUY orders (with scaling if needed)
        scaled_buy_cost = 0.0
        for est in buy_estimates:
            decision = est["decision"]
            estimated_price = est["estimated_price"]
            original_cost = est["original_cost"]
            position_size_percent: int = est[
                "position_size_percent"
            ]  # Already validated

            # Apply scaling
            if scaling_applied and scaling_factor:
                adjusted_cost = original_cost * scaling_factor
                adjusted_percent = int(position_size_percent * scaling_factor)
            else:
                adjusted_cost = original_cost
                adjusted_percent = None

            # Calculate shares
            shares_to_buy = (
                int(adjusted_cost / estimated_price) if estimated_price > 0 else 0
            )

            if shares_to_buy < 1:
                logger.info(
                    "BUY skipped: less than 1 share after scaling",
                    symbol=decision.symbol,
                    original_shares=est["original_shares"],
                    scaling_factor=scaling_factor,
                )
                orders_skipped += 1
                continue

            actual_cost = shares_to_buy * estimated_price
            scaled_buy_cost += actual_cost

            orders.append(
                OptimizedOrder(
                    symbol=decision.symbol,
                    side="buy",
                    shares=shares_to_buy,
                    estimated_price=estimated_price,
                    estimated_cost=actual_cost,
                    original_size_percent=position_size_percent,
                    adjusted_size_percent=adjusted_percent,
                    priority=priority,
                    skip_reason=None,
                    is_cover=False,
                )
            )
            priority += 1

        # Build final notes
        if not notes_parts:
            notes_parts.append(
                "Execution plan generated from Portfolio Agent decisions."
            )

        if orders_skipped > 0:
            notes_parts.append(
                f"{orders_skipped} orders skipped (< 1 share or missing data)."
            )

        logger.info(
            "Execution plan built",
            total_orders=len(orders),
            cover_orders=len([o for o in orders if o.is_cover]),
            sell_orders=len([o for o in orders if o.side == "sell"]),
            buy_orders=len([o for o in orders if o.side == "buy" and not o.is_cover]),
            total_sell_proceeds=total_sell_proceeds,
            total_buy_cost=scaled_buy_cost,
            available_buying_power=available_buying_power,
            scaling_applied=scaling_applied,
            scaling_factor=scaling_factor,
            orders_skipped=orders_skipped,
        )

        return OrderExecutionPlan(
            orders=orders,
            total_sell_proceeds=total_sell_proceeds,
            total_buy_cost=scaled_buy_cost,
            available_buying_power=available_buying_power,
            scaling_applied=scaling_applied,
            scaling_factor=scaling_factor,
            orders_skipped=orders_skipped,
            notes=" ".join(notes_parts),
        )

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
                    status="failed",
                    error_message=error_message,
                    created_at=datetime.utcnow(),
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
