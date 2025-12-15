"""
Portfolio orders endpoint.

Provides:
- GET /orders: Fetch order history from Alpaca
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request

from ...services.alpaca_trading_service import AlpacaTradingService
from ..dependencies.auth import get_current_user_id
from ..dependencies.portfolio_deps import get_alpaca_trading_service
from ..dependencies.rate_limit import limiter

logger = structlog.get_logger()

router = APIRouter()


@router.get("/orders")
@limiter.limit("10/minute")  # Alpaca API call - restrictive limit
async def get_portfolio_orders(
    request: Request,
    limit: int = 50,
    status: str | None = None,  # "open", "closed", "all"
    user_id: str = Depends(get_current_user_id),  # JWT authentication required
    trading_service: AlpacaTradingService = Depends(get_alpaca_trading_service),
) -> dict:
    """
    Get portfolio orders from Alpaca.

    **Authentication**: Requires Bearer token in Authorization header.

    Shows actual BUY/SELL orders placed by the portfolio analysis agent.
    All authenticated users see the same orders (shared paper trading account).

    Args:
        limit: Maximum number of orders to return (default: 50)
        status: Filter by status - "open", "closed", or "all" (default: "all")
        user_id: Authenticated user ID (auto-injected via JWT)

    Returns:
        List of orders with execution details
    """
    try:
        # Get orders from Alpaca
        from alpaca.trading.enums import QueryOrderStatus
        from alpaca.trading.requests import GetOrdersRequest

        # Map status parameter to Alpaca enum
        status_filter = None
        if status == "open":
            status_filter = QueryOrderStatus.OPEN
        elif status == "closed":
            status_filter = QueryOrderStatus.CLOSED
        else:
            status_filter = QueryOrderStatus.ALL

        request = GetOrdersRequest(
            status=status_filter,
            limit=limit,
        )

        alpaca_orders = trading_service.client.get_orders(filter=request)

        # Transform to our format
        orders = []
        for alpaca_order in alpaca_orders:
            # Clean enum strings (remove "orderside." prefix, etc.)
            side = str(alpaca_order.side).lower().replace("orderside.", "")
            order_type = str(alpaca_order.type).lower().replace("ordertype.", "")
            status = str(alpaca_order.status).lower().replace("orderstatus.", "")

            orders.append(
                {
                    "order_id": str(alpaca_order.id),
                    "symbol": alpaca_order.symbol,
                    "side": side,
                    "quantity": float(alpaca_order.qty),
                    "order_type": order_type,
                    "status": status,
                    "filled_qty": float(alpaca_order.filled_qty or 0),
                    "filled_avg_price": (
                        float(alpaca_order.filled_avg_price)
                        if alpaca_order.filled_avg_price
                        else None
                    ),
                    "submitted_at": (
                        alpaca_order.submitted_at.isoformat()
                        if alpaca_order.submitted_at
                        else None
                    ),
                    "filled_at": (
                        alpaca_order.filled_at.isoformat()
                        if alpaca_order.filled_at
                        else None
                    ),
                    "analysis_id": alpaca_order.client_order_id,  # Our analysis ID
                }
            )

        logger.info(
            "Portfolio orders retrieved",
            order_count=len(orders),
            status_filter=status,
        )

        return {
            "orders": orders,
            "total": len(orders),
        }

    except Exception as e:
        logger.error(
            "Failed to retrieve portfolio orders",
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve order history. Please try again later.",
        ) from e
