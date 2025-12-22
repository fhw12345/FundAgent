"""
Authentication service with modular provider support.
Handles JWT tokens and delegates verification to auth providers (email, SMS, WeChat).
"""

from datetime import datetime, timedelta
from typing import Any, Literal

import structlog
from jose import JWTError, jwt

from ..core.config import get_settings
from ..database.repositories.user_repository import UserRepository
from ..models.user import User, UserCreate
from .auth_providers import EmailAuthProvider
from .password import verify_password

from src.core.utils.date_utils import utcnow
logger = structlog.get_logger()
settings = get_settings()


class AuthService:
    """Service for user authentication and JWT management."""

    # JWT configuration
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

    def __init__(self, user_repository: UserRepository, redis_cache: Any = None):
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
            if not code:
                raise ValueError("Verification code required for email authentication")
            return await self._verify_email_login(identifier, code)
        elif auth_type == "phone":
            if not code:
                raise ValueError("Verification code required for phone authentication")
            return await self._verify_phone_login(identifier, code)
        elif auth_type == "wechat":
            if not wechat_code:
                raise ValueError("WeChat code required for WeChat authentication")
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
            # New user - create account with auto-generated username
            # Username will be generated from email (e.g., user@163.com → User_163)
            username = email.split("@")[0].replace(".", "_")[:20]
            user_create = UserCreate(
                email=email,
                username=username,
                password=None,
                phone_number=None,
                wechat_openid=None,
            )
            user = await self.user_repo.create(user_create)
            logger.info("New user created via email", user_id=user.user_id)
        else:
            # Existing user - update last login
            updated_user = await self.user_repo.update_last_login(user.user_id)
            if not updated_user:
                raise ValueError("User not found after login")
            user = updated_user
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

    async def register_user(
        self, email: str, code: str, username: str, password: str
    ) -> tuple[User, str]:
        """
        Register a new user with email verification.

        Flow:
        1. Verify email code
        2. Check if email/username already exists
        3. Create user with username and password
        4. Mark email as verified
        5. Generate JWT token

        Args:
            email: Email address
            code: Email verification code
            username: Desired username (must be unique)
            password: Plain text password (will be hashed)

        Returns:
            Tuple of (User, access_token)

        Raises:
            ValueError: If verification fails or user already exists
        """
        # Verify email code
        is_valid = await self.email_provider.verify_code(email, code)
        if not is_valid:
            raise ValueError("Invalid or expired verification code")

        logger.info("Email code verified for registration", email=email)

        # Check if email or username already exists
        existing_user_by_email = await self.user_repo.get_by_email(email)
        if existing_user_by_email:
            raise ValueError("Email already registered")

        existing_user_by_username = await self.user_repo.get_by_username(username)
        if existing_user_by_username:
            raise ValueError("Username already taken")

        # Create new user
        user_create = UserCreate(
            email=email,
            username=username,
            password=password,  # Will be hashed by repo
            phone_number=None,
            wechat_openid=None,
        )
        user = await self.user_repo.create(user_create)

        # Mark email as verified (update in DB)
        await self.user_repo.collection.update_one(
            {"user_id": user.user_id}, {"$set": {"email_verified": True}}
        )
        user.email_verified = True

        logger.info("New user registered", user_id=user.user_id, username=username)

        # Generate JWT token
        access_token = self.create_access_token(user.user_id)

        return user, access_token

    async def login_with_password(
        self, username: str, password: str
    ) -> tuple[User, str]:
        """
        Login with username and password.

        Args:
            username: Username
            password: Plain text password

        Returns:
            Tuple of (User, access_token)

        Raises:
            ValueError: If credentials invalid
        """
        # Get user by username
        user = await self.user_repo.get_by_username(username)

        if not user:
            raise ValueError("Invalid username or password")

        # Check if user has password set
        if not user.password_hash:
            raise ValueError(
                "Password not set for this account. Please use email login."
            )

        # Verify password
        is_valid = verify_password(password, user.password_hash)
        if not is_valid:
            raise ValueError("Invalid username or password")

        # Update last login
        updated_user = await self.user_repo.update_last_login(user.user_id)
        if not updated_user:
            raise ValueError("User not found after login")

        logger.info("User logged in with password", user_id=updated_user.user_id)

        # Generate JWT token
        access_token = self.create_access_token(updated_user.user_id)

        return updated_user, access_token

    async def reset_password(
        self, email: str, code: str, new_password: str
    ) -> tuple[User, str]:
        """
        Reset user password using email verification.

        Flow:
        1. Verify email code
        2. Find user by email
        3. Update password hash
        4. Generate JWT token for auto-login

        Args:
            email: Email address
            code: Email verification code
            new_password: New password (will be hashed)

        Returns:
            Tuple of (User, access_token)

        Raises:
            ValueError: If verification fails or user not found
        """
        # Verify email code
        is_valid = await self.email_provider.verify_code(email, code)
        if not is_valid:
            raise ValueError("Invalid or expired verification code")

        logger.info("Email code verified for password reset", email=email)

        # Get user by email
        user = await self.user_repo.get_by_email(email)
        if not user:
            raise ValueError("No account found with this email address")

        # Hash new password
        from .password import hash_password

        new_password_hash = hash_password(new_password)

        # Update password in database
        await self.user_repo.collection.update_one(
            {"user_id": user.user_id}, {"$set": {"password_hash": new_password_hash}}
        )
        user.password_hash = new_password_hash

        logger.info("Password reset successful", user_id=user.user_id)

        # Generate JWT token for auto-login after reset
        access_token = self.create_access_token(user.user_id)

        return user, access_token

    def create_access_token(self, user_id: str) -> str:
        """
        Create JWT access token for user.

        Args:
            user_id: User identifier

        Returns:
            JWT token string
        """
        expires_delta = timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)
        expire = utcnow() + expires_delta

        # JWT payload
        payload = {
            "sub": user_id,  # Subject (user ID)
            "exp": expire,  # Expiration time
            "iat": utcnow(),  # Issued at
        }

        # Encode JWT
        token: str = jwt.encode(payload, settings.secret_key, algorithm=self.ALGORITHM)

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
            payload = jwt.decode(
                token, settings.secret_key, algorithms=[self.ALGORITHM]
            )

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
