"""
Order operations for Alpaca Trading Service.

Handles order placement, retrieval, and history with full
support for market, limit, stop, and stop-limit orders.
"""

import structlog
from alpaca.trading.enums import QueryOrderStatus
from alpaca.trading.requests import (
    GetOrdersRequest,
    LimitOrderRequest,
    MarketOrderRequest,
    StopLimitOrderRequest,
    StopOrderRequest,
)

from ...models.portfolio import PortfolioOrder
from .base import AlpacaTradingServiceBase
from .helpers import (
    alpaca_order_to_portfolio_order,
    convert_side_to_alpaca,
    convert_time_in_force_to_alpaca,
    validate_order_quantity,
    validate_order_value,
)

logger = structlog.get_logger()


class OrderOperations(AlpacaTradingServiceBase):
    """Order placement and retrieval operations."""

    async def place_order(
        self,
        symbol: str,
        quantity: float,
        side: str,  # "buy" or "sell"
        order_type: str = "market",
        limit_price: float | None = None,
        stop_price: float | None = None,
        time_in_force: str = "day",
        analysis_id: str = "",
        chat_id: str = "",
        user_id: str = "",
        message_id: str | None = None,
    ) -> PortfolioOrder:
        """
        Place order with flexible order type and parameters.

        Unified order placement supporting all order types:
        - MARKET: Execute immediately at current market price
        - LIMIT: Execute at specified limit_price or better
        - STOP: Trigger market order when stop_price is reached
        - STOP_LIMIT: Trigger limit order when stop_price is reached

        Args:
            symbol: Stock symbol (e.g., "AAPL")
            quantity: Number of shares
            side: "buy" or "sell"
            order_type: "market", "limit", "stop", or "stop_limit"
            limit_price: Limit price (required for limit/stop_limit orders)
            stop_price: Stop price (required for stop/stop_limit orders)
            time_in_force: "day", "gtc", "ioc", or "fok"
            analysis_id: Analysis ID for audit trail (becomes client_order_id)
            chat_id: Chat where order was triggered
            user_id: Portfolio owner
            message_id: Message with order reasoning

        Returns:
            PortfolioOrder model with Alpaca order details

        Examples:
            >>> # Market order (immediate execution)
            >>> order = await service.place_order(
            ...     symbol="AAPL", quantity=10, side="buy", order_type="market"
            ... )

            >>> # Limit buy at $150
            >>> order = await service.place_order(
            ...     symbol="AAPL", quantity=10, side="buy",
            ...     order_type="limit", limit_price=150.0
            ... )

            >>> # Stop-loss at $140 (GTC)
            >>> order = await service.place_order(
            ...     symbol="AAPL", quantity=10, side="sell",
            ...     order_type="stop", stop_price=140.0, time_in_force="gtc"
            ... )

            >>> # Stop-limit: trigger at $140, limit at $145
            >>> order = await service.place_order(
            ...     symbol="AAPL", quantity=10, side="sell",
            ...     order_type="stop_limit",
            ...     stop_price=140.0, limit_price=145.0, time_in_force="gtc"
            ... )
        """
        # Validate order size
        validate_order_quantity(quantity)

        # Validate order value (if price is known) - safety limit for paper trading
        validate_order_value(quantity, limit_price, stop_price)

        logger.info(
            "Placing order",
            symbol=symbol,
            quantity=quantity,
            side=side,
            order_type=order_type,
            limit_price=limit_price,
            stop_price=stop_price,
            time_in_force=time_in_force,
            analysis_id=analysis_id,
        )

        try:
            # Convert side to Alpaca enum
            order_side = convert_side_to_alpaca(side)

            # Convert time_in_force to Alpaca enum
            tif = convert_time_in_force_to_alpaca(time_in_force)

            # Route to appropriate Alpaca order type
            if order_type.lower() == "market":
                request = MarketOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=order_side,
                    time_in_force=tif,
                    client_order_id=analysis_id or None,
                )

            elif order_type.lower() == "limit":
                if limit_price is None:
                    raise ValueError("limit_price required for limit orders")
                request = LimitOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=order_side,
                    limit_price=limit_price,
                    time_in_force=tif,
                    client_order_id=analysis_id or None,
                )

            elif order_type.lower() == "stop":
                if stop_price is None:
                    raise ValueError("stop_price required for stop orders")
                request = StopOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=order_side,
                    stop_price=stop_price,
                    time_in_force=tif,
                    client_order_id=analysis_id or None,
                )

            elif order_type.lower() == "stop_limit":
                if stop_price is None or limit_price is None:
                    raise ValueError(
                        "Both stop_price and limit_price required for stop_limit orders"
                    )
                request = StopLimitOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=order_side,
                    stop_price=stop_price,
                    limit_price=limit_price,
                    time_in_force=tif,
                    client_order_id=analysis_id or None,
                )

            else:
                raise ValueError(
                    f"Unsupported order_type: {order_type}. "
                    f"Must be one of: market, limit, stop, stop_limit"
                )

            # Submit order to Alpaca
            alpaca_order = self.client.submit_order(request)

            # Convert to our PortfolioOrder model
            order = alpaca_order_to_portfolio_order(
                alpaca_order,
                chat_id=chat_id,
                user_id=user_id,
                message_id=message_id,
            )

            logger.info(
                "Order placed successfully",
                order_id=order.order_id,
                alpaca_order_id=order.alpaca_order_id,
                order_type=order_type,
                status=order.status,
            )

            return order

        except Exception as e:
            logger.error(
                "Failed to place order",
                symbol=symbol,
                order_type=order_type,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

    async def place_market_order(
        self,
        symbol: str,
        quantity: float,
        side: str,  # "buy" or "sell"
        analysis_id: str,  # For audit trail
        chat_id: str,
        user_id: str,
        message_id: str | None = None,
    ) -> PortfolioOrder:
        """
        Place market order with audit trail.

        DEPRECATED: Use place_order() instead for full order type support.
        This method is kept for backward compatibility.

        Args:
            symbol: Stock symbol (e.g., "AAPL")
            quantity: Number of shares
            side: "buy" or "sell"
            analysis_id: Analysis ID for audit trail (becomes client_order_id)
            chat_id: Chat where order was triggered
            user_id: Portfolio owner
            message_id: Message with order reasoning

        Returns:
            PortfolioOrder model with Alpaca order details
        """
        # Wrapper for backward compatibility - delegates to place_order()
        return await self.place_order(
            symbol=symbol,
            quantity=quantity,
            side=side,
            order_type="market",
            analysis_id=analysis_id,
            chat_id=chat_id,
            user_id=user_id,
            message_id=message_id,
        )

    async def get_order_by_analysis_id(self, analysis_id: str) -> PortfolioOrder | None:
        """
        Retrieve order by analysis ID (client_order_id).

        AUDIT TRAIL: Proves we can link order back to analysis.

        Args:
            analysis_id: Analysis ID used as client_order_id

        Returns:
            PortfolioOrder if found, None otherwise

        Example:
            >>> order = await service.get_order_by_analysis_id(
            ...     "analysis-20251101-AAPL-bullish"
            ... )
            >>> print(order.filled_avg_price)
            271.17
        """
        try:
            # Get order by client_order_id
            alpaca_order = self.client.get_order_by_client_id(analysis_id)

            if not alpaca_order:
                return None

            # Convert to our PortfolioOrder model
            order = alpaca_order_to_portfolio_order(alpaca_order)

            logger.info(
                "Order retrieved by analysis_id",
                analysis_id=analysis_id,
                alpaca_order_id=order.alpaca_order_id,
                status=order.status,
            )

            return order

        except Exception as e:
            logger.warning(
                "Order not found by analysis_id",
                analysis_id=analysis_id,
                error=str(e),
            )
            return None

    async def get_order_history(
        self,
        user_id: str,
        limit: int = 100,
    ) -> list[PortfolioOrder]:
        """
        Get order history for user.

        Args:
            user_id: Portfolio owner
            limit: Maximum number of orders to return

        Returns:
            List of PortfolioOrder models (most recent first)

        Example:
            >>> orders = await service.get_order_history("user_123", limit=10)
            >>> for order in orders:
            ...     print(f"{order.side} {order.quantity} {order.symbol} @ ${order.filled_avg_price}")
            'buy 10.0 AAPL @ $271.17'
        """
        try:
            request = GetOrdersRequest(
                status=QueryOrderStatus.CLOSED,
                limit=limit,
            )

            alpaca_orders = self.client.get_orders(request)

            orders = [
                alpaca_order_to_portfolio_order(alpaca_order, user_id=user_id)
                for alpaca_order in alpaca_orders
            ]

            logger.info(
                "Order history retrieved",
                user_id=user_id,
                order_count=len(orders),
            )

            return orders

        except Exception as e:
            logger.error(
                "Failed to get order history",
                user_id=user_id,
                error=str(e),
            )
            raise
