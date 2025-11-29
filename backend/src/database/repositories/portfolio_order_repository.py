"""
Portfolio order repository for order audit trail.

Stores all orders placed through Alpaca with complete audit trail
linking orders to analysis decisions and chat contexts.
"""

from datetime import datetime

import structlog
from motor.motor_asyncio import AsyncIOMotorCollection

from ...models.portfolio import PortfolioOrder

logger = structlog.get_logger()


class PortfolioOrderRepository:
    """Repository for portfolio order data access operations."""

    def __init__(self, collection: AsyncIOMotorCollection):
        """
        Initialize portfolio order repository.

        Args:
            collection: MongoDB collection for portfolio_orders
        """
        self.collection = collection

    async def ensure_indexes(self) -> None:
        """
        Create indexes for optimal query performance.

        Indexes:
        1. user_id + created_at: For listing user orders by time
        2. analysis_id: For linking orders to analyses (audit trail)
        3. alpaca_order_id: For looking up orders by Alpaca ID (unique)
        4. user_id + status: For filtering orders by status
        5. user_id + symbol: For symbol-specific order history
        """
        # Index for listing user orders sorted by time
        await self.collection.create_index(
            [("user_id", 1), ("created_at", -1)],
            name="idx_user_orders",
        )

        # Index for audit trail (analysis → order linkage)
        await self.collection.create_index(
            [("analysis_id", 1)],
            name="idx_analysis_orders",
        )

        # Unique index on Alpaca order ID (prevent duplicates)
        # sparse=True allows multiple documents with null alpaca_order_id (failed orders)
        await self.collection.create_index(
            [("alpaca_order_id", 1)],
            name="idx_alpaca_order",
            unique=True,
            sparse=True,
        )

        # Index for filtering by status
        await self.collection.create_index(
            [("user_id", 1), ("status", 1), ("created_at", -1)],
            name="idx_user_status_orders",
        )

        # Index for symbol-specific queries
        await self.collection.create_index(
            [("user_id", 1), ("symbol", 1), ("created_at", -1)],
            name="idx_user_symbol_orders",
        )

        logger.info("Portfolio order indexes ensured")

    async def create(self, order: PortfolioOrder) -> PortfolioOrder:
        """
        Create a new portfolio order.

        Args:
            order: Portfolio order to store

        Returns:
            Created order

        Raises:
            DuplicateKeyError: If order with same alpaca_order_id exists
        """
        # Convert to dict for MongoDB
        order_dict = order.model_dump()

        # Insert into database
        await self.collection.insert_one(order_dict)

        logger.info(
            "Portfolio order created",
            order_id=order.order_id,
            alpaca_order_id=order.alpaca_order_id,
            user_id=order.user_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            status=order.status,
            analysis_id=order.analysis_id,
        )

        return order

    async def create_many(self, orders: list[PortfolioOrder]) -> int:
        """
        Batch insert multiple portfolio orders.

        Uses insert_many() for efficient bulk insertion, reducing
        database round trips from N to 1.

        Args:
            orders: List of portfolio orders to store

        Returns:
            Number of orders inserted

        Raises:
            BulkWriteError: If any order fails (e.g., duplicate alpaca_order_id)
        """
        if not orders:
            return 0

        order_dicts = [o.model_dump() for o in orders]
        result = await self.collection.insert_many(order_dicts)

        logger.info(
            "Portfolio orders batch created",
            count=len(result.inserted_ids),
            symbols=[o.symbol for o in orders],
        )

        return len(result.inserted_ids)

    async def get(self, order_id: str) -> PortfolioOrder | None:
        """
        Get order by internal order ID.

        Args:
            order_id: Internal order identifier

        Returns:
            PortfolioOrder if found, None otherwise
        """
        order_dict = await self.collection.find_one({"order_id": order_id})

        if not order_dict:
            return None

        # Remove MongoDB _id field
        order_dict.pop("_id", None)

        return PortfolioOrder(**order_dict)

    async def get_by_alpaca_id(self, alpaca_order_id: str) -> PortfolioOrder | None:
        """
        Get order by Alpaca order ID.

        Args:
            alpaca_order_id: Alpaca's native order UUID

        Returns:
            PortfolioOrder if found, None otherwise
        """
        order_dict = await self.collection.find_one(
            {"alpaca_order_id": alpaca_order_id}
        )

        if not order_dict:
            return None

        # Remove MongoDB _id field
        order_dict.pop("_id", None)

        return PortfolioOrder(**order_dict)

    async def get_by_analysis_id(self, analysis_id: str) -> PortfolioOrder | None:
        """
        Get order by analysis ID (audit trail).

        Args:
            analysis_id: Analysis identifier used as client_order_id

        Returns:
            PortfolioOrder if found, None otherwise
        """
        order_dict = await self.collection.find_one({"analysis_id": analysis_id})

        if not order_dict:
            return None

        # Remove MongoDB _id field
        order_dict.pop("_id", None)

        return PortfolioOrder(**order_dict)

    async def list_by_user(
        self,
        user_id: str,
        status: str | None = None,
        symbol: str | None = None,
        limit: int = 100,
    ) -> list[PortfolioOrder]:
        """
        List orders for a user with optional filtering.

        Args:
            user_id: User identifier
            status: Optional status filter ("filled", "canceled", etc.)
            symbol: Optional symbol filter
            limit: Maximum number of orders to return

        Returns:
            List of orders sorted by created_at descending
        """
        # Build query
        query = {"user_id": user_id}

        if status:
            query["status"] = status

        if symbol:
            query["symbol"] = symbol.upper()

        # Execute query
        cursor = self.collection.find(query).sort("created_at", -1).limit(limit)

        orders = []
        async for order_dict in cursor:
            # Remove MongoDB _id field
            order_dict.pop("_id", None)
            orders.append(PortfolioOrder(**order_dict))

        return orders

    async def list_by_chat(
        self, chat_id: str, limit: int = 100
    ) -> list[PortfolioOrder]:
        """
        List orders for a specific chat.

        Args:
            chat_id: Chat identifier
            limit: Maximum number of orders to return

        Returns:
            List of orders sorted by created_at descending
        """
        cursor = (
            self.collection.find({"chat_id": chat_id})
            .sort("created_at", -1)
            .limit(limit)
        )

        orders = []
        async for order_dict in cursor:
            # Remove MongoDB _id field
            order_dict.pop("_id", None)
            orders.append(PortfolioOrder(**order_dict))

        return orders

    async def update_status(
        self,
        alpaca_order_id: str,
        status: str,
        filled_qty: float | None = None,
        filled_avg_price: float | None = None,
        filled_at: datetime | None = None,
    ) -> PortfolioOrder | None:
        """
        Update order status and fill information.

        Used when order status changes in Alpaca (e.g., filled, canceled).

        Args:
            alpaca_order_id: Alpaca order UUID
            status: New status
            filled_qty: Filled quantity (if status is filled/partially_filled)
            filled_avg_price: Average fill price
            filled_at: Fill timestamp

        Returns:
            Updated order if found, None otherwise
        """
        # Build update dict
        update_dict = {
            "status": status,
            "updated_at": datetime.utcnow(),
        }

        if filled_qty is not None:
            update_dict["filled_qty"] = filled_qty

        if filled_avg_price is not None:
            update_dict["filled_avg_price"] = filled_avg_price

        if filled_at is not None:
            update_dict["filled_at"] = filled_at

        # Update in database
        result = await self.collection.find_one_and_update(
            {"alpaca_order_id": alpaca_order_id},
            {"$set": update_dict},
            return_document=True,
        )

        if not result:
            return None

        # Remove MongoDB _id field
        result.pop("_id", None)

        logger.info(
            "Order status updated",
            alpaca_order_id=alpaca_order_id,
            status=status,
            filled_qty=filled_qty,
            filled_avg_price=filled_avg_price,
        )

        return PortfolioOrder(**result)

    async def count_by_user(self, user_id: str, status: str | None = None) -> int:
        """
        Count orders for a user.

        Args:
            user_id: User identifier
            status: Optional status filter

        Returns:
            Order count
        """
        query = {"user_id": user_id}

        if status:
            query["status"] = status

        return await self.collection.count_documents(query)
