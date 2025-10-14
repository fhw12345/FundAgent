"""
Credits API endpoints for token-based economy.
"""

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..core.exceptions import ValidationError
from ..database.repositories.user_repository import UserRepository
from ..models.transaction import CreditTransaction
from ..models.user import User
from ..services.credit_service import CreditService
from .dependencies.auth import get_current_user, require_admin
from .dependencies.chat_deps import get_current_user_id
from .dependencies.credit_deps import get_credit_service, get_user_repository

logger = structlog.get_logger()

router = APIRouter(prefix="/api", tags=["credits"])


# ===== Response Models =====


class UserProfileResponse(BaseModel):
    """User profile with credit information."""

    user_id: str
    username: str
    email: str | None
    credits: float
    total_tokens_used: int
    total_credits_spent: float
    created_at: str

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_abc123",
                "username": "alice",
                "email": "alice@example.com",
                "credits": 987.5,
                "total_tokens_used": 12500,
                "total_credits_spent": 62.5,
                "created_at": "2025-10-13T10:00:00Z",
            }
        }


class TransactionHistoryResponse(BaseModel):
    """Paginated transaction history."""

    transactions: list[CreditTransaction]
    pagination: dict[str, Any]

    class Config:
        json_schema_extra = {
            "example": {
                "transactions": [
                    {
                        "transaction_id": "txn_abc123",
                        "chat_id": "chat_xyz",
                        "status": "COMPLETED",
                        "input_tokens": 500,
                        "output_tokens": 1200,
                        "total_tokens": 1700,
                        "actual_cost": 8.5,
                        "created_at": "2025-10-13T10:30:00Z",
                    }
                ],
                "pagination": {
                    "page": 1,
                    "page_size": 20,
                    "total": 45,
                    "total_pages": 3,
                },
            }
        }


class CreditAdjustmentRequest(BaseModel):
    """Request to manually adjust user credits (admin only)."""

    user_id: str = Field(..., description="User to adjust credits for")
    amount: float = Field(
        ..., description="Credits to add (positive) or deduct (negative)"
    )
    reason: str = Field(
        ..., min_length=10, description="Reason for adjustment (audit trail)"
    )


class CreditAdjustmentResponse(BaseModel):
    """Response after credit adjustment."""

    user_id: str
    old_balance: float
    adjustment: float
    new_balance: float
    reason: str


# ===== Endpoints =====


@router.get("/users/me", response_model=UserProfileResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
) -> UserProfileResponse:
    """
    Get current user profile including credit balance.

    **Authentication**: Requires Bearer token in Authorization header.

    **Response:**
    ```json
    {
      "user_id": "user_abc123",
      "username": "alice",
      "email": "alice@example.com",
      "credits": 987.5,
      "total_tokens_used": 12500,
      "total_credits_spent": 62.5,
      "created_at": "2025-10-13T10:00:00Z"
    }
    ```
    """
    logger.info("User profile requested", user_id=current_user.user_id)

    return UserProfileResponse(
        user_id=current_user.user_id,
        username=current_user.username,
        email=current_user.email,
        credits=current_user.credits,
        total_tokens_used=current_user.total_tokens_used,
        total_credits_spent=current_user.total_credits_spent,
        created_at=current_user.created_at.isoformat(),
    )


@router.get("/credits/transactions", response_model=TransactionHistoryResponse)
async def get_transaction_history(
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    user_id: str = Depends(get_current_user_id),
    credit_service: CreditService = Depends(get_credit_service),
) -> TransactionHistoryResponse:
    """
    Get paginated credit transaction history for authenticated user.

    **Authentication**: Requires Bearer token in Authorization header.

    **Query Parameters:**
    - page: Page number (1-indexed, default: 1)
    - page_size: Items per page (1-100, default: 20)
    - status: Optional filter (PENDING, COMPLETED, FAILED)

    **Response:**
    ```json
    {
      "transactions": [...],
      "pagination": {
        "page": 1,
        "page_size": 20,
        "total": 45,
        "total_pages": 3
      }
    }
    ```
    """
    try:
        transactions, total = await credit_service.get_user_transactions(
            user_id=user_id,
            page=page,
            page_size=page_size,
            status=status,
        )

        total_pages = (total + page_size - 1) // page_size

        logger.info(
            "Transaction history retrieved",
            user_id=user_id,
            page=page,
            count=len(transactions),
        )

        return TransactionHistoryResponse(
            transactions=transactions,
            pagination={
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
            },
        )

    except ValidationError as e:
        logger.error("Validation error getting transactions", error=str(e))
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("Failed to get transaction history", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve transaction history",
        ) from e


@router.post("/admin/credits/adjust", response_model=CreditAdjustmentResponse)
async def adjust_user_credits(
    request: CreditAdjustmentRequest,
    current_user: User = Depends(require_admin),
    credit_service: CreditService = Depends(get_credit_service),
    user_repo: UserRepository = Depends(get_user_repository),
) -> CreditAdjustmentResponse:
    """
    Manually adjust user credits (admin only).

    **Authentication**: Requires Bearer token with admin privileges.

    **Request:**
    ```json
    {
      "user_id": "user_abc123",
      "amount": 50.0,
      "reason": "Refund for system error on 2025-10-13"
    }
    ```

    **Response:**
    ```json
    {
      "user_id": "user_abc123",
      "old_balance": 10.5,
      "adjustment": 50.0,
      "new_balance": 60.5,
      "reason": "Refund for system error on 2025-10-13"
    }
    ```
    """
    try:
        # Get user's current balance
        target_user = await user_repo.get_by_id(request.user_id)

        if not target_user:
            raise HTTPException(status_code=404, detail="User not found")

        old_balance = target_user.credits

        # Perform adjustment
        updated_user = await credit_service.adjust_credits_admin(
            user_id=request.user_id,
            amount=request.amount,
            reason=request.reason,
            admin_user_id=current_user.user_id,
        )

        if not updated_user:
            raise HTTPException(
                status_code=500,
                detail="Failed to adjust credits",
            )

        logger.info(
            "Credits adjusted by admin",
            admin_user_id=current_user.user_id,
            target_user_id=request.user_id,
            amount=request.amount,
            reason=request.reason,
        )

        return CreditAdjustmentResponse(
            user_id=request.user_id,
            old_balance=old_balance,
            adjustment=request.amount,
            new_balance=updated_user.credits,
            reason=request.reason,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to adjust credits", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to adjust credits",
        ) from e
