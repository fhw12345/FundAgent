"""
Feedback CRUD endpoints.

This module provides core CRUD operations for feedback items including
creation, listing, retrieval, and voting.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status

from ...core.rate_limiter import RateLimiter
from ...models.feedback import (
    FeedbackItem,
    FeedbackItemCreate,
    FeedbackType,
)
from ...services.feedback_service import FeedbackService
from ...services.oss_service import OSSService
from ..dependencies.feedback_deps import (
    get_current_user_id,
    get_current_user_id_optional,
    get_feedback_service,
    get_oss_service_dep,
)

logger = structlog.get_logger()


# Rate limiter instance (initialized with Redis from app state)
def get_rate_limiter(request: Request) -> RateLimiter:
    """Get rate limiter from app state."""
    redis_cache = request.app.state.redis
    return RateLimiter(redis_cache)


router = APIRouter()


def _convert_to_presigned_urls(
    item: FeedbackItem, oss_service: OSSService
) -> FeedbackItem:
    """
    Convert public image URLs to presigned download URLs for private bucket access.

    Args:
        item: Feedback item with public image URLs
        oss_service: OSS service for generating presigned URLs

    Returns:
        Feedback item with presigned image URLs
    """
    if not item.image_urls:
        return item

    presigned_urls = []
    for url in item.image_urls:
        # Extract object key from URL
        # URL format: https://bucket.endpoint/object_key
        try:
            # Parse the object key from the URL
            parts = url.split(f"{oss_service.bucket_name}.{oss_service.endpoint}/")
            if len(parts) == 2:
                object_key = parts[1]
                # Generate presigned download URL (1 hour expiration)
                presigned_url = oss_service.generate_presigned_download_url(
                    object_key, expires_in_seconds=3600
                )
                presigned_urls.append(presigned_url)
            else:
                # Keep original URL if parsing fails
                presigned_urls.append(url)
        except Exception as e:
            logger.warning(
                "Failed to generate presigned URL",
                url=url,
                error=str(e),
            )
            presigned_urls.append(url)

    # Create new item with presigned URLs
    item_dict = item.model_dump()
    item_dict["image_urls"] = presigned_urls
    return FeedbackItem(**item_dict)


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
    oss_service: OSSService = Depends(get_oss_service_dep),
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

        # Convert image URLs to presigned download URLs
        items = [_convert_to_presigned_urls(item, oss_service) for item in items]

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
    oss_service: OSSService = Depends(get_oss_service_dep),
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

        # Convert image URLs to presigned download URLs
        item = _convert_to_presigned_urls(item, oss_service)

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
