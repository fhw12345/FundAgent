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

    async def ensure_indexes(self) -> None:
        """
        Create indexes for efficient queries and TTL cleanup.

        For Cosmos DB compatibility, this method checks if indexes already exist
        before creating them, and handles the case where unique indexes cannot
        be created on collections with existing documents.
        """
        try:
            # Get existing indexes
            existing_indexes = await self.collection.index_information()
            index_names = set(existing_indexes.keys())

            # Create token_hash unique index if it doesn't exist
            if "token_hash_1" not in index_names:
                try:
                    await self.collection.create_index("token_hash", unique=True)
                    logger.info("Created unique index on token_hash")
                except Exception as e:
                    # Cosmos DB: Cannot create unique index on non-empty collection
                    # Log warning and continue - index will be created on next deployment
                    logger.warning(
                        "Failed to create unique index on token_hash",
                        error=str(e),
                        recommendation="Clear collection or create index before inserting documents",
                    )

            # Create other indexes (these can be created on non-empty collections)
            if "user_id_1" not in index_names:
                await self.collection.create_index("user_id")
                logger.info("Created index on user_id")

            if "expires_at_1" not in index_names:
                await self.collection.create_index("expires_at")
                logger.info("Created index on expires_at")

            if "user_id_1_revoked_1" not in index_names:
                await self.collection.create_index([("user_id", 1), ("revoked", 1)])
                logger.info("Created compound index on user_id + revoked")

            # TTL index: Auto-delete revoked tokens after 30 days
            # Only affects documents where revoked_at is set (active tokens have revoked_at=null)
            if "revoked_at_1" not in index_names:
                await self.collection.create_index(
                    "revoked_at",
                    expireAfterSeconds=30 * 24 * 60 * 60,  # 30 days = 2,592,000 seconds
                )
                logger.info("Created TTL index on revoked_at (30 days)")

            logger.info("Refresh token indexes ensured")

        except Exception as e:
            # Log error but don't fail startup
            logger.error("Failed to ensure refresh token indexes", error=str(e))

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

    async def rotate_token_atomic(
        self, old_token_hash: str, new_token: RefreshToken
    ) -> RefreshToken:
        """
        Atomically revoke old token and create new token using MongoDB transaction.
        This prevents race conditions where a token could be revoked but new token fails to create.

        Falls back to non-atomic operations if transactions not supported (standalone MongoDB).
        Production (Cosmos DB) supports transactions; local dev (standalone) uses fallback.

        Args:
            old_token_hash: SHA256 hash of the old token to revoke
            new_token: New refresh token to create

        Returns:
            Created refresh token

        Raises:
            ValueError: If old token not found or already revoked
        """
        # Get the client from collection database to start session
        client = self.collection.database.client

        try:
            # Try transactional approach (Cosmos DB, replica sets)
            async with await client.start_session() as session:
                async with session.start_transaction():
                    # 1. Verify old token exists and is valid
                    old_token_doc = await self.collection.find_one(
                        {"token_hash": old_token_hash}, session=session
                    )

                    if not old_token_doc:
                        raise ValueError("Old refresh token not found")

                    if old_token_doc.get("revoked", False):
                        raise ValueError("Old refresh token already revoked")

                    # 2. Revoke old token
                    await self.collection.update_one(
                        {"token_hash": old_token_hash},
                        {
                            "$set": {
                                "revoked": True,
                                "revoked_at": datetime.utcnow(),
                            }
                        },
                        session=session,
                    )

                    # 3. Create new token
                    new_token_dict = new_token.model_dump()
                    await self.collection.insert_one(new_token_dict, session=session)

                    logger.info(
                        "Token rotation completed atomically (transactional)",
                        old_token_hash=old_token_hash[:16] + "...",
                        new_token_id=new_token.token_id,
                        user_id=new_token.user_id,
                    )

                    # Transaction auto-commits on successful context exit
                    return new_token

        except Exception as transaction_error:
            # If transactions not supported (standalone MongoDB), fall back to non-atomic
            error_msg = str(transaction_error).lower()
            if "transaction" in error_msg or "replica" in error_msg:
                logger.warning(
                    "MongoDB transactions not supported, using non-atomic fallback",
                    error=str(transaction_error),
                    recommendation="Use replica set or Cosmos DB for atomic operations",
                )

                # Fallback: Non-atomic operations (best effort)
                # 1. Verify old token exists and is valid
                old_token_doc = await self.collection.find_one(
                    {"token_hash": old_token_hash}
                )

                if not old_token_doc:
                    raise ValueError("Old refresh token not found") from None

                if old_token_doc.get("revoked", False):
                    raise ValueError("Old refresh token already revoked") from None

                # 2. Revoke old token
                await self.collection.update_one(
                    {"token_hash": old_token_hash},
                    {
                        "$set": {
                            "revoked": True,
                            "revoked_at": datetime.utcnow(),
                        }
                    },
                )

                # 3. Create new token
                new_token_dict = new_token.model_dump()
                await self.collection.insert_one(new_token_dict)

                logger.info(
                    "Token rotation completed (non-atomic fallback)",
                    old_token_hash=old_token_hash[:16] + "...",
                    new_token_id=new_token.token_id,
                    user_id=new_token.user_id,
                )

                return new_token
            else:
                # Other errors (token validation, etc.) - propagate
                logger.error(
                    "Token rotation failed",
                    error=str(transaction_error),
                    old_token_hash=old_token_hash[:16] + "...",
                )
                raise

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
        modified_count: int = result.modified_count

        return modified_count

    async def cleanup_expired(self) -> int:
        """
        Delete expired tokens (run as cron job).

        Returns:
            Number of tokens deleted
        """
        result = await self.collection.delete_many(
            {"expires_at": {"$lt": datetime.utcnow()}}
        )
        deleted_count: int = result.deleted_count

        if deleted_count > 0:
            logger.info("Expired refresh tokens cleaned up", count=deleted_count)

        return deleted_count

    async def count_active_by_user(self, user_id: str) -> int:
        """
        Count active refresh tokens for a user.

        Args:
            user_id: User identifier

        Returns:
            Number of active tokens
        """
        now = datetime.utcnow()
        count: int = await self.collection.count_documents(
            {
                "user_id": user_id,
                "revoked": False,
                "expires_at": {"$gt": now},
            }
        )

        return count
