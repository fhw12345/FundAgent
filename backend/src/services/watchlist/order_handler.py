"""
Order placement handler for watchlist analysis.

Manages trading order placement via Alpaca.
"""

import structlog

from ...database.repositories.message_repository import MessageRepository

logger = structlog.get_logger()


class OrderHandler:
    """Handles order placement for trading decisions."""

    def __init__(
        self,
        message_repo: MessageRepository,
        trading_service,
        order_repository,
    ):
        """
        Initialize order handler.

        Args:
            message_repo: Repository for message operations
            trading_service: Trading service for order placement
            order_repository: Repository for persisting orders
        """
        self.message_repo = message_repo
        self.trading_service = trading_service
        self.order_repository = order_repository

    async def place_order(
        self,
        symbol: str,
        decision: str,
        position_size: int,
        analysis_id: str,
        chat_id: str,
        user_id: str,
        message,
    ):
        """
        Place trading order via Alpaca.

        Args:
            symbol: Stock symbol
            decision: Trading decision (BUY/SELL)
            position_size: Position size percentage
            analysis_id: Analysis ID
            chat_id: Chat ID
            user_id: User ID
            message: Analysis message object
        """
        try:
            # For now, use a fixed quantity of 1 share
            # TODO: Calculate quantity based on position_size percentage and portfolio value
            quantity = 1

            logger.info(
                "Placing order via Alpaca",
                symbol=symbol,
                side=decision.lower(),
                quantity=quantity,
                analysis_id=analysis_id,
            )

            order = await self.trading_service.place_market_order(
                symbol=symbol,
                quantity=quantity,
                side=decision.lower(),
                analysis_id=analysis_id,
                chat_id=chat_id,
                user_id=user_id,
                message_id=message.message_id if message else None,
            )

            # Persist order to MongoDB for audit trail
            if self.order_repository:
                await self.order_repository.create(order)
                logger.info("Order persisted to MongoDB", order_id=order.order_id)
            else:
                logger.warning(
                    "Order repository not available - order not persisted to MongoDB"
                )

            logger.info(
                "Order placed successfully",
                symbol=symbol,
                order_id=order.alpaca_order_id,
                analysis_id=analysis_id,
            )

            # Update message metadata with order_id
            if message:
                message.metadata.order_placed = True
                message.metadata.order_id = order.alpaca_order_id
                await self.message_repo.update_metadata(
                    message.message_id, message.metadata
                )

        except Exception as e:
            logger.error(
                "Failed to place order",
                symbol=symbol,
                error=str(e),
                error_type=type(e).__name__,
            )
            # Don't fail the whole analysis if order placement fails
