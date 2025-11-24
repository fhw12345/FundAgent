"""
Trading Agent Tools for Order Placement.

Provides MCP tools for placing stock orders with advanced parameters:
- Order types: market, limit, stop, stop_limit
- Time in force: day, gtc, ioc, fok
- Risk management: stop-loss, take-profit strategies
"""

import structlog
from langchain_core.tools import tool

from ...services.alpaca_trading_service import AlpacaTradingService

logger = structlog.get_logger()


def create_trading_tools(trading_service: AlpacaTradingService) -> list:
    """
    Create trading agent tools with service dependency injection.

    Args:
        trading_service: Initialized AlpacaTradingService instance

    Returns:
        List of trading tools for agent access
    """

    @tool
    async def place_stock_order(
        symbol: str,
        quantity: int,
        side: str,
        order_type: str = "market",
        limit_price: float | None = None,
        stop_price: float | None = None,
        time_in_force: str = "day",
        reasoning: str = "",
    ) -> str:
        """
        Place stock order with advanced parameters for risk management.

        ORDER TYPES:
        - "market": Execute immediately at current market price
        - "limit": Execute at specified limit_price or better
        - "stop": Trigger market order when stop_price is reached (for stop-loss)
        - "stop_limit": Trigger limit order when stop_price is reached

        TIME IN FORCE:
        - "day": Valid until end of trading day (default)
        - "gtc": Good Till Cancelled (persists across days)
        - "ioc": Immediate or Cancel (fill immediately or cancel)
        - "fok": Fill or Kill (fill entirely or cancel)

        RISK MANAGEMENT EXAMPLES:
        1. Buy with immediate stop-loss protection:
           - place_stock_order("AAPL", 10, "buy", "market")
           - place_stock_order("AAPL", 10, "sell", "stop", stop_price=142.50, time_in_force="gtc")

        2. Limit buy with take-profit:
           - place_stock_order("AAPL", 10, "buy", "limit", limit_price=145.0, time_in_force="gtc")
           - place_stock_order("AAPL", 10, "sell", "limit", limit_price=160.0, time_in_force="gtc")

        3. Stop-limit sell (controlled exit):
           - place_stock_order("AAPL", 10, "sell", "stop_limit",
                              stop_price=140.0, limit_price=145.0, time_in_force="gtc")

        Args:
            symbol: Stock ticker (e.g., "AAPL", "MSFT", "TSLA")
            quantity: Number of shares (must be positive integer)
            side: "buy" or "sell"
            order_type: "market", "limit", "stop", or "stop_limit"
            limit_price: Limit price (required for limit/stop_limit orders)
            stop_price: Stop price (required for stop/stop_limit orders)
            time_in_force: "day", "gtc", "ioc", or "fok"
            reasoning: Explanation for this order (for audit trail)

        Returns:
            Order confirmation with order ID, status, and next steps

        Examples:
            >>> # Market buy (immediate execution)
            >>> place_stock_order("AAPL", 10, "buy", "market",
            ...                  reasoning="Bullish momentum on earnings beat")

            >>> # Stop-loss at 5% below current price
            >>> place_stock_order("AAPL", 10, "sell", "stop", stop_price=142.50,
            ...                  time_in_force="gtc",
            ...                  reasoning="Risk management: 5% stop-loss")

            >>> # Limit buy at target entry
            >>> place_stock_order("TSLA", 5, "buy", "limit", limit_price=180.0,
            ...                  time_in_force="gtc",
            ...                  reasoning="Entry at support level")
        """
        try:
            # Validate inputs
            if side.lower() not in ["buy", "sell"]:
                return f"❌ Invalid side: {side}. Must be 'buy' or 'sell'"

            if quantity <= 0:
                return f"❌ Invalid quantity: {quantity}. Must be positive integer"

            order_type_lower = order_type.lower()
            if order_type_lower not in ["market", "limit", "stop", "stop_limit"]:
                return (
                    f"❌ Invalid order_type: {order_type}. "
                    f"Must be one of: market, limit, stop, stop_limit"
                )

            # Validate required parameters for each order type
            if order_type_lower in ["limit", "stop_limit"] and limit_price is None:
                return f"❌ limit_price required for {order_type} orders"

            if order_type_lower in ["stop", "stop_limit"] and stop_price is None:
                return f"❌ stop_price required for {order_type} orders"

            # Generate analysis ID for audit trail
            from datetime import datetime

            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            analysis_id = f"{symbol}_{side}_{order_type}_{timestamp}"

            # Place order
            order = await trading_service.place_order(
                symbol=symbol.upper(),
                quantity=float(quantity),
                side=side.lower(),
                order_type=order_type_lower,
                limit_price=limit_price,
                stop_price=stop_price,
                time_in_force=time_in_force.lower(),
                analysis_id=analysis_id,
                chat_id="",  # Will be populated by agent
                user_id="portfolio_agent",
                message_id=None,
            )

            # Format confirmation message
            order_details = [
                f"**{side.upper()} {quantity} {symbol}**",
                f"Order Type: {order_type.upper()}",
                f"Time in Force: {time_in_force.upper()}",
            ]

            if limit_price:
                order_details.append(f"Limit Price: ${limit_price:.2f}")

            if stop_price:
                order_details.append(f"Stop Price: ${stop_price:.2f}")

            order_details.extend(
                [
                    f"Status: {order.status.upper()}",
                    f"Order ID: {order.alpaca_order_id}",
                    f"Analysis ID: {analysis_id}",
                ]
            )

            # Add reasoning if provided
            if reasoning:
                order_details.append(f"Reasoning: {reasoning}")

            # Add next steps based on order type
            if order_type_lower == "market":
                next_steps = "✅ Market order submitted - should fill immediately during market hours"
            elif order_type_lower == "limit":
                next_steps = (
                    f"⏳ Limit order queued - will execute when price reaches "
                    f"${limit_price:.2f} or better ({time_in_force.upper()})"
                )
            elif order_type_lower == "stop":
                next_steps = (
                    f"⏳ Stop-loss order active - will trigger market order "
                    f"if price reaches ${stop_price:.2f} ({time_in_force.upper()})"
                )
            elif order_type_lower == "stop_limit":
                next_steps = (
                    f"⏳ Stop-limit order active - will trigger limit order at "
                    f"${limit_price:.2f} when price reaches ${stop_price:.2f} ({time_in_force.upper()})"
                )

            result = "\n".join(order_details) + f"\n\n{next_steps}"

            logger.info(
                "Order placed via tool",
                symbol=symbol,
                quantity=quantity,
                side=side,
                order_type=order_type,
                order_id=order.alpaca_order_id,
                analysis_id=analysis_id,
            )

            return result

        except ValueError as e:
            error_msg = f"❌ Order validation failed: {str(e)}"
            logger.warning("Order tool validation error", error=str(e))
            return error_msg

        except Exception as e:
            error_msg = f"❌ Order placement failed: {str(e)}"
            logger.error(
                "Order tool execution error",
                symbol=symbol,
                error=str(e),
                error_type=type(e).__name__,
            )
            return error_msg

    return [place_stock_order]
