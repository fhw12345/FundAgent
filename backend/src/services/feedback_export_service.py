"""
Feedback export service for Markdown snapshots.

This service handles exporting all feedback items and comments to Markdown format,
optimized with batch fetching to avoid N+1 query problems.
"""

import structlog

from src.core.utils.date_utils import utcnow

from ..database.repositories.comment_repository import CommentRepository
from ..database.repositories.feedback_repository import FeedbackRepository
from ..database.repositories.user_repository import UserRepository
from ..models.feedback import Comment

logger = structlog.get_logger()


class FeedbackExportService:
    """Service for exporting feedback data to Markdown."""

    def __init__(
        self,
        feedback_repo: FeedbackRepository,
        comment_repo: CommentRepository,
        user_repo: UserRepository,
    ):
        """
        Initialize feedback export service.

        Args:
            feedback_repo: Repository for feedback items
            comment_repo: Repository for comments
            user_repo: Repository for users (for author lookups)
        """
        self.feedback_repo = feedback_repo
        self.comment_repo = comment_repo
        self.user_repo = user_repo

    async def export_all(self) -> str:
        """
        Generate a Markdown snapshot of all feedback items and comments.

        Optimized to avoid N+1 queries by batch-fetching all users upfront.

        Returns:
            Markdown-formatted string containing all feedback
        """
        items = await self.feedback_repo.get_all()

        if not items:
            return "# Feedback & Community Roadmap Export\n\nNo feedback items found."

        # Batch fetch ALL unique authors upfront (fixes N+1 problem)
        all_author_ids = {item.authorId for item in items}

        # Fetch all comments for all items
        all_comments = []
        for item in items:
            comments = await self.comment_repo.list_by_item(item.item_id)
            all_comments.extend(comments)
            # Collect comment author IDs too
            all_author_ids.update(comment.authorId for comment in comments)

        # Single batch query for ALL unique authors
        authors_map = await self.user_repo.get_by_ids(list(all_author_ids))

        markdown_lines = [
            "# Feedback & Community Roadmap Export",
            "",
            f"Generated: {utcnow().isoformat()}",
            f"Total Items: {len(items)}",
            f"Total Comments: {len(all_comments)}",
            "",
            "---",
            "",
        ]

        # Group comments by item_id for quick lookup
        comments_by_item: dict[str, list[Comment]] = {}
        for comment in all_comments:
            if comment.itemId not in comments_by_item:
                comments_by_item[comment.itemId] = []
            comments_by_item[comment.itemId].append(comment)

        for item in items:
            # Get author from pre-fetched map
            author = authors_map.get(item.authorId)
            author_name = author.username if author else "Unknown"

            # Item header
            markdown_lines.append(f"## {item.title}")
            markdown_lines.append("")
            markdown_lines.append(f"**Type:** {item.type}")
            markdown_lines.append(f"**Status:** {item.status}")
            markdown_lines.append(f"**Author:** {author_name}")
            markdown_lines.append(f"**Votes:** {item.voteCount}")
            markdown_lines.append(f"**Created:** {item.createdAt.isoformat()}")
            markdown_lines.append("")

            # Description
            markdown_lines.append("### Description")
            markdown_lines.append("")
            markdown_lines.append(item.description)
            markdown_lines.append("")

            # Comments (from pre-fetched and grouped data)
            item_comments = comments_by_item.get(item.item_id, [])
            if item_comments:
                markdown_lines.append("### Comments")
                markdown_lines.append("")

                for comment in item_comments:
                    # Get comment author from pre-fetched map
                    comment_author = authors_map.get(comment.authorId)
                    comment_author_name = (
                        comment_author.username if comment_author else "Unknown"
                    )

                    markdown_lines.append(
                        f"**{comment_author_name}** ({comment.createdAt.isoformat()}):"
                    )
                    markdown_lines.append("")
                    markdown_lines.append(comment.content)
                    markdown_lines.append("")

            markdown_lines.append("---")
            markdown_lines.append("")

        return "\n".join(markdown_lines)
