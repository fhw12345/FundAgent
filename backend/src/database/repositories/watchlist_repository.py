"""
Watchlist repository for managing watched stocks.
Handles CRUD operations for watchlist collection.
"""

from datetime import datetime

import structlog
from motor.motor_asyncio import AsyncIOMotorCollection

from ...models.watchlist import WatchlistItem, WatchlistItemCreate

from src.core.utils.date_utils import utcnow
logger = structlog.get_logger()


class WatchlistRepository:
    """Repository for watchlist data access operations."""

    def __init__(self, collection: AsyncIOMotorCollection):
        """
        Initialize watchlist repository.

        Args:
            collection: MongoDB collection for watchlist items
        """
        self.collection = collection

    async def ensure_indexes(self) -> None:
        """
        Create indexes for optimal query performance.
        Called during application startup.
        """
        # Compound index for user + symbol (ensure uniqueness)
        await self.collection.create_index(
            [("user_id", 1), ("symbol", 1)], unique=True, name="idx_user_symbol"
        )
        # Index for user queries
        await self.collection.create_index("user_id", name="user_id_1")
        # Index for analysis scheduling
        await self.collection.create_index(
            "last_analyzed_at", name="last_analyzed_at_1"
        )

        logger.info("Watchlist indexes ensured")

    async def create(
        self, user_id: str, watchlist_create: WatchlistItemCreate
    ) -> WatchlistItem:
        """
        Create a new watchlist item.

        Args:
            user_id: User identifier
            watchlist_create: Watchlist item creation data

        Returns:
            Created watchlist item with generated ID

        Raises:
            DuplicateKeyError: If symbol already in user's watchlist
        """
        import uuid

        watchlist_id = f"watch_{uuid.uuid4().hex[:12]}"

        watchlist_item = WatchlistItem(
            watchlist_id=watchlist_id,
            user_id=user_id,
            symbol=watchlist_create.symbol.upper(),  # Normalize to uppercase
            added_at=utcnow(),
            last_analyzed_at=None,
            notes=watchlist_create.notes,
        )

        # Convert to dict for MongoDB
        watchlist_dict = watchlist_item.model_dump()

        # Insert into database
        await self.collection.insert_one(watchlist_dict)

        logger.info(
            "Watchlist item created",
            watchlist_id=watchlist_id,
            user_id=user_id,
            symbol=watchlist_item.symbol,
        )

        return watchlist_item

    async def get_by_user(self, user_id: str) -> list[WatchlistItem]:
        """
        Get all watchlist items for a user.

        Args:
            user_id: User identifier

        Returns:
            List of watchlist items sorted by added_at descending
        """
        cursor = self.collection.find({"user_id": user_id}).sort(
            "added_at", -1
        )  # Newest first

        items = []
        async for item_dict in cursor:
            # Remove MongoDB _id field
            item_dict.pop("_id", None)
            items.append(WatchlistItem(**item_dict))

        return items

    async def get_by_id(self, watchlist_id: str, user_id: str) -> WatchlistItem | None:
        """
        Get a specific watchlist item.

        Args:
            watchlist_id: Watchlist item identifier
            user_id: User identifier (for security - ensure ownership)

        Returns:
            Watchlist item if found, None otherwise
        """
        item_dict = await self.collection.find_one(
            {"watchlist_id": watchlist_id, "user_id": user_id}
        )

        if not item_dict:
            return None

        # Remove MongoDB _id field
        item_dict.pop("_id", None)

        return WatchlistItem(**item_dict)

    async def delete(self, watchlist_id: str, user_id: str) -> bool:
        """
        Delete a watchlist item.

        Args:
            watchlist_id: Watchlist item identifier
            user_id: User identifier (for security - ensure ownership)

        Returns:
            True if deleted, False if not found
        """
        result = await self.collection.delete_one(
            {"watchlist_id": watchlist_id, "user_id": user_id}
        )

        deleted = result.deleted_count > 0

        if deleted:
            logger.info(
                "Watchlist item deleted", watchlist_id=watchlist_id, user_id=user_id
            )

        return deleted

    async def update_last_analyzed(
        self, watchlist_id: str, user_id: str, timestamp: datetime | None = None
    ) -> bool:
        """
        Update last_analyzed_at timestamp.

        Args:
            watchlist_id: Watchlist item identifier
            user_id: User identifier
            timestamp: Timestamp to set (defaults to now)

        Returns:
            True if updated, False if not found
        """
        if timestamp is None:
            timestamp = utcnow()

        result = await self.collection.update_one(
            {"watchlist_id": watchlist_id, "user_id": user_id},
            {"$set": {"last_analyzed_at": timestamp}},
        )

        updated = result.modified_count > 0

        if updated:
            logger.info(
                "Watchlist item analyzed timestamp updated",
                watchlist_id=watchlist_id,
                user_id=user_id,
                timestamp=timestamp.isoformat(),
            )

        return updated

    async def get_stale_items(self, minutes: int = 5) -> list[WatchlistItem]:
        """
        Get watchlist items that haven't been analyzed recently.

        Useful for automated analysis scheduling (default: 5 minutes).

        Args:
            minutes: Minimum minutes since last analysis

        Returns:
            List of watchlist items needing analysis
        """
        from datetime import timedelta

        cutoff_time = utcnow() - timedelta(minutes=minutes)

        # Find items either never analyzed OR analyzed before cutoff
        cursor = self.collection.find(
            {
                "$or": [
                    {"last_analyzed_at": None},
                    {"last_analyzed_at": {"$lt": cutoff_time}},
                ]
            }
        ).sort(
            "last_analyzed_at", 1
        )  # Oldest first

        items = []
        async for item_dict in cursor:
            # Remove MongoDB _id field
            item_dict.pop("_id", None)
            items.append(WatchlistItem(**item_dict))

        logger.info(
            "Stale watchlist items retrieved", count=len(items), min_age_minutes=minutes
        )

        return items
