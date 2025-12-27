"""
Helper utilities for Alpaca Trading Service.

Provides validation, conversion, and transformation utilities
shared across order and position operations.
"""

from alpaca.trading.enums import OrderSide, TimeInForce

from src.core.utils.date_utils import utcnow

from ...models.portfolio import PortfolioOrder, PortfolioPosition

# Order validation constants (paper trading - no artificial limits)
# Note: Alpaca paper trading has no share limits, only real-world liquidity constraints
MAX_ORDER_VALUE = 500000  # Maximum order value in USD (safety limit for paper trading)


def validate_order_quantity(quantity: float) -> None:
    """
    Validate order quantity is positive.

    Args:
        quantity: Number of shares

    Raises:
        ValueError: If quantity is not positive
    """
    if quantity <= 0:
        raise ValueError(f"Order quantity must be positive: {quantity}")


def validate_order_value(
    quantity: float,
    limit_price: float | None = None,
    stop_price: float | None = None,
) -> None:
    """
    Validate order value doesn't exceed maximum limit.

    Args:
        quantity: Number of shares
        limit_price: Limit price (if applicable)
        stop_price: Stop price (if applicable)

    Raises:
        ValueError: If order value exceeds MAX_ORDER_VALUE
    """
    estimated_price = limit_price or stop_price
    if estimated_price:
        order_value = quantity * estimated_price
        if order_value > MAX_ORDER_VALUE:
            raise ValueError(
                f"Order value exceeds maximum limit: ${order_value:,.2f} > ${MAX_ORDER_VALUE:,.2f}"
            )


def convert_side_to_alpaca(side: str) -> OrderSide:
    """
    Convert string side to Alpaca OrderSide enum.

    Args:
        side: "buy" or "sell"

    Returns:
        OrderSide enum value
    """
    return OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL


def convert_time_in_force_to_alpaca(time_in_force: str) -> TimeInForce:
    """
    Convert string time_in_force to Alpaca TimeInForce enum.

    Args:
        time_in_force: "day", "gtc", "ioc", or "fok"

    Returns:
        TimeInForce enum value (defaults to DAY if unknown)
    """
    tif_map = {
        "day": TimeInForce.DAY,
        "gtc": TimeInForce.GTC,
        "ioc": TimeInForce.IOC,
        "fok": TimeInForce.FOK,
    }
    return tif_map.get(time_in_force.lower(), TimeInForce.DAY)


def alpaca_order_to_portfolio_order(
    alpaca_order,
    chat_id: str = "",
    user_id: str = "",
    message_id: str | None = None,
) -> PortfolioOrder:
    """
    Convert Alpaca Order to PortfolioOrder model.

    Args:
        alpaca_order: Alpaca Order object
        chat_id: Chat where order was triggered (optional)
        user_id: Portfolio owner (optional)
        message_id: Message with order reasoning (optional)

    Returns:
        PortfolioOrder model
    """
    return PortfolioOrder(
        order_id=f"order_{utcnow().strftime('%Y%m%d%H%M%S%f')}",
        chat_id=chat_id,
        user_id=user_id,
        message_id=message_id,
        alpaca_order_id=str(alpaca_order.id),
        analysis_id=alpaca_order.client_order_id or "",
        symbol=alpaca_order.symbol,
        order_type=str(alpaca_order.type),
        side=str(alpaca_order.side),
        quantity=float(alpaca_order.qty),
        limit_price=(
            float(alpaca_order.limit_price) if alpaca_order.limit_price else None
        ),
        stop_price=float(alpaca_order.stop_price) if alpaca_order.stop_price else None,
        time_in_force=str(alpaca_order.time_in_force),
        status=str(alpaca_order.status),
        filled_qty=float(alpaca_order.filled_qty or 0),
        filled_avg_price=(
            float(alpaca_order.filled_avg_price)
            if alpaca_order.filled_avg_price
            else None
        ),
        created_at=alpaca_order.submitted_at,
        filled_at=alpaca_order.filled_at,
        metadata=(
            {"extended_hours": alpaca_order.extended_hours}
            if hasattr(alpaca_order, "extended_hours")
            else {}
        ),
    )


def alpaca_position_to_portfolio_position(
    alpaca_position, user_id: str
) -> PortfolioPosition:
    """
    Convert Alpaca Position to PortfolioPosition model.

    Args:
        alpaca_position: Alpaca Position object
        user_id: Portfolio owner

    Returns:
        PortfolioPosition model
    """
    return PortfolioPosition(
        user_id=user_id,
        symbol=alpaca_position.symbol,
        quantity=float(alpaca_position.qty),
        avg_entry_price=float(alpaca_position.avg_entry_price),
        current_price=float(alpaca_position.current_price),
        market_value=float(alpaca_position.market_value),
        cost_basis=float(alpaca_position.cost_basis),
        unrealized_pl=float(alpaca_position.unrealized_pl),
        unrealized_pl_pct=float(alpaca_position.unrealized_plpc) * 100,  # Convert to %
        first_acquired=utcnow(),  # Alpaca doesn't provide this
    )
