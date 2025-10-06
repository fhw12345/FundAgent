"""
Authentication service with modular provider support.
Handles JWT tokens and delegates verification to auth providers (email, SMS, WeChat).
"""

from datetime import datetime, timedelta
from typing import Literal
from jose import JWTError, jwt
import structlog

from ..database.repositories.user_repository import UserRepository
from ..models.user import User, UserCreate
from ..core.config import get_settings
from .auth_providers import EmailAuthProvider

logger = structlog.get_logger()
settings = get_settings()


class AuthService:
    """Service for user authentication and JWT management."""

    # JWT configuration
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

    def __init__(self, user_repository: UserRepository, redis_cache=None):
        """
        Initialize auth service with pluggable providers.

        Args:
            user_repository: Repository for user data access
            redis_cache: Optional Redis cache for storing codes
        """
        self.user_repo = user_repository
        self.redis = redis_cache

        # Initialize auth providers
        self.email_provider = EmailAuthProvider(redis_cache)

    async def send_code_email(self, email: str) -> str:
        """
        Send verification code to email.

        Args:
            email: Email address

        Returns:
            Verification code (for dev/testing)
        """
        code = await self.email_provider.send_verification_code(email)
        return code

    async def verify_and_login(
        self,
        auth_type: Literal["email", "phone", "wechat"],
        identifier: str,
        code: str | None = None,
        wechat_code: str | None = None,
    ) -> tuple[User, str]:
        """
        Verify credentials and login/signup user.

        Args:
            auth_type: Type of authentication (email, phone, wechat)
            identifier: Email, phone number, or WeChat identifier
            code: Verification code (for email/phone)
            wechat_code: WeChat authorization code

        Returns:
            Tuple of (User, access_token)

        Raises:
            ValueError: If verification fails
        """
        if auth_type == "email":
            return await self._verify_email_login(identifier, code)
        elif auth_type == "phone":
            return await self._verify_phone_login(identifier, code)
        elif auth_type == "wechat":
            return await self._verify_wechat_login(wechat_code)
        else:
            raise ValueError(f"Unsupported auth type: {auth_type}")

    async def _verify_email_login(self, email: str, code: str) -> tuple[User, str]:
        """Verify email code and login."""
        # Verify code
        is_valid = await self.email_provider.verify_code(email, code)
        if not is_valid:
            raise ValueError("Invalid verification code")

        logger.info("Email code verified", email=email)

        # Get or create user
        user = await self.user_repo.get_by_email(email)

        if not user:
            # New user - create account
            user_create = UserCreate(email=email)
            user = await self.user_repo.create(user_create)
            logger.info("New user created via email", user_id=user.user_id)
        else:
            # Existing user - update last login
            user = await self.user_repo.update_last_login(user.user_id)
            logger.info("Existing user logged in", user_id=user.user_id)

        # Generate JWT token
        access_token = self.create_access_token(user.user_id)

        return user, access_token

    async def _verify_phone_login(self, phone: str, code: str) -> tuple[User, str]:
        """Verify phone SMS code and login (placeholder for future)."""
        # TODO: Implement SMS provider
        raise NotImplementedError("Phone authentication not yet implemented")

    async def _verify_wechat_login(self, wechat_code: str) -> tuple[User, str]:
        """Verify WeChat OAuth and login (placeholder for future)."""
        # TODO: Implement WeChat OAuth provider
        raise NotImplementedError("WeChat authentication not yet implemented")

    def create_access_token(self, user_id: str) -> str:
        """
        Create JWT access token for user.

        Args:
            user_id: User identifier

        Returns:
            JWT token string
        """
        expires_delta = timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)
        expire = datetime.utcnow() + expires_delta

        # JWT payload
        payload = {
            "sub": user_id,  # Subject (user ID)
            "exp": expire,  # Expiration time
            "iat": datetime.utcnow(),  # Issued at
        }

        # Encode JWT
        token = jwt.encode(payload, settings.secret_key, algorithm=self.ALGORITHM)

        logger.info("Access token created", user_id=user_id, expires_at=expire)

        return token

    def verify_token(self, token: str) -> str | None:
        """
        Verify JWT token and extract user ID.

        Args:
            token: JWT token string

        Returns:
            User ID if valid, None if invalid/expired
        """
        try:
            # Decode JWT
            payload = jwt.decode(token, settings.secret_key, algorithms=[self.ALGORITHM])

            # Extract user ID
            user_id: str = payload.get("sub")

            if not user_id:
                logger.warning("Invalid token: missing user ID")
                return None

            return user_id

        except JWTError as e:
            logger.warning("Token verification failed", error=str(e))
            return None

    async def get_current_user(self, token: str) -> User | None:
        """
        Get current user from JWT token.

        Args:
            token: JWT token string

        Returns:
            User if token valid, None otherwise
        """
        user_id = self.verify_token(token)

        if not user_id:
            return None

        # Fetch user from database
        user = await self.user_repo.get_by_id(user_id)

        if not user:
            logger.warning("Token valid but user not found", user_id=user_id)
            return None

        return user
