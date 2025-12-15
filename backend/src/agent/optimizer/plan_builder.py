"""
Order Execution Plan Builder.

Converts TradingDecisions into an optimized OrderExecutionPlan with:
1. SELLs first (to free up buying power / gain liquidity)
2. Calculate available funds = current_buying_power + estimated_sell_proceeds
3. Scale down BUYs proportionally if insufficient funds
"""

from typing import Any

import structlog

from ...models.trading_decision import (
    OptimizedOrder,
    OrderExecutionPlan,
    SymbolAnalysisResult,
    TradingAction,
    TradingDecision,
)
from .order_helpers import create_cover_order, create_sell_order

logger = structlog.get_logger()


class PlanBuilder:
    """
    Builds OrderExecutionPlan from TradingDecisions.

    Handles:
    - Separating SELLs and BUYs
    - Short position handling (SELL → BUY-to-cover)
    - Buy order scaling for insufficient funds
    """

    @staticmethod
    async def build_execution_plan(
        analysis_results: list[SymbolAnalysisResult],
        portfolio_context: dict[str, Any],
        user_id: str,
        trading_decisions: list[TradingDecision] | None = None,
    ) -> OrderExecutionPlan | None:
        """
        Convert trading decisions into an optimized execution plan.

        Takes pre-made TradingDecisions and builds an OrderExecutionPlan:
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

        # Process SELL orders (includes handling short positions)
        sell_result = PlanBuilder._process_sell_orders(
            sell_decisions, positions_by_symbol
        )

        orders = sell_result["orders"]
        total_sell_proceeds = sell_result["total_sell_proceeds"]
        orders_skipped = sell_result["orders_skipped"]
        priority = sell_result["next_priority"]
        notes_parts = sell_result["notes_parts"]

        # Calculate available buying power after SELLs
        available_buying_power = buying_power + total_sell_proceeds

        if sell_result["sell_orders"] and total_sell_proceeds > 0:
            notes_parts.append(
                f"SELLs will provide ${total_sell_proceeds:,.2f} in liquidity."
            )

        # Process BUY orders (with scaling if needed)
        buy_result = PlanBuilder._process_buy_orders(
            buy_decisions,
            positions_by_symbol,
            buying_power,
            available_buying_power,
            priority,
        )

        orders.extend(buy_result["orders"])
        orders_skipped += buy_result["orders_skipped"]
        notes_parts.extend(buy_result["notes_parts"])
        total_buy_cost = buy_result["total_buy_cost"]
        scaling_applied = buy_result["scaling_applied"]
        scaling_factor = buy_result["scaling_factor"]

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
            total_buy_cost=total_buy_cost,
            available_buying_power=available_buying_power,
            scaling_applied=scaling_applied,
            scaling_factor=scaling_factor,
            orders_skipped=orders_skipped,
        )

        return OrderExecutionPlan(
            orders=orders,
            total_sell_proceeds=total_sell_proceeds,
            total_buy_cost=total_buy_cost,
            available_buying_power=available_buying_power,
            scaling_applied=scaling_applied,
            scaling_factor=scaling_factor,
            orders_skipped=orders_skipped,
            notes=" ".join(notes_parts),
        )

    @staticmethod
    def _process_sell_orders(
        sell_decisions: list[TradingDecision],
        positions_by_symbol: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Process SELL orders, including short position handling.

        For short positions, converts SELL decisions to BUY-to-cover orders.

        Args:
            sell_decisions: List of SELL decisions
            positions_by_symbol: Lookup dict of positions by symbol

        Returns:
            Dict with processed orders, proceeds, and metadata
        """
        orders: list[OptimizedOrder] = []
        cover_orders: list[OptimizedOrder] = []
        sell_orders: list[OptimizedOrder] = []
        total_sell_proceeds = 0.0
        orders_skipped = 0
        notes_parts = []
        priority = 1

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
                result = create_cover_order(decision, pos, position_qty)
                if result["order"]:
                    cover_orders.append(result["order"])
                    notes_parts.extend(result["notes"])
                else:
                    orders_skipped += 1
            else:
                # LONG POSITION: Normal SELL
                result = create_sell_order(decision, pos, position_qty)
                if result["order"]:
                    sell_orders.append(result["order"])
                    total_sell_proceeds += result["proceeds"]
                else:
                    orders_skipped += 1

        # Set priorities: COVER orders first (risk reduction), then SELLs (liquidity)
        for cover_order in cover_orders:
            cover_order.priority = priority
            orders.append(cover_order)
            priority += 1

        for sell_order in sell_orders:
            sell_order.priority = priority
            orders.append(sell_order)
            priority += 1

        return {
            "orders": orders,
            "cover_orders": cover_orders,
            "sell_orders": sell_orders,
            "total_sell_proceeds": total_sell_proceeds,
            "orders_skipped": orders_skipped,
            "notes_parts": notes_parts,
            "next_priority": priority,
        }

    @staticmethod
    def _process_buy_orders(
        buy_decisions: list[TradingDecision],
        positions_by_symbol: dict[str, Any],
        buying_power: float,
        available_buying_power: float,
        start_priority: int,
    ) -> dict[str, Any]:
        """
        Process BUY orders with scaling if needed.

        Args:
            buy_decisions: List of BUY decisions
            positions_by_symbol: Lookup dict of positions by symbol
            buying_power: Current buying power (before SELLs)
            available_buying_power: Available buying power (after SELLs)
            start_priority: Starting priority for BUY orders

        Returns:
            Dict with processed orders, costs, and scaling info
        """
        orders: list[OptimizedOrder] = []
        orders_skipped = 0
        notes_parts = []
        priority = start_priority

        # Estimate total BUY cost (before scaling)
        buy_estimates = []
        total_buy_cost_estimate = 0.0

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
                    "position_size_percent": decision.position_size_percent,
                }
            )
            total_buy_cost_estimate += estimated_cost

        # Apply scaling if total BUY cost exceeds available funds
        scaling_applied = False
        scaling_factor = None

        if (
            total_buy_cost_estimate > available_buying_power
            and total_buy_cost_estimate > 0
        ):
            scaling_factor = available_buying_power / total_buy_cost_estimate
            scaling_applied = True
            notes_parts.append(
                f"BUY orders scaled to {scaling_factor:.1%} due to limited buying power "
                f"(requested ${total_buy_cost_estimate:,.2f}, available ${available_buying_power:,.2f})."
            )

        # Build BUY orders (with scaling if needed)
        total_buy_cost = 0.0
        for est in buy_estimates:
            decision = est["decision"]
            estimated_price = est["estimated_price"]
            original_cost = est["original_cost"]
            position_size_percent: int = est["position_size_percent"]

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
            total_buy_cost += actual_cost

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

        return {
            "orders": orders,
            "total_buy_cost": total_buy_cost,
            "orders_skipped": orders_skipped,
            "notes_parts": notes_parts,
            "scaling_applied": scaling_applied,
            "scaling_factor": scaling_factor,
        }
