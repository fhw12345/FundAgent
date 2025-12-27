"""
Feedback repository for feedback item management.
Handles CRUD operations for feedback_items collection.
"""

import uuid
from typing import Any

import structlog
from motor.motor_asyncio import AsyncIOMotorCollection

from src.core.utils.date_utils import utcnow

from ...models.feedback import FeedbackItem, FeedbackItemCreate

logger = structlog.get_logger()


class FeedbackRepository:
    """Repository for feedback item data access operations."""

    def __init__(self, collection: AsyncIOMotorCollection):
        """
        Initialize feedback repository.

        Args:
            collection: MongoDB collection for feedback items
        """
        self.collection = collection

    async def ensure_indexes(self) -> None:
        """
        Create database indexes for optimal query performance.

        Indexes:
        - item_id (unique) - for fast lookups
        - voteCount (desc) - for leaderboard sorting
        - type - for filtering features/bugs
        - authorId - for user's feedback lookup
        - (type, voteCount desc) - compound index for filtered leaderboards
        """
        # Unique index on item_id
        await self.collection.create_index("item_id", unique=True)

        # Single field indexes
        await self.collection.create_index(
            [("voteCount", -1)]
        )  # Descending for leaderboard
        await self.collection.create_index("type")
        await self.collection.create_index("authorId")

        # Compound index for filtered leaderboards (most common query)
        await self.collection.create_index([("type", 1), ("voteCount", -1)])

        logger.info("Feedback item indexes created")

    async def create(
        self,
        item_create: FeedbackItemCreate,
        author_id: str,
    ) -> FeedbackItem:
        """
        Create a new feedback item.

        Args:
            item_create: Feedback item creation data
            author_id: User ID of the author

        Returns:
            Created feedback item with generated ID
        """
        # Generate item_id
        item_id = f"feedback_{uuid.uuid4().hex[:12]}"

        now = utcnow()

        # Create database document
        item_dict = {
            "item_id": item_id,
            "title": item_create.title,
            "description": item_create.description,
            "authorId": author_id,
            "type": item_create.type,
            "status": "under_consideration",  # Default status
            "voteCount": 0,  # Initial vote count
            "commentCount": 0,  # Initial comment count
            "createdAt": now,
            "updatedAt": now,
            "image_urls": item_create.image_urls,  # Image attachments
        }

        # Insert into database
        await self.collection.insert_one(item_dict)

        logger.info(
            "Feedback item created",
            item_id=item_id,
            author_id=author_id,
            type=item_create.type,
        )

        # Return as FeedbackItem model
        return FeedbackItem(
            item_id=item_id,
            title=item_create.title,
            description=item_create.description,
            authorId=author_id,
            type=item_create.type,
            status="under_consideration",
            voteCount=0,
            commentCount=0,
            createdAt=now,
            updatedAt=now,
            image_urls=item_create.image_urls,
            hasVoted=False,
            authorUsername=None,  # Will be populated by service layer
        )

    async def get_by_id(self, item_id: str) -> FeedbackItem | None:
        """
        Get feedback item by ID.

        Args:
            item_id: Feedback item identifier

        Returns:
            Feedback item if found, None otherwise
        """
        item_dict = await self.collection.find_one({"item_id": item_id})

        if not item_dict:
            return None

        # Remove MongoDB _id field
        item_dict.pop("_id", None)

        return FeedbackItem(**item_dict, hasVoted=False)

    async def list_by_type(
        self,
        feedback_type: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[FeedbackItem]:
        """
        List feedback items, optionally filtered by type.

        Args:
            feedback_type: Filter by type ('feature' or 'bug'), None for all
            skip: Number of items to skip (pagination)
            limit: Maximum number of items to return

        Returns:
            List of feedback items sorted by vote count (descending)
        """
        # Build query filter
        query = {}
        if feedback_type:
            query["type"] = feedback_type

        # Fetch items sorted by voteCount descending
        cursor = (
            self.collection.find(query).sort("voteCount", -1).skip(skip).limit(limit)
        )

        items = []
        async for item_dict in cursor:
            # Remove MongoDB _id field
            item_dict.pop("_id", None)
            items.append(FeedbackItem(**item_dict, hasVoted=False))

        return items

    async def increment_vote_count(
        self, item_id: str, delta: int, session: Any = None
    ) -> bool:
        """
        Atomically increment vote count for a feedback item.

        Args:
            item_id: Feedback item identifier
            delta: Amount to increment (+1 for vote, -1 for unvote)
            session: Optional MongoDB session for transactions

        Returns:
            True if successful, False if item not found
        """
        result = await self.collection.update_one(
            {"item_id": item_id},
            {
                "$inc": {"voteCount": delta},
                "$set": {"updatedAt": utcnow()},
            },
            session=session,
        )

        if result.modified_count == 0:
            logger.warning("Failed to increment vote count", item_id=item_id)
            return False

        logger.info(
            "Vote count incremented",
            item_id=item_id,
            delta=delta,
        )
        return True

    async def increment_comment_count(self, item_id: str) -> bool:
        """
        Atomically increment comment count for a feedback item.

        Args:
            item_id: Feedback item identifier

        Returns:
            True if successful, False if item not found
        """
        result = await self.collection.update_one(
            {"item_id": item_id},
            {
                "$inc": {"commentCount": 1},
                "$set": {"updatedAt": utcnow()},
            },
        )

        if result.modified_count == 0:
            logger.warning("Failed to increment comment count", item_id=item_id)
            return False

        logger.info("Comment count incremented", item_id=item_id)
        return True

    async def get_all(self) -> list[FeedbackItem]:
        """
        Get all feedback items (for export functionality).

        Returns:
            List of all feedback items
        """
        cursor = self.collection.find({}).sort("createdAt", -1)

        items = []
        async for item_dict in cursor:
            # Remove MongoDB _id field
            item_dict.pop("_id", None)
            items.append(FeedbackItem(**item_dict, hasVoted=False))

        return items

    async def update_status(self, item_id: str, status: str) -> bool:
        """
        Update the status of a feedback item.

        Args:
            item_id: Feedback item identifier
            status: New status value

        Returns:
            True if successful, False if item not found
        """
        result = await self.collection.update_one(
            {"item_id": item_id},
            {
                "$set": {
                    "status": status,
                    "updatedAt": utcnow(),
                }
            },
        )

        if result.modified_count == 0:
            logger.warning("Failed to update status", item_id=item_id)
            return False

        logger.info("Status updated", item_id=item_id, status=status)
        return True
