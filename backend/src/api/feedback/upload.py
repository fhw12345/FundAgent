"""
Feedback image upload endpoints.

This module provides endpoints for uploading feedback images to OSS.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status

from ...core.rate_limiter import RateLimiter
from ...models.feedback import (
    FeedbackImageUploadRequest,
    FeedbackImageUploadResponse,
)
from ...services.oss_service import OSSService
from ..dependencies.feedback_deps import (
    get_current_user_id,
    get_oss_service_dep,
)

logger = structlog.get_logger()


# Rate limiter instance (initialized with Redis from app state)
def get_rate_limiter(request: Request) -> RateLimiter:
    """Get rate limiter from app state."""
    redis_cache = request.app.state.redis
    return RateLimiter(redis_cache)


router = APIRouter()


@router.post("/upload-image", response_model=FeedbackImageUploadResponse)
async def generate_image_upload_url(
    request_data: FeedbackImageUploadRequest,
    user_id: str = Depends(get_current_user_id),
    oss_service: OSSService = Depends(get_oss_service_dep),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> FeedbackImageUploadResponse:
    """
    Generate presigned URL for uploading feedback images to OSS.

    **Authentication**: Required (Bearer token)
    **Rate Limit**: 10 uploads per minute per user

    **Request Body**:
    ```json
    {
      "filename": "screenshot.png",
      "content_type": "image/png"
    }
    ```

    **Response**: Presigned upload URL, object key, and public URL

    **Upload Process**:
    1. Call this endpoint to get presigned URL
    2. Use the presigned URL to upload the file directly from browser (PUT request)
    3. Use the public_url when creating feedback item
    """
    # Rate limiting: 10 image uploads per minute per user
    await rate_limiter.enforce_limit(
        key=f"upload_image:{user_id}",
        limit=10,
        window_seconds=60,
    )

    try:
        # Validate content type
        if not oss_service.validate_image_type(request_data.content_type):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid content type. Allowed types: {', '.join(oss_service.ALLOWED_IMAGE_TYPES.keys())}",
            )

        # Generate unique object key
        object_key = oss_service.generate_object_key(
            prefix="financial-agent/feedbacks",
            filename=request_data.filename,
            user_id=user_id,
        )

        # Generate presigned upload URL (5 minutes expiration)
        presigned_data = oss_service.generate_presigned_upload_url(
            object_key=object_key,
            content_type=request_data.content_type,
            expires_in_seconds=300,
        )

        # Construct public URL for later access
        public_url = (
            f"https://{oss_service.bucket_name}.{oss_service.endpoint}/{object_key}"
        )

        logger.info(
            "Generated image upload URL",
            user_id=user_id,
            filename=request_data.filename,
            object_key=object_key,
        )

        return FeedbackImageUploadResponse(
            upload_url=presigned_data["url"],
            object_key=object_key,
            public_url=public_url,
            expires_in=300,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to generate image upload URL",
            error=str(e),
            user_id=user_id,
            filename=request_data.filename,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate upload URL",
        ) from e
