"""
Comment repository for feedback item comments management.
Handles CRUD operations for comments collection.
"""

import uuid
from datetime import datetime

import structlog
from motor.motor_asyncio import AsyncIOMotorCollection

from ...models.feedback import Comment, CommentCreate

logger = structlog.get_logger()


class CommentRepository:
    """Repository for comment data access operations."""

    def __init__(self, collection: AsyncIOMotorCollection):
        """
        Initialize comment repository.

        Args:
            collection: MongoDB collection for comments
        """
        self.collection = collection

    async def ensure_indexes(self) -> None:
        """
        Create database indexes for optimal query performance.

        Indexes:
        - comment_id (unique) - for fast lookups
        - itemId - for fetching comments by feedback item (most common query)
        - authorId - for user's comments lookup
        - (itemId, createdAt) - compound index for sorted comments
        """
        # Unique index on comment_id
        await self.collection.create_index("comment_id", unique=True)

        # Index on itemId (most common query)
        await self.collection.create_index("itemId")

        # Index on authorId for user's comments
        await self.collection.create_index("authorId")

        # Compound index for fetching comments sorted by date
        await self.collection.create_index([("itemId", 1), ("createdAt", 1)])

        logger.info("Comment indexes created")

    async def create(
        self,
        comment_create: CommentCreate,
        item_id: str,
        author_id: str,
    ) -> Comment:
        """
        Create a new comment on a feedback item.

        Args:
            comment_create: Comment creation data
            item_id: Feedback item ID this comment belongs to
            author_id: User ID of the comment author

        Returns:
            Created comment with generated ID
        """
        # Generate comment_id
        comment_id = f"comment_{uuid.uuid4().hex[:12]}"

        now = datetime.utcnow()

        # Create database document
        comment_dict = {
            "comment_id": comment_id,
            "itemId": item_id,
            "authorId": author_id,
            "content": comment_create.content,
            "createdAt": now,
        }

        # Insert into database
        await self.collection.insert_one(comment_dict)

        logger.info(
            "Comment created",
            comment_id=comment_id,
            item_id=item_id,
            author_id=author_id,
        )

        # Return as Comment model
        return Comment(
            comment_id=comment_id,
            itemId=item_id,
            authorId=author_id,
            content=comment_create.content,
            createdAt=now,
            authorUsername=None,  # Will be populated by service layer
        )

    async def list_by_item(self, item_id: str) -> list[Comment]:
        """
        List all comments for a specific feedback item.

        Args:
            item_id: Feedback item identifier

        Returns:
            List of comments sorted by creation date (ascending - oldest first)
        """
        cursor = self.collection.find({"itemId": item_id}).sort("createdAt", 1)

        comments = []
        async for comment_dict in cursor:
            # Remove MongoDB _id field
            comment_dict.pop("_id", None)
            comments.append(Comment(**comment_dict))

        return comments

    async def get_by_id(self, comment_id: str) -> Comment | None:
        """
        Get comment by ID.

        Args:
            comment_id: Comment identifier

        Returns:
            Comment if found, None otherwise
        """
        comment_dict = await self.collection.find_one({"comment_id": comment_id})

        if not comment_dict:
            return None

        # Remove MongoDB _id field
        comment_dict.pop("_id", None)

        return Comment(**comment_dict)

    async def delete(self, comment_id: str) -> bool:
        """
        Delete a comment.

        Args:
            comment_id: Comment identifier

        Returns:
            True if deleted, False if not found
        """
        result = await self.collection.delete_one({"comment_id": comment_id})

        if result.deleted_count == 0:
            logger.warning("Failed to delete comment", comment_id=comment_id)
            return False

        logger.info("Comment deleted", comment_id=comment_id)
        return True

    async def count_by_item(self, item_id: str) -> int:
        """
        Count comments for a specific feedback item.

        Args:
            item_id: Feedback item identifier

        Returns:
            Number of comments
        """
        count = await self.collection.count_documents({"itemId": item_id})
        return count
