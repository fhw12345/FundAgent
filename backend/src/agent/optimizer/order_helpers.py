"""
Helper functions for creating individual orders.

Provides utilities for:
- Creating SELL orders from long positions
- Creating BUY-to-cover orders from short positions
"""

from typing import Any

import structlog

from ...models.trading_decision import (
    OptimizedOrder,
    TradingDecision,
)

logger = structlog.get_logger()


def create_cover_order(
    decision: TradingDecision,
    pos: dict[str, Any],
    position_qty: int,
) -> dict[str, Any]:
    """
    Create BUY-to-cover order for short position.

    Args:
        decision: Trading decision
        pos: Position data
        position_qty: Position quantity (negative for short)

    Returns:
        Dict with order and notes, or None if skipped
    """
    # Use absolute value for calculations
    abs_qty = abs(position_qty)
    shares_to_cover = int(abs_qty * (decision.position_size_percent or 0) / 100)

    if shares_to_cover < 1:
        logger.info(
            "COVER skipped: less than 1 share",
            symbol=decision.symbol,
            position_qty=position_qty,
            calculated_shares=shares_to_cover,
        )
        return {"order": None, "notes": []}

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

    order = OptimizedOrder(
        symbol=decision.symbol,
        side="buy",  # BUY to cover
        shares=shares_to_cover,
        estimated_price=estimated_price,
        estimated_cost=estimated_cost,
        original_size_percent=decision.position_size_percent or 0,
        adjusted_size_percent=None,
        priority=1,  # Placeholder - will be reassigned
        skip_reason=None,
        is_cover=True,
    )

    notes = [f"COVER: BUY {shares_to_cover} {decision.symbol} to close short position."]

    return {"order": order, "notes": notes}


def create_sell_order(
    decision: TradingDecision,
    pos: dict[str, Any],
    position_qty: int,
) -> dict[str, Any]:
    """
    Create normal SELL order for long position.

    Args:
        decision: Trading decision
        pos: Position data
        position_qty: Position quantity (positive for long)

    Returns:
        Dict with order and proceeds, or None if skipped
    """
    shares_to_sell = int(position_qty * (decision.position_size_percent or 0) / 100)

    if shares_to_sell < 1:
        logger.info(
            "SELL skipped: less than 1 share",
            symbol=decision.symbol,
            calculated_shares=shares_to_sell,
        )
        return {"order": None, "proceeds": 0.0}

    # Estimate price from position
    estimated_price = pos["market_value"] / position_qty if position_qty > 0 else 0
    estimated_proceeds = shares_to_sell * estimated_price

    order = OptimizedOrder(
        symbol=decision.symbol,
        side="sell",
        shares=shares_to_sell,
        estimated_price=estimated_price,
        estimated_cost=estimated_proceeds,
        original_size_percent=decision.position_size_percent or 0,
        adjusted_size_percent=None,
        priority=1,  # Placeholder - will be reassigned
        skip_reason=None,
        is_cover=False,
    )

    return {"order": order, "proceeds": estimated_proceeds}
