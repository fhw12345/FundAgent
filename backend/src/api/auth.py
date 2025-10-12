"""
Authentication API endpoints supporting multiple auth methods.
Provides email/phone verification and JWT token generation.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..database.mongodb import MongoDB
from ..database.redis import RedisCache
from ..database.repositories.refresh_token_repository import RefreshTokenRepository
from ..database.repositories.user_repository import UserRepository
from ..models.refresh_token import TokenPair
from ..models.user import User
from ..services.auth_service import AuthService
from ..services.token_service import TokenService
from .dependencies.auth import get_mongodb, get_user_repository
from .schemas.auth_schemas import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshTokenRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SendCodeRequest,
    SendCodeResponse,
    VerifyCodeRequest,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/api/auth", tags=["authentication"])


# ===== Dependencies =====


def get_redis() -> RedisCache:
    """Get Redis instance from app state."""
    from ..main import app

    redis: RedisCache = app.state.redis
    return redis


def get_refresh_token_repository(
    mongodb: MongoDB = Depends(get_mongodb),
) -> RefreshTokenRepository:
    """Get refresh token repository instance."""
    refresh_tokens_collection = mongodb.get_collection("refresh_tokens")
    return RefreshTokenRepository(refresh_tokens_collection)


def get_token_service(
    refresh_token_repo: RefreshTokenRepository = Depends(get_refresh_token_repository),
) -> TokenService:
    """Get token service instance."""
    return TokenService(refresh_token_repo)


def get_auth_service(
    user_repo: UserRepository = Depends(get_user_repository),
    redis_cache: RedisCache = Depends(get_redis),
) -> AuthService:
    """Get auth service with Redis cache for code verification."""
    return AuthService(user_repo, redis_cache)


# ===== Endpoints =====


@router.post("/send-code", response_model=SendCodeResponse)
async def send_verification_code(
    request: SendCodeRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> SendCodeResponse:
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
    verify_request: VerifyCodeRequest,
    http_request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    token_service: TokenService = Depends(get_token_service),
) -> LoginResponse:
    """
    Verify code and login user.

    Creates new user if identifier not registered.
    Returns JWT token pair for authenticated requests.
    """
    try:
        user, _ = await auth_service.verify_and_login(
            auth_type=verify_request.auth_type,
            identifier=verify_request.identifier,
            code=verify_request.code,
        )

        # Create token pair with device info
        user_agent = http_request.headers.get("user-agent")
        ip_address = http_request.client.host if http_request.client else None

        token_pair = await token_service.create_token_pair(
            user=user,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        return LoginResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            token_type=token_pair.token_type,
            expires_in=token_pair.expires_in,
            refresh_expires_in=token_pair.refresh_expires_in,
            user=user,
        )

    except NotImplementedError as e:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=str(e),
        ) from e
    except ValueError as e:
        logger.warning("Verification failed", identifier=verify_request.identifier)
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
    register_request: RegisterRequest,
    http_request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    token_service: TokenService = Depends(get_token_service),
) -> LoginResponse:
    """
    Register a new user with email verification.

    Flow:
    1. User sends email → receives code
    2. User submits this endpoint with: email, code, username, password
    3. System verifies code, creates user, returns JWT token pair
    """
    try:
        user, _ = await auth_service.register_user(
            email=register_request.email,
            code=register_request.code,
            username=register_request.username,
            password=register_request.password,
        )

        # Create token pair with device info
        user_agent = http_request.headers.get("user-agent")
        ip_address = http_request.client.host if http_request.client else None

        token_pair = await token_service.create_token_pair(
            user=user,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        return LoginResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            token_type=token_pair.token_type,
            expires_in=token_pair.expires_in,
            refresh_expires_in=token_pair.refresh_expires_in,
            user=user,
        )

    except ValueError as e:
        logger.warning(
            "Registration failed", email=register_request.email, error=str(e)
        )
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
    login_request: LoginRequest,
    http_request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    token_service: TokenService = Depends(get_token_service),
) -> LoginResponse:
    """
    Login with username and password.

    For users who have already registered.
    Returns JWT token pair (access + refresh) for authenticated requests.
    """
    try:
        # Authenticate user
        user, _ = await auth_service.login_with_password(
            username=login_request.username,
            password=login_request.password,
        )

        # Create token pair with device info
        user_agent = http_request.headers.get("user-agent")
        ip_address = http_request.client.host if http_request.client else None

        token_pair = await token_service.create_token_pair(
            user=user,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        return LoginResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            token_type=token_pair.token_type,
            expires_in=token_pair.expires_in,
            refresh_expires_in=token_pair.refresh_expires_in,
            user=user,
        )

    except ValueError as e:
        logger.warning("Login failed", username=login_request.username)
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
    reset_request: ResetPasswordRequest,
    http_request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    token_service: TokenService = Depends(get_token_service),
) -> LoginResponse:
    """
    Reset password using email verification.

    Flow:
    1. User requests password reset (sends email → receives code)
    2. User submits this endpoint with: email, code, new_password
    3. System verifies code, updates password, returns JWT token pair (auto-login)
    """
    try:
        user, _ = await auth_service.reset_password(
            email=reset_request.email,
            code=reset_request.code,
            new_password=reset_request.new_password,
        )

        # Create token pair with device info
        user_agent = http_request.headers.get("user-agent")
        ip_address = http_request.client.host if http_request.client else None

        token_pair = await token_service.create_token_pair(
            user=user,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        return LoginResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            token_type=token_pair.token_type,
            expires_in=token_pair.expires_in,
            refresh_expires_in=token_pair.refresh_expires_in,
            user=user,
        )

    except ValueError as e:
        logger.warning("Password reset failed", email=reset_request.email, error=str(e))
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
) -> User:
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


@router.post("/refresh", response_model=TokenPair)
async def refresh_access_token(
    request: RefreshTokenRequest,
    token_service: TokenService = Depends(get_token_service),
) -> TokenPair:
    """
    Refresh access token using refresh token.

    Automatically rotates refresh token for security.
    Returns new token pair.
    """
    try:
        token_pair = await token_service.refresh_access_token(
            refresh_token=request.refresh_token,
            rotate=True,
        )

        if isinstance(token_pair, str):
            # Should not happen with rotate=True, but handle gracefully
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Token rotation failed",
            )

        return token_pair

    except ValueError as e:
        logger.warning("Token refresh failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error("Token refresh failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed",
        ) from e


@router.post("/logout")
async def logout(
    request: LogoutRequest,
    token_service: TokenService = Depends(get_token_service),
) -> dict[str, str]:
    """
    Logout by revoking refresh token.

    Access token will remain valid until expiry (30 min).
    Client should delete both tokens from storage.
    """
    try:
        revoked = await token_service.revoke_token(request.refresh_token)

        if not revoked:
            # Token not found or already revoked - treat as success
            logger.info("Logout attempted with invalid token")

        return {"message": "Logged out successfully"}

    except Exception as e:
        logger.error("Logout failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed",
        ) from e


@router.post("/logout-all")
async def logout_all_devices(
    token: str,
    auth_service: AuthService = Depends(get_auth_service),
    token_service: TokenService = Depends(get_token_service),
) -> dict[str, str]:
    """
    Logout from all devices by revoking all refresh tokens.

    Requires access token to identify user.
    All active refresh tokens will be revoked.
    """
    try:
        # Get current user from access token
        user = await auth_service.get_current_user(token)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )

        # Revoke all refresh tokens for this user
        count = await token_service.revoke_all_user_tokens(user.user_id)

        logger.info("Logout all completed", user_id=user.user_id, tokens_revoked=count)

        return {"message": f"Logged out from all devices ({count} tokens revoked)"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Logout all failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout all failed",
        ) from e
