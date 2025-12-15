"""
Feedback comment endpoints.

This module provides endpoints for adding and retrieving comments on feedback items.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status

from ...core.rate_limiter import RateLimiter
from ...models.feedback import (
    Comment,
    CommentCreate,
)
from ...services.feedback_service import FeedbackService
from ..dependencies.feedback_deps import (
    get_current_user_id,
    get_feedback_service,
)

logger = structlog.get_logger()


# Rate limiter instance (initialized with Redis from app state)
def get_rate_limiter(request: Request) -> RateLimiter:
    """Get rate limiter from app state."""
    redis_cache = request.app.state.redis
    return RateLimiter(redis_cache)


router = APIRouter()


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
