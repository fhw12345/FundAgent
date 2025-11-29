"""
Order Optimization Module - Aggregation Hook for Portfolio Analysis.

Handles Phase 2 (order aggregation) and Phase 3 (order execution) of the
two-phase portfolio analysis workflow.
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
    OrderExecutionPlan,
    SymbolAnalysisResult,
    TradingAction,
)

logger = structlog.get_logger()


class OrderOptimizer:
    """
    Aggregation hook for optimizing and executing trading orders.

    Responsibilities:
    1. Review all TradingDecisions from Phase 1 analysis
    2. Invoke agent to optimize order sequence and sizes
    3. Execute orders (SELLs first, then scaled BUYs)
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
            react_agent: ReAct agent with ainvoke_structured() method
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
    ) -> OrderExecutionPlan | None:
        """
        Aggregation Hook: Invoke agent to optimize all trading decisions.

        This method is called AFTER all individual symbol analyses complete.
        It reviews all decisions holistically and produces an optimized execution plan.

        Key responsibilities:
        1. Order SELLs first (to free up buying power)
        2. Calculate available funds = current_buying_power + estimated_sell_proceeds
        3. Scale down BUYs proportionally if insufficient funds (Option A)
        4. Return OrderExecutionPlan for execution

        Args:
            analysis_results: List of SymbolAnalysisResult from Phase 1
            portfolio_context: Portfolio state (equity, buying_power, positions)
            user_id: User ID for the portfolio

        Returns:
            OrderExecutionPlan with optimized order sequence, or None if failed
        """
        if not analysis_results:
            logger.info("No analysis results to optimize")
            return None

        # Filter to actionable decisions only:
        # 1. Exclude HOLD (no action)
        # 2. Exclude market_mover (informational only, no auto-trading)
        actionable_decisions = [
            r
            for r in analysis_results
            if r.decision.decision != TradingAction.HOLD
            and r.analysis_type != "market_mover"
        ]

        market_mover_count = sum(
            1 for r in analysis_results if r.analysis_type == "market_mover"
        )
        if market_mover_count:
            logger.info(
                "Market movers excluded from execution (informational only)",
                count=market_mover_count,
            )

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

        # Build context for aggregation prompt
        total_equity = portfolio_context.get("total_equity", 0)
        buying_power = portfolio_context.get("buying_power", 0)
        cash = portfolio_context.get("cash", 0)
        positions = portfolio_context.get("positions", [])

        # Build positions table
        positions_table = "| Symbol | Shares | Market Value | P/L % |\n|--------|--------|--------------|-------|\n"
        for pos in positions:
            positions_table += f"| {pos['symbol']} | {pos['quantity']} | ${pos['market_value']:,.2f} | {pos['unrealized_pl_percent']:.2f}% |\n"
        if not positions:
            positions_table += "| (No positions) | - | - | - |\n"

        # Build decisions table
        decisions_table = "| Symbol | Decision | Size % | Confidence | Reasoning |\n|--------|----------|--------|------------|----------|\n"
        for r in actionable_decisions:
            d = r.decision
            decisions_table += f"| {d.symbol} | {d.decision.value} | {d.position_size_percent or 'N/A'}% | {d.confidence}/10 | {d.reasoning_summary[:50]}... |\n"

        # Estimate sell proceeds for SELLs
        sell_estimates = []
        for r in actionable_decisions:
            if r.decision.decision == TradingAction.SELL:
                # Find position for this symbol
                pos = next(
                    (p for p in positions if p["symbol"] == r.decision.symbol), None
                )
                if pos and r.decision.position_size_percent:
                    shares_to_sell = int(
                        pos["quantity"] * r.decision.position_size_percent / 100
                    )
                    estimated_price = (
                        pos["market_value"] / pos["quantity"]
                        if pos["quantity"] > 0
                        else 0
                    )
                    estimated_proceeds = shares_to_sell * estimated_price
                    sell_estimates.append(
                        {
                            "symbol": r.decision.symbol,
                            "shares": shares_to_sell,
                            "estimated_price": estimated_price,
                            "estimated_proceeds": estimated_proceeds,
                        }
                    )

        sell_proceeds_text = ""
        total_sell_proceeds = 0
        for est in sell_estimates:
            sell_proceeds_text += f"- {est['symbol']}: Sell {est['shares']} shares @ ~${est['estimated_price']:.2f} = ~${est['estimated_proceeds']:,.2f}\n"
            total_sell_proceeds += est["estimated_proceeds"]
        if not sell_estimates:
            sell_proceeds_text = "- No SELL orders\n"

        # Build aggregation prompt
        aggregation_prompt = f"""# Order Optimization Task

You are optimizing a portfolio's trading orders. Review all proposed trades and create an execution plan.

## Current Portfolio State
- **Total Equity:** ${total_equity:,.2f}
- **Current Buying Power:** ${buying_power:,.2f}
- **Cash:** ${cash:,.2f}

## Current Positions
{positions_table}

## Proposed Trades from Analysis
{decisions_table}

## Estimated SELL Proceeds
{sell_proceeds_text}
**Total Estimated SELL Proceeds:** ${total_sell_proceeds:,.2f}

## Available Funds Calculation
Available Funds = Current Buying Power (${buying_power:,.2f}) + SELL Proceeds (${total_sell_proceeds:,.2f}) = **${buying_power + total_sell_proceeds:,.2f}**

## Your Task

1. **Order SELLs first** - They free up buying power
2. **Calculate share quantities** for each order:
   - For SELL: shares = holding_quantity * (position_size_percent / 100)
   - For BUY: shares = (buying_power * position_size_percent / 100) / stock_price
3. **Check if total BUY cost exceeds available funds**
   - If yes: Scale ALL BUY orders proportionally (Option A)
   - scaling_factor = available_funds / total_buy_cost
   - Skip any order that becomes < 1 share after scaling
4. **Assign priorities**: SELLs get priority 1-N, BUYs get priority N+1 onwards

## Important Notes
- Use realistic stock prices from the analysis context
- Round shares DOWN to whole numbers (no fractional shares)
- Minimum 1 share per order, skip if less

Output the final OrderExecutionPlan.
"""

        logger.info(
            "Invoking agent for order optimization",
            actionable_decisions=len(actionable_decisions),
            total_equity=total_equity,
            buying_power=buying_power,
            estimated_sell_proceeds=total_sell_proceeds,
        )

        try:
            # Invoke agent with structured output for OrderExecutionPlan
            execution_plan = await self.react_agent.ainvoke_structured(
                prompt=aggregation_prompt,
                schema=OrderExecutionPlan,
                context=None,  # Context is embedded in prompt
            )

            logger.info(
                "Order optimization completed",
                orders_count=len(execution_plan.orders),
                total_sell_proceeds=execution_plan.total_sell_proceeds,
                total_buy_cost=execution_plan.total_buy_cost,
                scaling_applied=execution_plan.scaling_applied,
                scaling_factor=execution_plan.scaling_factor,
                orders_skipped=execution_plan.orders_skipped,
            )

            return execution_plan

        except Exception as e:
            logger.error(
                "Order optimization failed",
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            return None

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
                    analysis_id=analysis.analysis_id if analysis else f"failed_{order.symbol}",
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
