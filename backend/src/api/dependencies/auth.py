"""
Shared authentication dependencies for all API endpoints.
"""

import structlog
from fastapi import Depends, Header, HTTPException, status

from ...database.mongodb import MongoDB
from ...database.repositories.user_repository import UserRepository
from ...models.user import User
from ...services.auth_service import AuthService

logger = structlog.get_logger()


def get_mongodb() -> MongoDB:
    """Get MongoDB instance from app state."""
    from ...main import app

    mongodb: MongoDB = app.state.mongodb
    return mongodb


def get_user_repository(mongodb: MongoDB = Depends(get_mongodb)) -> UserRepository:
    """Get user repository instance."""
    users_collection = mongodb.get_collection("users")
    return UserRepository(users_collection)


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


async def get_current_user(
    user_id: str = Depends(get_current_user_id),
    user_repo: UserRepository = Depends(get_user_repository),
) -> User:
    """
    Get full User object for the current authenticated user.

    Args:
        user_id: User ID from JWT token (via get_current_user_id)
        user_repo: User repository for database queries

    Returns:
        Full User object with all fields

    Raises:
        HTTPException: If user not found (401)
    """
    user = await user_repo.get_by_id(user_id)

    if not user:
        logger.warning("User not found", user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> None:
    """
    Require admin privileges for endpoint access.

    Args:
        current_user: Current authenticated user (via get_current_user)

    Raises:
        HTTPException: If user is not admin (403 Forbidden)

    Usage:
        @router.get("/admin/endpoint")
        async def admin_endpoint(
            _: None = Depends(require_admin),  # Admin check
            current_user: User = Depends(get_current_user),  # Get user data
        ):
            # Only admins can reach here
            pass
    """
    if not current_user.admin:
        logger.warning(
            "Non-admin user attempted admin access",
            user_id=current_user.user_id,
            username=current_user.username,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
