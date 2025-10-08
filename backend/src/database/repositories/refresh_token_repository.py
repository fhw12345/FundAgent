"""
Refresh token repository for JWT token refresh mechanism.
Handles CRUD operations for refresh_tokens collection.
"""

from datetime import datetime

import structlog
from motor.motor_asyncio import AsyncIOMotorCollection

from ...models.refresh_token import RefreshToken

logger = structlog.get_logger()


class RefreshTokenRepository:
    """Repository for refresh token data access operations."""

    def __init__(self, collection: AsyncIOMotorCollection):
        """
        Initialize refresh token repository.

        Args:
            collection: MongoDB collection for refresh_tokens
        """
        self.collection = collection

    async def ensure_indexes(self):
        """Create indexes for efficient queries."""
        await self.collection.create_index("token_hash", unique=True)
        await self.collection.create_index("user_id")
        await self.collection.create_index("expires_at")
        await self.collection.create_index([("user_id", 1), ("revoked", 1)])
        logger.info("Refresh token indexes created")

    async def create(self, token: RefreshToken) -> RefreshToken:
        """
        Create a new refresh token.

        Args:
            token: Refresh token data

        Returns:
            Created refresh token
        """
        token_dict = token.model_dump()
        await self.collection.insert_one(token_dict)

        logger.info(
            "Refresh token created",
            token_id=token.token_id,
            user_id=token.user_id,
            expires_at=token.expires_at,
        )

        return token

    async def find_by_hash(self, token_hash: str) -> RefreshToken | None:
        """
        Find refresh token by hash.

        Args:
            token_hash: SHA256 hash of the token

        Returns:
            Refresh token if found, None otherwise
        """
        token_dict = await self.collection.find_one({"token_hash": token_hash})

        if not token_dict:
            return None

        token_dict.pop("_id", None)
        return RefreshToken(**token_dict)

    async def find_active_by_user(self, user_id: str) -> list[RefreshToken]:
        """
        Get all active (non-revoked, non-expired) tokens for a user.

        Args:
            user_id: User identifier

        Returns:
            List of active refresh tokens
        """
        now = datetime.utcnow()
        cursor = self.collection.find(
            {
                "user_id": user_id,
                "revoked": False,
                "expires_at": {"$gt": now},
            }
        )

        tokens = []
        async for token_dict in cursor:
            token_dict.pop("_id", None)
            tokens.append(RefreshToken(**token_dict))

        return tokens

    async def update_last_used(self, token_hash: str) -> RefreshToken | None:
        """
        Update last_used_at timestamp for a token.

        Args:
            token_hash: SHA256 hash of the token

        Returns:
            Updated refresh token if found, None otherwise
        """
        result = await self.collection.find_one_and_update(
            {"token_hash": token_hash},
            {"$set": {"last_used_at": datetime.utcnow()}},
            return_document=True,
        )

        if not result:
            return None

        result.pop("_id", None)
        return RefreshToken(**result)

    async def revoke_by_hash(self, token_hash: str) -> bool:
        """
        Revoke a refresh token by hash.

        Args:
            token_hash: SHA256 hash of the token

        Returns:
            True if token was revoked, False if not found
        """
        result = await self.collection.update_one(
            {"token_hash": token_hash},
            {
                "$set": {
                    "revoked": True,
                    "revoked_at": datetime.utcnow(),
                }
            },
        )

        if result.modified_count > 0:
            logger.info("Refresh token revoked", token_hash=token_hash[:16] + "...")
            return True

        return False

    async def revoke_all_for_user(self, user_id: str) -> int:
        """
        Revoke all refresh tokens for a user.

        Args:
            user_id: User identifier

        Returns:
            Number of tokens revoked
        """
        result = await self.collection.update_many(
            {"user_id": user_id, "revoked": False},
            {
                "$set": {
                    "revoked": True,
                    "revoked_at": datetime.utcnow(),
                }
            },
        )

        logger.info(
            "All refresh tokens revoked for user",
            user_id=user_id,
            count=result.modified_count,
        )

        return result.modified_count

    async def cleanup_expired(self) -> int:
        """
        Delete expired tokens (run as cron job).

        Returns:
            Number of tokens deleted
        """
        result = await self.collection.delete_many(
            {"expires_at": {"$lt": datetime.utcnow()}}
        )

        if result.deleted_count > 0:
            logger.info("Expired refresh tokens cleaned up", count=result.deleted_count)

        return result.deleted_count

    async def count_active_by_user(self, user_id: str) -> int:
        """
        Count active refresh tokens for a user.

        Args:
            user_id: User identifier

        Returns:
            Number of active tokens
        """
        now = datetime.utcnow()
        count = await self.collection.count_documents(
            {
                "user_id": user_id,
                "revoked": False,
                "expires_at": {"$gt": now},
            }
        )

        return count
