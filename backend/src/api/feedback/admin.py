"""
Feedback admin endpoints.

This module provides admin-only endpoints for managing feedback items,
including status updates and data exports.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse

from ...models.feedback import (
    FeedbackItem,
    FeedbackStatusUpdate,
)
from ...services.feedback_export_service import FeedbackExportService
from ...services.feedback_service import FeedbackService
from ..dependencies.auth import require_admin
from ..dependencies.feedback_deps import (
    get_feedback_export_service,
    get_feedback_service,
)

logger = structlog.get_logger()


router = APIRouter()


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
