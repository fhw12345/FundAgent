"""
Feedback service for business logic coordination.

This service orchestrates feedback repositories, user repositories, and comment repositories
to provide high-level business operations for the feedback platform.

For export functionality, see feedback_export_service.py.
"""

import structlog

from ..database.mongodb import MongoDB
from ..database.repositories.comment_repository import CommentRepository
from ..database.repositories.feedback_repository import FeedbackRepository
from ..database.repositories.user_repository import UserRepository
from ..models.feedback import Comment, CommentCreate, FeedbackItem, FeedbackItemCreate

logger = structlog.get_logger()


class FeedbackService:
    """Service for feedback platform business logic."""

    def __init__(
        self,
        feedback_repo: FeedbackRepository,
        comment_repo: CommentRepository,
        user_repo: UserRepository,
        mongodb: MongoDB,
    ):
        """
        Initialize feedback service.

        Args:
            feedback_repo: Repository for feedback items
            comment_repo: Repository for comments
            user_repo: Repository for users (for vote tracking and author lookups)
            mongodb: MongoDB instance for transactions
        """
        self.feedback_repo = feedback_repo
        self.comment_repo = comment_repo
        self.user_repo = user_repo
        self.mongodb = mongodb

    async def create_item(
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
            Created feedback item
        """
        item = await self.feedback_repo.create(item_create, author_id)

        # Fetch author username
        author = await self.user_repo.get_by_id(author_id)
        if author:
            item.authorUsername = author.username

        logger.info(
            "Feedback item created",
            item_id=item.item_id,
            author_id=author_id,
            type=item.type,
        )

        return item

    async def get_item(
        self,
        item_id: str,
        user_id: str | None = None,
    ) -> FeedbackItem | None:
        """
        Get a feedback item by ID with user context.

        Args:
            item_id: Feedback item identifier
            user_id: Current user ID (optional, for hasVoted field)

        Returns:
            Feedback item if found, None otherwise
        """
        item = await self.feedback_repo.get_by_id(item_id)

        if not item:
            return None

        # Inject hasVoted field if user is authenticated
        if user_id:
            user_votes = await self.user_repo.get_user_votes(user_id)
            item.hasVoted = item_id in user_votes

        # Fetch author username
        author = await self.user_repo.get_by_id(item.authorId)
        if author:
            item.authorUsername = author.username

        return item

    async def list_items(
        self,
        feedback_type: str | None = None,
        user_id: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[FeedbackItem]:
        """
        List feedback items with user context.

        Args:
            feedback_type: Filter by type ('feature' or 'bug'), None for all
            user_id: Current user ID (optional, for hasVoted field)
            skip: Number of items to skip (pagination)
            limit: Maximum number of items to return

        Returns:
            List of feedback items sorted by vote count
        """
        items = await self.feedback_repo.list_by_type(feedback_type, skip, limit)

        if not items:
            return items

        # Get user votes if authenticated
        user_votes = []
        if user_id:
            user_votes = await self.user_repo.get_user_votes(user_id)

        # Batch fetch all unique authors in ONE query (fixes N+1 problem)
        unique_author_ids = list({item.authorId for item in items})
        authors_map = await self.user_repo.get_by_ids(unique_author_ids)

        # Inject hasVoted and authorUsername fields
        for item in items:
            if user_id:
                item.hasVoted = item.item_id in user_votes

            # Map author username from batch-fetched data
            author = authors_map.get(item.authorId)
            if author:
                item.authorUsername = author.username

        return items

    async def vote_item(self, item_id: str, user_id: str) -> bool:
        """
        Cast a vote for a feedback item (idempotent).

        Uses MongoDB transactions if available (replica set),
        otherwise falls back to sequential operations.

        Args:
            item_id: Feedback item identifier
            user_id: User ID casting the vote

        Returns:
            True if vote was added, False if already voted or item not found
        """
        # Check if item exists
        item = await self.feedback_repo.get_by_id(item_id)
        if not item:
            logger.warning("Vote failed - item not found", item_id=item_id)
            return False

        # Check if user has already voted
        user_votes = await self.user_repo.get_user_votes(user_id)
        if item_id in user_votes:
            logger.info(
                "Vote skipped - already voted",
                item_id=item_id,
                user_id=user_id,
            )
            return False  # Idempotent - already voted

        # Try to use transaction if MongoDB supports it (replica set)
        if self.mongodb.client:
            try:
                async with await self.mongodb.client.start_session() as session:
                    async with session.start_transaction():
                        # Add vote to item (atomic increment within transaction)
                        success = await self.feedback_repo.increment_vote_count(
                            item_id, delta=1, session=session
                        )
                        if not success:
                            await session.abort_transaction()
                            return False

                        # Add to user's voted items (within same transaction)
                        success = await self.user_repo.add_vote(
                            user_id, item_id, session=session
                        )
                        if not success:
                            await session.abort_transaction()
                            return False

                logger.info(
                    "Vote cast successfully (transactional)",
                    item_id=item_id,
                    user_id=user_id,
                )
                return True
            except Exception as e:
                # If transaction fails (e.g., standalone MongoDB), fall back to sequential
                error_msg = str(e)
                if (
                    "replica set" in error_msg.lower()
                    or "transaction" in error_msg.lower()
                ):
                    logger.warning(
                        "Transactions not supported - falling back to sequential operations",
                        error=error_msg,
                    )
                else:
                    # Unexpected error
                    logger.error("Transaction failed", error=error_msg)
                    return False

        # Fallback: Sequential operations (no transaction)
        # Add vote to item (atomic increment)
        success = await self.feedback_repo.increment_vote_count(item_id, delta=1)
        if not success:
            return False

        # Add to user's voted items
        await self.user_repo.add_vote(user_id, item_id)

        logger.info(
            "Vote cast successfully (non-transactional)",
            item_id=item_id,
            user_id=user_id,
        )
        return True

    async def unvote_item(self, item_id: str, user_id: str) -> bool:
        """
        Remove a vote from a feedback item (idempotent).

        Uses MongoDB transactions if available (replica set),
        otherwise falls back to sequential operations.

        Args:
            item_id: Feedback item identifier
            user_id: User ID removing the vote

        Returns:
            True if vote was removed, False if not voted or item not found
        """
        # Check if item exists
        item = await self.feedback_repo.get_by_id(item_id)
        if not item:
            logger.warning("Unvote failed - item not found", item_id=item_id)
            return False

        # Check if user has voted
        user_votes = await self.user_repo.get_user_votes(user_id)
        if item_id not in user_votes:
            logger.info(
                "Unvote skipped - not voted",
                item_id=item_id,
                user_id=user_id,
            )
            return False  # Idempotent - not voted

        # Try to use transaction if MongoDB supports it (replica set)
        if self.mongodb.client:
            try:
                async with await self.mongodb.client.start_session() as session:
                    async with session.start_transaction():
                        # Remove vote from item (atomic decrement within transaction)
                        success = await self.feedback_repo.increment_vote_count(
                            item_id, delta=-1, session=session
                        )
                        if not success:
                            await session.abort_transaction()
                            return False

                        # Remove from user's voted items (within same transaction)
                        success = await self.user_repo.remove_vote(
                            user_id, item_id, session=session
                        )
                        if not success:
                            await session.abort_transaction()
                            return False

                logger.info(
                    "Vote removed successfully (transactional)",
                    item_id=item_id,
                    user_id=user_id,
                )
                return True
            except Exception as e:
                # If transaction fails (e.g., standalone MongoDB), fall back to sequential
                error_msg = str(e)
                if (
                    "replica set" in error_msg.lower()
                    or "transaction" in error_msg.lower()
                ):
                    logger.warning(
                        "Transactions not supported - falling back to sequential operations",
                        error=error_msg,
                    )
                else:
                    # Unexpected error
                    logger.error("Transaction failed", error=error_msg)
                    return False

        # Fallback: Sequential operations (no transaction)
        # Remove vote from item (atomic decrement)
        success = await self.feedback_repo.increment_vote_count(item_id, delta=-1)
        if not success:
            return False

        # Remove from user's voted items
        await self.user_repo.remove_vote(user_id, item_id)

        logger.info(
            "Vote removed successfully (non-transactional)",
            item_id=item_id,
            user_id=user_id,
        )
        return True

    async def add_comment(
        self,
        item_id: str,
        comment_create: CommentCreate,
        author_id: str,
    ) -> Comment | None:
        """
        Add a comment to a feedback item.

        Args:
            item_id: Feedback item identifier
            comment_create: Comment creation data
            author_id: User ID of the comment author

        Returns:
            Created comment if successful, None if item not found
        """
        # Check if item exists
        item = await self.feedback_repo.get_by_id(item_id)
        if not item:
            logger.warning("Comment failed - item not found", item_id=item_id)
            return None

        # Create comment
        comment = await self.comment_repo.create(comment_create, item_id, author_id)

        # Increment comment count on item
        await self.feedback_repo.increment_comment_count(item_id)

        # Fetch author username
        author = await self.user_repo.get_by_id(author_id)
        if author:
            comment.authorUsername = author.username

        logger.info(
            "Comment added",
            comment_id=comment.comment_id,
            item_id=item_id,
            author_id=author_id,
        )

        return comment

    async def get_comments(self, item_id: str) -> list[Comment]:
        """
        Get all comments for a feedback item with author usernames.

        Args:
            item_id: Feedback item identifier

        Returns:
            List of comments sorted by creation date
        """
        comments = await self.comment_repo.list_by_item(item_id)

        if not comments:
            return comments

        # Batch fetch all unique authors in ONE query (fixes N+1 problem)
        unique_author_ids = list({comment.authorId for comment in comments})
        authors_map = await self.user_repo.get_by_ids(unique_author_ids)

        # Map author usernames from batch-fetched data
        for comment in comments:
            author = authors_map.get(comment.authorId)
            if author:
                comment.authorUsername = author.username

        return comments

    async def update_status(self, item_id: str, new_status: str) -> FeedbackItem | None:
        """
        Update the status of a feedback item (admin only).

        Args:
            item_id: Feedback item identifier
            new_status: New status value

        Returns:
            Updated feedback item if successful, None if item not found
        """
        # Check if item exists
        item = await self.feedback_repo.get_by_id(item_id)
        if not item:
            logger.warning("Status update failed - item not found", item_id=item_id)
            return None

        # Update status
        success = await self.feedback_repo.update_status(item_id, new_status)
        if not success:
            return None

        # Fetch updated item
        updated_item = await self.feedback_repo.get_by_id(item_id)

        if updated_item:
            # Fetch author username
            author = await self.user_repo.get_by_id(updated_item.authorId)
            if author:
                updated_item.authorUsername = author.username

        logger.info(
            "Status updated successfully", item_id=item_id, new_status=new_status
        )
        return updated_item
