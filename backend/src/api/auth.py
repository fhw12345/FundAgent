"""
Authentication API endpoints supporting multiple auth methods.
Provides email/phone verification and JWT token generation.
"""

from typing import Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..database.mongodb import MongoDB
from ..database.redis import RedisCache
from ..database.repositories.user_repository import UserRepository
from ..models.user import User
from ..services.auth_service import AuthService

logger = structlog.get_logger()

router = APIRouter(prefix="/api/auth", tags=["authentication"])


# ===== Request/Response Models =====


class SendCodeRequest(BaseModel):
    """Request to send verification code (email or phone)."""

    auth_type: Literal["email", "phone"] = Field(..., description="Authentication type")
    identifier: str = Field(..., description="Email or phone number")


class SendCodeResponse(BaseModel):
    """Response for send code request."""

    message: str
    code: str | None = Field(
        None, description="Verification code (dev mode only)"
    )  # Only returned in dev


class VerifyCodeRequest(BaseModel):
    """Request to verify code and login."""

    auth_type: Literal["email", "phone"] = Field(..., description="Authentication type")
    identifier: str = Field(..., description="Email or phone number")
    code: str = Field(..., description="6-digit verification code")


class LoginResponse(BaseModel):
    """Response for login request."""

    access_token: str
    token_type: str = "bearer"
    user: User


class RegisterRequest(BaseModel):
    """Request to register a new user."""

    email: str = Field(..., description="Email address")
    code: str = Field(..., description="6-digit verification code")
    username: str = Field(..., min_length=3, max_length=20, description="Username")
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")


class LoginRequest(BaseModel):
    """Request to login with username and password."""

    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")


class ResetPasswordRequest(BaseModel):
    """Request to reset password using email verification."""

    email: str = Field(..., description="Email address")
    code: str = Field(..., description="6-digit verification code")
    new_password: str = Field(
        ..., min_length=8, description="New password (min 8 characters)"
    )


# ===== Dependencies =====


def get_mongodb() -> MongoDB:
    """Get MongoDB instance from app state."""
    from ..main import app

    return app.state.mongodb


def get_redis() -> RedisCache:
    """Get Redis instance from app state."""
    from ..main import app

    return app.state.redis


def get_user_repository(mongodb: MongoDB = Depends(get_mongodb)) -> UserRepository:
    """Get user repository instance."""
    users_collection = mongodb.get_collection("users")
    return UserRepository(users_collection)


def get_auth_service(
    user_repo: UserRepository = Depends(get_user_repository),
    redis_cache: RedisCache = Depends(get_redis),
) -> AuthService:
    """Get auth service instance."""
    return AuthService(user_repo, redis_cache)


# ===== Endpoints =====


@router.post("/send-code", response_model=SendCodeResponse)
async def send_verification_code(
    request: SendCodeRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    Send verification code via email or SMS.

    Returns code in response for dev mode.
    In production, code is sent but not returned in response.
    """
    try:
        if request.auth_type == "email":
            await auth_service.send_code_email(request.identifier)
        elif request.auth_type == "phone":
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Phone authentication not yet implemented",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid auth type: {request.auth_type}",
            )

        # In production, do NOT return the code (it should only be sent via email)
        # Code is only visible in email inbox
        return SendCodeResponse(
            message=f"Verification code sent to {request.identifier}",
            code=None,  # Never return code in response for security
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to send verification code", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send verification code: {str(e)}",
        ) from e


@router.post("/verify-code", response_model=LoginResponse)
async def verify_code_and_login(
    request: VerifyCodeRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    Verify code and login user.

    Creates new user if identifier not registered.
    Returns JWT access token for authenticated requests.
    """
    try:
        user, access_token = await auth_service.verify_and_login(
            auth_type=request.auth_type,
            identifier=request.identifier,
            code=request.code,
        )

        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            user=user,
        )

    except NotImplementedError as e:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=str(e),
        ) from e
    except ValueError as e:
        logger.warning("Verification failed", identifier=request.identifier)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error("Login failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed",
        ) from e


@router.post("/register", response_model=LoginResponse)
async def register_user(
    request: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    Register a new user with email verification.

    Flow:
    1. User sends email → receives code
    2. User submits this endpoint with: email, code, username, password
    3. System verifies code, creates user, returns JWT token
    """
    try:
        user, access_token = await auth_service.register_user(
            email=request.email,
            code=request.code,
            username=request.username,
            password=request.password,
        )

        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            user=user,
        )

    except ValueError as e:
        logger.warning("Registration failed", email=request.email, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error("Registration failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed",
        ) from e


@router.post("/login", response_model=LoginResponse)
async def login_with_password(
    request: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    Login with username and password.

    For users who have already registered.
    Returns JWT access token for authenticated requests.
    """
    try:
        user, access_token = await auth_service.login_with_password(
            username=request.username,
            password=request.password,
        )

        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            user=user,
        )

    except ValueError as e:
        logger.warning("Login failed", username=request.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error("Login failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed",
        ) from e


@router.post("/reset-password", response_model=LoginResponse)
async def reset_password(
    request: ResetPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    Reset password using email verification.

    Flow:
    1. User requests password reset (sends email → receives code)
    2. User submits this endpoint with: email, code, new_password
    3. System verifies code, updates password, returns JWT token (auto-login)
    """
    try:
        user, access_token = await auth_service.reset_password(
            email=request.email,
            code=request.code,
            new_password=request.new_password,
        )

        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            user=user,
        )

    except ValueError as e:
        logger.warning("Password reset failed", email=request.email, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error("Password reset failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password reset failed",
        ) from e


@router.get("/me", response_model=User)
async def get_current_user(
    token: str,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    Get current authenticated user.

    Requires Bearer token in Authorization header or token query param.
    """
    user = await auth_service.get_current_user(token)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    return user
