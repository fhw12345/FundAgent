"""
Token service for JWT access/refresh token management.
Implements dual-token authentication with automatic rotation.
"""

import hashlib
import secrets
import uuid
from datetime import timedelta
from typing import Any

import structlog
from jose import JWTError, jwt

from src.core.utils.date_utils import utcnow

from ..core.config import get_settings
from ..database.repositories.refresh_token_repository import RefreshTokenRepository
from ..models.refresh_token import RefreshToken, TokenPair
from ..models.user import User

logger = structlog.get_logger()
settings = get_settings()


class TokenService:
    """Service for JWT access/refresh token management with rotation."""

    # Token configuration
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30  # Short-lived
    REFRESH_TOKEN_EXPIRE_DAYS = 7  # Long-lived

    def __init__(self, refresh_token_repo: RefreshTokenRepository):
        """
        Initialize token service.

        Args:
            refresh_token_repo: Repository for refresh token persistence
        """
        self.refresh_token_repo = refresh_token_repo

    async def create_token_pair(
        self,
        user: User,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> TokenPair:
        """
        Create access token + refresh token pair.

        Args:
            user: User to create tokens for
            user_agent: Browser/device user agent
            ip_address: Client IP address

        Returns:
            Token pair with access and refresh tokens
        """
        # Create short-lived access token
        access_token = self._create_access_token(user)

        # Create long-lived refresh token
        refresh_token_value = secrets.token_urlsafe(32)
        refresh_token_jwt = self._create_refresh_token_jwt(user, refresh_token_value)

        # Store refresh token in database
        token_hash = self._hash_token(refresh_token_value)
        refresh_token = RefreshToken(
            token_id=str(uuid.uuid4()),
            user_id=user.user_id,
            token_hash=token_hash,
            expires_at=utcnow() + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS),
            user_agent=user_agent,
            ip_address=ip_address,
            revoked=False,
            revoked_at=None,
        )

        await self.refresh_token_repo.create(refresh_token)

        logger.info(
            "Token pair created",
            user_id=user.user_id,
            token_id=refresh_token.token_id,
            expires_in_min=self.ACCESS_TOKEN_EXPIRE_MINUTES,
        )

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token_jwt,
            token_type="bearer",
            expires_in=self.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            refresh_expires_in=self.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        )

    def _create_access_token(self, user: User) -> str:
        """
        Create short-lived JWT access token.

        Args:
            user: User to create token for

        Returns:
            JWT access token string
        """
        now = utcnow()
        expire = now + timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)

        payload = {
            "sub": user.user_id,  # Subject (user ID)
            "username": user.username,  # For convenience
            "type": "access",  # Token type
            "exp": expire,  # Expiration
            "iat": now,  # Issued at
            "jti": str(uuid.uuid4()),  # Unique token ID
        }

        token: str = jwt.encode(payload, settings.secret_key, algorithm=self.ALGORITHM)
        return token

    def _create_refresh_token_jwt(self, user: User, token_value: str) -> str:
        """
        Create long-lived JWT refresh token.

        Args:
            user: User to create token for
            token_value: Random token value (will be hashed for DB)

        Returns:
            JWT refresh token string
        """
        now = utcnow()
        expire = now + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS)

        payload = {
            "sub": user.user_id,
            "type": "refresh",
            "token_value": token_value,  # For DB verification
            "exp": expire,
            "iat": now,
            "jti": str(uuid.uuid4()),
        }

        token: str = jwt.encode(payload, settings.secret_key, algorithm=self.ALGORITHM)
        return token

    def _hash_token(self, token: str) -> str:
        """
        Hash token for database storage using SHA256.

        Args:
            token: Plain text token

        Returns:
            SHA256 hash hex string
        """
        return hashlib.sha256(token.encode()).hexdigest()

    async def refresh_access_token(
        self, refresh_token: str, rotate: bool = True
    ) -> TokenPair | str:
        """
        Generate new access token from refresh token.

        Args:
            refresh_token: JWT refresh token
            rotate: Whether to rotate refresh token (default: True)

        Returns:
            New token pair if rotate=True, or just access token if rotate=False

        Raises:
            ValueError: If refresh token invalid/expired/revoked
        """
        try:
            # Decode refresh token JWT
            payload = jwt.decode(
                refresh_token, settings.secret_key, algorithms=[self.ALGORITHM]
            )

            if payload.get("type") != "refresh":
                raise ValueError("Invalid token type")

            token_value = payload.get("token_value")
            if not token_value:
                raise ValueError("Missing token value")

            # Verify token exists in database and is valid
            token_hash = self._hash_token(token_value)
            db_token = await self.refresh_token_repo.find_by_hash(token_hash)

            if not db_token or not db_token.is_valid:
                logger.warning(
                    "Refresh token invalid or revoked",
                    token_hash=token_hash[:16] + "...",
                )
                raise ValueError("Invalid or revoked refresh token")

            # Update last_used_at
            await self.refresh_token_repo.update_last_used(token_hash)

            # Get user (need for creating new tokens)

            # Note: In production, inject UserRepository via __init__
            # For now, we'll need to fetch user_id from token
            user_id = payload["sub"]

            if rotate:
                # Create new token pair (rotation)
                # Note: Need user object - this requires UserRepository
                # For now, create access token with user_id from payload
                access_token = self._create_access_token_from_payload(payload)

                # Create new refresh token
                new_refresh_value = secrets.token_urlsafe(32)
                new_refresh_jwt = self._create_refresh_token_jwt_from_user_id(
                    user_id, new_refresh_value
                )

                # Prepare new refresh token
                new_token_hash = self._hash_token(new_refresh_value)
                new_refresh_token = RefreshToken(
                    token_id=str(uuid.uuid4()),
                    user_id=user_id,
                    token_hash=new_token_hash,
                    expires_at=utcnow()
                    + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS),
                    user_agent=db_token.user_agent,
                    ip_address=db_token.ip_address,
                    revoked=False,
                    revoked_at=None,
                )

                # Atomically revoke old token and create new token (prevents race conditions)
                await self.refresh_token_repo.rotate_token_atomic(
                    token_hash, new_refresh_token
                )

                logger.info(
                    "Access token refreshed with rotation",
                    user_id=user_id,
                    new_token_id=new_refresh_token.token_id,
                )

                return TokenPair(
                    access_token=access_token,
                    refresh_token=new_refresh_jwt,
                    token_type="bearer",
                    expires_in=self.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                    refresh_expires_in=self.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
                )
            else:
                # Just create new access token, keep refresh token
                access_token = self._create_access_token_from_payload(payload)

                logger.info("Access token refreshed without rotation", user_id=user_id)

                return access_token

        except JWTError as e:
            logger.warning("Refresh token JWT decode failed", error=str(e))
            raise ValueError(f"Invalid refresh token: {e}") from e

    def _create_access_token_from_payload(self, refresh_payload: dict[str, Any]) -> str:
        """Create access token from refresh token payload."""
        now = utcnow()
        expire = now + timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)

        payload = {
            "sub": refresh_payload["sub"],
            "username": refresh_payload.get(
                "username", ""
            ),  # May not exist in old tokens
            "type": "access",
            "exp": expire,
            "iat": now,
            "jti": str(uuid.uuid4()),
        }

        token: str = jwt.encode(payload, settings.secret_key, algorithm=self.ALGORITHM)
        return token

    def _create_refresh_token_jwt_from_user_id(
        self, user_id: str, token_value: str
    ) -> str:
        """Create refresh token JWT from user_id."""
        now = utcnow()
        expire = now + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS)

        payload = {
            "sub": user_id,
            "type": "refresh",
            "token_value": token_value,
            "exp": expire,
            "iat": now,
            "jti": str(uuid.uuid4()),
        }

        token: str = jwt.encode(payload, settings.secret_key, algorithm=self.ALGORITHM)
        return token

    def verify_access_token(self, token: str) -> str | None:
        """
        Verify JWT access token and extract user ID.

        Args:
            token: JWT access token

        Returns:
            User ID if valid, None if invalid/expired
        """
        try:
            payload = jwt.decode(
                token, settings.secret_key, algorithms=[self.ALGORITHM]
            )

            # Check token type
            if payload.get("type") != "access":
                logger.warning(
                    "Token type mismatch", expected="access", got=payload.get("type")
                )
                return None

            user_id: str = payload.get("sub")
            if not user_id:
                logger.warning("Access token missing user ID")
                return None

            return user_id

        except JWTError as e:
            logger.debug("Access token verification failed", error=str(e))
            return None

    async def revoke_token(self, refresh_token: str) -> bool:
        """
        Revoke a refresh token.

        Args:
            refresh_token: JWT refresh token to revoke

        Returns:
            True if revoked, False if not found
        """
        try:
            payload = jwt.decode(
                refresh_token, settings.secret_key, algorithms=[self.ALGORITHM]
            )
            token_value = payload.get("token_value")

            if not token_value:
                return False

            token_hash = self._hash_token(token_value)
            revoked = await self.refresh_token_repo.revoke_by_hash(token_hash)

            if revoked:
                logger.info("Refresh token revoked", user_id=payload.get("sub"))

            return revoked

        except JWTError:
            return False

    async def revoke_all_user_tokens(self, user_id: str) -> int:
        """
        Revoke all refresh tokens for a user.

        Args:
            user_id: User identifier

        Returns:
            Number of tokens revoked
        """
        count = await self.refresh_token_repo.revoke_all_for_user(user_id)
        logger.info("All user tokens revoked", user_id=user_id, count=count)
        return count
