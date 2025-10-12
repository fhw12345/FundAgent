"""
Feedback API endpoints for user feature requests and bug reports.

This module provides REST API endpoints for the Feedback & Community Roadmap platform.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse

from ..core.rate_limiter import RateLimiter
from ..models.feedback import (
    Comment,
    CommentCreate,
    FeedbackItem,
    FeedbackItemCreate,
    FeedbackStatusUpdate,
    FeedbackType,
)
from ..services.feedback_export_service import FeedbackExportService
from ..services.feedback_service import FeedbackService
from .dependencies.auth import require_admin
from .dependencies.feedback_deps import (
    get_current_user_id,
    get_current_user_id_optional,
    get_feedback_export_service,
    get_feedback_service,
)

logger = structlog.get_logger()


# Rate limiter instance (initialized with Redis from app state)
def get_rate_limiter(request: Request) -> RateLimiter:
    """Get rate limiter from app state."""
    redis_cache = request.app.state.redis
    return RateLimiter(redis_cache)


router = APIRouter(prefix="/api/feedback", tags=["feedback"])


# ===== Feedback Item Endpoints =====


@router.post("/items", status_code=status.HTTP_201_CREATED, response_model=FeedbackItem)
async def create_feedback_item(
    item: FeedbackItemCreate,
    request: Request,
    user_id: str = Depends(get_current_user_id),
    service: FeedbackService = Depends(get_feedback_service),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> FeedbackItem:
    """
    Create a new feedback item (feature request or bug report).

    **Authentication**: Required (Bearer token)
    **Rate Limit**: 3 feedback items per hour per user

    **Request Body**:
    ```json
    {
      "title": "Add dark mode toggle",
      "description": "## Problem\\nUsers want dark mode...",
      "type": "feature"
    }
    ```

    **Response**: Created feedback item with ID and metadata
    """
    # Rate limiting: 3 feedback items per hour per user (prevent spam)
    await rate_limiter.enforce_limit(
        key=f"create_feedback:{user_id}",
        limit=3,
        window_seconds=3600,
    )

    try:
        created_item = await service.create_item(item, user_id)

        logger.info(
            "Feedback item created via API",
            item_id=created_item.item_id,
            user_id=user_id,
            type=created_item.type,
        )

        return created_item

    except Exception as e:
        logger.error("Failed to create feedback item", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create feedback item",
        ) from e


@router.get("/items", response_model=list[FeedbackItem])
async def list_feedback_items(
    type: FeedbackType | None = None,
    skip: int = 0,
    limit: int = 100,
    user_id: str | None = Depends(get_current_user_id_optional),
    service: FeedbackService = Depends(get_feedback_service),
) -> list[FeedbackItem]:
    """
    List feedback items, optionally filtered by type.

    **Authentication**: Optional (Bearer token for hasVoted field)

    **Query Parameters**:
    - `type`: Filter by 'feature' or 'bug' (optional)
    - `skip`: Number of items to skip for pagination (default: 0)
    - `limit`: Maximum items to return (default: 100, max: 100)

    **Response**: List of feedback items sorted by vote count (descending)
    """
    try:
        # Validate pagination parameters
        if skip < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="skip must be >= 0",
            )
        if limit < 1 or limit > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="limit must be between 1 and 100",
            )

        items = await service.list_items(
            feedback_type=type,
            user_id=user_id,
            skip=skip,
            limit=limit,
        )

        logger.info(
            "Feedback items listed",
            type=type,
            count=len(items),
            user_id=user_id,
        )

        return items

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to list feedback items", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list feedback items",
        ) from e


@router.get("/items/{item_id}", response_model=FeedbackItem)
async def get_feedback_item(
    item_id: str,
    user_id: str | None = Depends(get_current_user_id_optional),
    service: FeedbackService = Depends(get_feedback_service),
) -> FeedbackItem:
    """
    Get detailed view of a feedback item.

    **Authentication**: Optional (Bearer token for hasVoted field)

    **Path Parameters**:
    - `item_id`: Feedback item identifier

    **Response**: Feedback item with full details
    """
    try:
        item = await service.get_item(item_id, user_id)

        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feedback item {item_id} not found",
            )

        logger.info("Feedback item retrieved", item_id=item_id, user_id=user_id)

        return item

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get feedback item", error=str(e), item_id=item_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get feedback item",
        ) from e


# ===== Vote Endpoints =====


@router.post("/items/{item_id}/vote", status_code=status.HTTP_204_NO_CONTENT)
async def vote_feedback_item(
    item_id: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
    service: FeedbackService = Depends(get_feedback_service),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> None:
    """
    Cast a vote for a feedback item (idempotent).

    **Authentication**: Required (Bearer token)
    **Rate Limit**: 10 votes per minute per user

    **Path Parameters**:
    - `item_id`: Feedback item identifier

    **Response**: 204 No Content (success) or 404 if item not found
    """
    # Rate limiting: 10 votes per minute per user
    await rate_limiter.enforce_limit(
        key=f"vote:{user_id}",
        limit=10,
        window_seconds=60,
    )

    try:
        success = await service.vote_item(item_id, user_id)

        if not success:
            # Check if item exists
            item = await service.get_item(item_id)
            if not item:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Feedback item {item_id} not found",
                )
            # Item exists but already voted - still return 204 (idempotent)

        logger.info("Vote cast", item_id=item_id, user_id=user_id)

        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to vote", error=str(e), item_id=item_id, user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cast vote",
        ) from e


@router.delete("/items/{item_id}/vote", status_code=status.HTTP_204_NO_CONTENT)
async def unvote_feedback_item(
    item_id: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
    service: FeedbackService = Depends(get_feedback_service),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> None:
    """
    Remove a vote from a feedback item (idempotent).

    **Authentication**: Required (Bearer token)
    **Rate Limit**: 10 unvotes per minute per user

    **Path Parameters**:
    - `item_id`: Feedback item identifier

    **Response**: 204 No Content (success) or 404 if item not found
    """
    # Rate limiting: 10 unvotes per minute per user (same limit as votes)
    await rate_limiter.enforce_limit(
        key=f"vote:{user_id}",
        limit=10,
        window_seconds=60,
    )

    try:
        success = await service.unvote_item(item_id, user_id)

        if not success:
            # Check if item exists
            item = await service.get_item(item_id)
            if not item:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Feedback item {item_id} not found",
                )
            # Item exists but not voted - still return 204 (idempotent)

        logger.info("Vote removed", item_id=item_id, user_id=user_id)

        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to unvote",
            error=str(e),
            item_id=item_id,
            user_id=user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove vote",
        ) from e


# ===== Admin Endpoints =====


@router.patch("/items/{item_id}/status", response_model=FeedbackItem)
async def update_feedback_status(
    item_id: str,
    status_update: FeedbackStatusUpdate,
    _: None = Depends(require_admin),
    service: FeedbackService = Depends(get_feedback_service),
) -> FeedbackItem:
    """
    Update the status of a feedback item (admin only).

    **Authentication**: Required (Bearer token) + Admin privileges

    **Path Parameters**:
    - `item_id`: Feedback item identifier

    **Request Body**:
    - `status`: New status ("under_consideration", "planned", "in_progress", "completed")

    **Response**: Updated feedback item

    **Permissions**: Admin only (returns 403 for non-admin users)
    """
    try:
        updated_item = await service.update_status(item_id, status_update.status)

        if not updated_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feedback item {item_id} not found",
            )

        logger.info(
            "Status updated by admin", item_id=item_id, new_status=status_update.status
        )

        return updated_item

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update status", error=str(e), item_id=item_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update status",
        ) from e


# ===== Comment Endpoints =====


@router.post(
    "/items/{item_id}/comments",
    status_code=status.HTTP_201_CREATED,
    response_model=Comment,
)
async def add_comment(
    item_id: str,
    comment: CommentCreate,
    request: Request,
    user_id: str = Depends(get_current_user_id),
    service: FeedbackService = Depends(get_feedback_service),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> Comment:
    """
    Add a comment to a feedback item.

    **Authentication**: Required (Bearer token)
    **Rate Limit**: 5 comments per minute per user

    **Path Parameters**:
    - `item_id`: Feedback item identifier

    **Request Body**:
    ```json
    {
      "content": "I agree, this would be very useful!"
    }
    ```

    **Response**: Created comment with ID and metadata
    """
    # Rate limiting: 5 comments per minute per user (prevent spam)
    await rate_limiter.enforce_limit(
        key=f"add_comment:{user_id}",
        limit=5,
        window_seconds=60,
    )

    try:
        created_comment = await service.add_comment(item_id, comment, user_id)

        if not created_comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feedback item {item_id} not found",
            )

        logger.info(
            "Comment added",
            comment_id=created_comment.comment_id,
            item_id=item_id,
            user_id=user_id,
        )

        return created_comment

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to add comment",
            error=str(e),
            item_id=item_id,
            user_id=user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add comment",
        ) from e


@router.get("/items/{item_id}/comments", response_model=list[Comment])
async def get_comments(
    item_id: str,
    service: FeedbackService = Depends(get_feedback_service),
) -> list[Comment]:
    """
    Get all comments for a feedback item.

    **Authentication**: Not required (public endpoint)

    **Path Parameters**:
    - `item_id`: Feedback item identifier

    **Response**: List of comments sorted by creation date (oldest first)
    """
    try:
        comments = await service.get_comments(item_id)

        logger.info("Comments retrieved", item_id=item_id, count=len(comments))

        return comments

    except Exception as e:
        logger.error("Failed to get comments", error=str(e), item_id=item_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get comments",
        ) from e


# ===== Export Endpoint =====


@router.get("/export", response_class=PlainTextResponse)
async def export_feedback(
    _: None = Depends(require_admin),
    export_service: FeedbackExportService = Depends(get_feedback_export_service),
) -> str:
    """
    Generate Markdown snapshot of all feedback items and comments (admin only).

    **Authentication**: Required (Bearer token) + Admin privileges
    **Permissions**: Admin only (returns 403 for non-admin users)

    **Response**: Plain text Markdown document containing all feedback

    **Warning**: This endpoint loads all feedback data into memory. Use with caution
    if feedback volume is large (>10k items).
    """
    try:
        markdown = await export_service.export_all()

        logger.info("Feedback exported by admin")

        return markdown

    except Exception as e:
        logger.error("Failed to export feedback", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export feedback",
        ) from e
