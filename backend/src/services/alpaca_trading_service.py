"""
Alpaca Paper Trading Service for portfolio management.

Provides order execution, position tracking, and portfolio history
using Alpaca's Paper Trading API (FREE for testing).

Based on verification results from scripts/alpaca_test_results.json
"""

from datetime import datetime

import structlog
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import GetPortfolioHistoryRequest, MarketOrderRequest

from ..core.config import Settings
from ..models.portfolio import (
    PortfolioOrder,
    PortfolioPosition,
    PortfolioSummary,
)

logger = structlog.get_logger()


class AlpacaTradingService:
    """
    Alpaca Paper Trading API integration.

    Provides:
    1. Order execution with audit trail (client_order_id)
    2. Position tracking
    3. Portfolio summary
    4. Order history

    Free tier: Paper trading with $1M virtual portfolio
    """

    def __init__(self, settings: Settings):
        """
        Initialize Alpaca trading client.

        Args:
            settings: Application settings with Alpaca credentials
        """
        self.settings = settings

        # Initialize Alpaca client
        self.client = TradingClient(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
            paper=True,  # Paper trading (FREE)
        )

        logger.info(
            "AlpacaTradingService initialized",
            base_url=settings.alpaca_base_url,
            paper_trading=True,
        )

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

        Uses analysis_id as client_order_id to link order to AI analysis.

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

        Example:
            >>> order = await service.place_market_order(
            ...     symbol="AAPL",
            ...     quantity=10,
            ...     side="buy",
            ...     analysis_id="analysis-20251101-AAPL-bullish",
            ...     chat_id="chat_xyz",
            ...     user_id="user_123"
            ... )
            >>> print(order.alpaca_order_id)
            'f8e1b8c3-7d4a-4e2f-9b1c-5a6d7e8f9a0b'
            >>> print(order.analysis_id)
            'analysis-20251101-AAPL-bullish'
        """
        logger.info(
            "Placing market order",
            symbol=symbol,
            quantity=quantity,
            side=side,
            analysis_id=analysis_id,
        )

        try:
            # Create market order request
            order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL

            request = MarketOrderRequest(
                symbol=symbol,
                qty=quantity,
                side=order_side,
                time_in_force=TimeInForce.DAY,
                client_order_id=analysis_id,  # AUDIT TRAIL: Links to analysis
            )

            # Submit order to Alpaca
            alpaca_order = self.client.submit_order(request)

            # Create our PortfolioOrder model
            order = PortfolioOrder(
                order_id=f"order_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                chat_id=chat_id,
                user_id=user_id,
                message_id=message_id,
                alpaca_order_id=str(alpaca_order.id),  # Alpaca's UUID
                analysis_id=analysis_id,  # Our custom ID
                symbol=symbol,
                order_type="market",
                side=side.lower(),
                quantity=quantity,
                status=str(alpaca_order.status),
                filled_qty=float(alpaca_order.filled_qty or 0),
                filled_avg_price=(
                    float(alpaca_order.filled_avg_price)
                    if alpaca_order.filled_avg_price
                    else None
                ),
                created_at=alpaca_order.submitted_at,
                filled_at=alpaca_order.filled_at,
                metadata={
                    "time_in_force": str(alpaca_order.time_in_force),
                    "extended_hours": alpaca_order.extended_hours,
                },
            )

            logger.info(
                "Order placed successfully",
                order_id=order.order_id,
                alpaca_order_id=order.alpaca_order_id,
                status=order.status,
            )

            return order

        except Exception as e:
            logger.error(
                "Failed to place order",
                symbol=symbol,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

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
            order = PortfolioOrder(
                order_id=f"order_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                chat_id="",  # Will be filled from database
                user_id="",  # Will be filled from database
                message_id=None,
                alpaca_order_id=str(alpaca_order.id),
                analysis_id=alpaca_order.client_order_id or "",
                symbol=alpaca_order.symbol,
                order_type=str(alpaca_order.type),
                side=str(alpaca_order.side),
                quantity=float(alpaca_order.qty),
                status=str(alpaca_order.status),
                filled_qty=float(alpaca_order.filled_qty or 0),
                filled_avg_price=(
                    float(alpaca_order.filled_avg_price)
                    if alpaca_order.filled_avg_price
                    else None
                ),
                created_at=alpaca_order.submitted_at,
                filled_at=alpaca_order.filled_at,
            )

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

    async def get_account_summary(self, user_id: str) -> PortfolioSummary:
        """
        Get portfolio summary from Alpaca account.

        Fetches base_value from portfolio history to calculate accurate P&L.

        Args:
            user_id: Portfolio owner

        Returns:
            PortfolioSummary with account values and P&L

        Example:
            >>> summary = await service.get_account_summary("user_123")
            >>> print(summary.equity)
            106870.0
            >>> print(summary.total_pl)
            107.50
        """
        try:
            # Get account info from Alpaca
            account = self.client.get_account()

            # Get positions for position count
            positions = self.client.get_all_positions()

            # Get base_value from portfolio history (this is the actual starting balance)
            history_request = GetPortfolioHistoryRequest(
                period="all",
                timeframe="1D",
            )
            history = self.client.get_portfolio_history(history_request)
            base_value = history.base_value

            # Calculate P&L from actual base value
            equity = float(account.equity)
            total_pl = equity - base_value
            total_pl_pct = (total_pl / base_value * 100) if base_value > 0 else 0.0

            # Create summary
            summary = PortfolioSummary(
                user_id=user_id,
                equity=equity,
                cash=float(account.cash),
                buying_power=float(account.buying_power),
                total_pl=total_pl,
                total_pl_pct=total_pl_pct,
                day_pl=float(account.equity) - float(account.last_equity),
                day_pl_pct=(
                    (float(account.equity) - float(account.last_equity))
                    / float(account.last_equity)
                    * 100
                    if float(account.last_equity) > 0
                    else 0.0
                ),
                position_count=len(positions),
            )

            logger.info(
                "Account summary retrieved",
                user_id=user_id,
                equity=summary.equity,
                base_value=base_value,
                total_pl=summary.total_pl,
                total_pl_pct=summary.total_pl_pct,
                position_count=summary.position_count,
            )

            return summary

        except Exception as e:
            logger.error(
                "Failed to get account summary",
                user_id=user_id,
                error=str(e),
            )
            raise

    async def get_positions(self, user_id: str) -> list[PortfolioPosition]:
        """
        Get all current positions in portfolio.

        Args:
            user_id: Portfolio owner

        Returns:
            List of PortfolioPosition models

        Example:
            >>> positions = await service.get_positions("user_123")
            >>> for pos in positions:
            ...     print(f"{pos.symbol}: {pos.quantity} shares @ ${pos.current_price}")
            'AAPL: 25.0 shares @ $274.80'
        """
        try:
            # Get positions from Alpaca
            alpaca_positions = self.client.get_all_positions()

            positions = []
            for pos in alpaca_positions:
                position = PortfolioPosition(
                    user_id=user_id,
                    symbol=pos.symbol,
                    quantity=float(pos.qty),
                    avg_entry_price=float(pos.avg_entry_price),
                    current_price=float(pos.current_price),
                    market_value=float(pos.market_value),
                    cost_basis=float(pos.cost_basis),
                    unrealized_pl=float(pos.unrealized_pl),
                    unrealized_pl_pct=float(pos.unrealized_plpc) * 100,  # Convert to %
                    first_acquired=datetime.utcnow(),  # Alpaca doesn't provide this
                )
                positions.append(position)

            logger.info(
                "Positions retrieved",
                user_id=user_id,
                position_count=len(positions),
            )

            return positions

        except Exception as e:
            logger.error(
                "Failed to get positions",
                user_id=user_id,
                error=str(e),
            )
            raise

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
            # Get closed orders from Alpaca
            from alpaca.trading.enums import QueryOrderStatus
            from alpaca.trading.requests import GetOrdersRequest

            request = GetOrdersRequest(
                status=QueryOrderStatus.CLOSED,
                limit=limit,
            )

            alpaca_orders = self.client.get_orders(request)

            orders = []
            for alpaca_order in alpaca_orders:
                order = PortfolioOrder(
                    order_id=f"order_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                    chat_id="",  # Will be filled from database
                    user_id=user_id,
                    message_id=None,
                    alpaca_order_id=str(alpaca_order.id),
                    analysis_id=alpaca_order.client_order_id or "",
                    symbol=alpaca_order.symbol,
                    order_type=str(alpaca_order.type),
                    side=str(alpaca_order.side),
                    quantity=float(alpaca_order.qty),
                    status=str(alpaca_order.status),
                    filled_qty=float(alpaca_order.filled_qty or 0),
                    filled_avg_price=(
                        float(alpaca_order.filled_avg_price)
                        if alpaca_order.filled_avg_price
                        else None
                    ),
                    created_at=alpaca_order.submitted_at,
                    filled_at=alpaca_order.filled_at,
                )
                orders.append(order)

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

    async def get_portfolio_history(
        self,
        period: str = "1M",
        timeframe: str = "1D",
    ) -> dict:
        """
        Get portfolio value history from Alpaca.

        Args:
            period: Time period ("1D", "1M", "1Y", "all")
            timeframe: Data granularity ("1Min", "5Min", "15Min", "1H", "1D")

        Returns:
            Dict with:
            - base_value: Starting portfolio value
            - timestamps: List of datetime strings
            - equity: List of portfolio values
            - profit_loss: List of P/L values
            - profit_loss_pct: List of P/L percentages

        Example:
            >>> history = await service.get_portfolio_history(period="1M", timeframe="1D")
            >>> print(history["base_value"])
            100000.0
            >>> print(history["equity"][-1])
            106870.0
        """
        try:
            request = GetPortfolioHistoryRequest(
                period=period,
                timeframe=timeframe,
                extended_hours=False,
            )

            # Run blocking Alpaca API call in thread executor to avoid blocking event loop
            import asyncio

            history = await asyncio.to_thread(
                self.client.get_portfolio_history, request
            )

            logger.info(
                "Portfolio history retrieved",
                period=period,
                timeframe=timeframe,
                data_points=len(history.timestamp),
                base_value=history.base_value,
            )

            return {
                "base_value": history.base_value,
                "timestamps": [
                    datetime.fromtimestamp(ts).isoformat() for ts in history.timestamp
                ],
                "equity": list(history.equity) if history.equity else [],
                "profit_loss": list(history.profit_loss) if history.profit_loss else [],
                "profit_loss_pct": (
                    [pct * 100 for pct in history.profit_loss_pct]
                    if history.profit_loss_pct
                    else []
                ),
            }

        except Exception as e:
            logger.error(
                "Failed to get portfolio history",
                period=period,
                error=str(e),
            )
            raise
