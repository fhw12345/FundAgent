"""
Dependency injection for feedback platform endpoints.
"""

from fastapi import Depends, Header, HTTPException, status

from ...database.mongodb import MongoDB
from ...database.repositories.comment_repository import CommentRepository
from ...database.repositories.feedback_repository import FeedbackRepository
from ...database.repositories.user_repository import UserRepository
from ...services.auth_service import AuthService
from ...services.feedback_export_service import FeedbackExportService
from ...services.feedback_service import FeedbackService


def get_mongodb() -> MongoDB:
    """Get MongoDB instance from app state."""
    from ...main import app

    return app.state.mongodb


def get_feedback_repository(
    mongodb: MongoDB = Depends(get_mongodb),
) -> FeedbackRepository:
    """Get feedback repository instance."""
    feedback_collection = mongodb.get_collection("feedback_items")
    return FeedbackRepository(feedback_collection)


def get_comment_repository(
    mongodb: MongoDB = Depends(get_mongodb),
) -> CommentRepository:
    """Get comment repository instance."""
    comments_collection = mongodb.get_collection("comments")
    return CommentRepository(comments_collection)


def get_user_repository(mongodb: MongoDB = Depends(get_mongodb)) -> UserRepository:
    """Get user repository instance."""
    users_collection = mongodb.get_collection("users")
    return UserRepository(users_collection)


def get_feedback_service(
    feedback_repo: FeedbackRepository = Depends(get_feedback_repository),
    comment_repo: CommentRepository = Depends(get_comment_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    mongodb: MongoDB = Depends(get_mongodb),
) -> FeedbackService:
    """Get feedback service instance."""
    return FeedbackService(feedback_repo, comment_repo, user_repo, mongodb)


def get_feedback_export_service(
    feedback_repo: FeedbackRepository = Depends(get_feedback_repository),
    comment_repo: CommentRepository = Depends(get_comment_repository),
    user_repo: UserRepository = Depends(get_user_repository),
) -> FeedbackExportService:
    """Get feedback export service instance."""
    return FeedbackExportService(feedback_repo, comment_repo, user_repo)


def get_auth_service(
    user_repo: UserRepository = Depends(get_user_repository),
) -> AuthService:
    """Get auth service for token verification."""
    return AuthService(user_repo, redis_cache=None)


async def get_current_user_id(
    authorization: str | None = Header(None),
    auth_service: AuthService = Depends(get_auth_service),
) -> str:
    """
    Extract and verify user_id from JWT token in Authorization header.

    Args:
        authorization: Authorization header (Bearer token)
        auth_service: Auth service for token verification

    Returns:
        User ID from token

    Raises:
        HTTPException: If token is missing, invalid, or expired
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract token from "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Expected: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]

    # Verify token and extract user_id
    user_id = auth_service.verify_token(token)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user_id


async def get_current_user_id_optional(
    authorization: str | None = Header(None),
    auth_service: AuthService = Depends(get_auth_service),
) -> str | None:
    """
    Extract user_id from JWT token if present (optional authentication).

    Args:
        authorization: Authorization header (Bearer token), optional
        auth_service: Auth service for token verification

    Returns:
        User ID from token if valid, None if not provided or invalid
    """
    if not authorization:
        return None

    # Extract token from "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    token = parts[1]

    # Verify token and extract user_id
    user_id = auth_service.verify_token(token)

    return user_id
