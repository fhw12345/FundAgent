"""
Credit transaction repository for credit economy management.
Handles CRUD operations for transactions collection.
"""

import uuid
from datetime import datetime, timedelta
from typing import Any

import structlog
from motor.motor_asyncio import AsyncIOMotorCollection
from pymongo import ReturnDocument

from ...models.transaction import CreditTransaction, TransactionCreate

logger = structlog.get_logger()


class TransactionRepository:
    """Repository for credit transaction data access operations."""

    def __init__(self, collection: AsyncIOMotorCollection):
        """
        Initialize transaction repository.

        Args:
            collection: MongoDB collection for transactions
        """
        self.collection = collection

    async def ensure_indexes(self) -> None:
        """
        Create indexes for optimal query performance.
        Called during application startup.
        """
        await self.collection.create_index("transaction_id", unique=True)
        await self.collection.create_index("user_id")
        await self.collection.create_index([("status", 1), ("created_at", 1)])
        await self.collection.create_index("chat_id")

        logger.info("Transaction indexes created")

    async def create_pending(
        self, transaction_create: TransactionCreate
    ) -> CreditTransaction:
        """
        Create a new PENDING transaction (safety net before LLM call).

        Args:
            transaction_create: Transaction creation data

        Returns:
            Created transaction with PENDING status
        """
        transaction_id = f"txn_{uuid.uuid4().hex[:12]}"

        transaction = CreditTransaction(
            transaction_id=transaction_id,
            user_id=transaction_create.user_id,
            chat_id=transaction_create.chat_id,
            message_id=None,  # Will be set when message is saved
            status="PENDING",
            estimated_cost=transaction_create.estimated_cost,
            input_tokens=None,
            output_tokens=None,
            total_tokens=None,
            actual_cost=None,
            created_at=datetime.utcnow(),
            completed_at=None,
            model=transaction_create.model,
            request_type=transaction_create.request_type,
        )

        # Convert to dict for MongoDB
        transaction_dict = transaction.model_dump()

        # Insert into database
        await self.collection.insert_one(transaction_dict)

        logger.info(
            "Transaction created",
            transaction_id=transaction_id,
            user_id=transaction_create.user_id,
            estimated_cost=transaction_create.estimated_cost,
        )

        return transaction

    async def get_by_id(self, transaction_id: str) -> CreditTransaction | None:
        """
        Get transaction by ID.

        Args:
            transaction_id: Transaction identifier

        Returns:
            Transaction if found, None otherwise
        """
        transaction_dict = await self.collection.find_one(
            {"transaction_id": transaction_id}
        )

        if not transaction_dict:
            return None

        # Remove MongoDB _id field
        transaction_dict.pop("_id", None)

        return CreditTransaction(**transaction_dict)

    async def complete_transaction(
        self,
        transaction_id: str,
        message_id: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        actual_cost: float,
        session: Any = None,
    ) -> CreditTransaction | None:
        """
        Mark transaction as COMPLETED with actual costs.
        Uses atomic update with status condition to prevent race conditions.

        Args:
            transaction_id: Transaction identifier
            message_id: Assistant message identifier
            input_tokens: Input tokens (prompt + history)
            output_tokens: Output tokens (LLM response)
            total_tokens: Total tokens consumed
            actual_cost: Actual cost calculated
            session: Optional MongoDB session for transactions

        Returns:
            Updated transaction if found and was PENDING, None otherwise
        """
        result = await self.collection.find_one_and_update(
            {"transaction_id": transaction_id, "status": "PENDING"},  # Only if PENDING
            {
                "$set": {
                    "status": "COMPLETED",
                    "message_id": message_id,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                    "actual_cost": actual_cost,
                    "completed_at": datetime.utcnow(),
                }
            },
            return_document=ReturnDocument.AFTER,
            session=session,
        )

        if not result:
            logger.warning(
                "Transaction completion failed - not found or not PENDING",
                transaction_id=transaction_id,
            )
            return None

        # Remove MongoDB _id field
        result.pop("_id", None)

        logger.info(
            "Transaction completed",
            transaction_id=transaction_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            actual_cost=actual_cost,
        )

        return CreditTransaction(**result)

    async def fail_transaction(
        self, transaction_id: str, session: Any = None
    ) -> CreditTransaction | None:
        """
        Mark transaction as FAILED (no charge to user).

        Args:
            transaction_id: Transaction identifier
            session: Optional MongoDB session for transactions

        Returns:
            Updated transaction if found and was PENDING, None otherwise
        """
        result = await self.collection.find_one_and_update(
            {"transaction_id": transaction_id, "status": "PENDING"},
            {"$set": {"status": "FAILED", "completed_at": datetime.utcnow()}},
            return_document=ReturnDocument.AFTER,
            session=session,
        )

        if not result:
            logger.warning(
                "Transaction failure marking failed - not found or not PENDING",
                transaction_id=transaction_id,
            )
            return None

        # Remove MongoDB _id field
        result.pop("_id", None)

        logger.info("Transaction marked as failed", transaction_id=transaction_id)

        return CreditTransaction(**result)

    async def find_stuck_transactions(
        self, age_minutes: int = 10
    ) -> list[CreditTransaction]:
        """
        Find transactions stuck in PENDING status for reconciliation.

        Args:
            age_minutes: Minimum age in minutes to consider stuck

        Returns:
            List of stuck transactions
        """
        cutoff_time = datetime.utcnow() - timedelta(minutes=age_minutes)

        cursor = self.collection.find(
            {"status": "PENDING", "created_at": {"$lt": cutoff_time}}
        )

        transactions = []
        async for transaction_dict in cursor:
            transaction_dict.pop("_id", None)
            transactions.append(CreditTransaction(**transaction_dict))

        if transactions:
            logger.info(
                "Found stuck transactions",
                count=len(transactions),
                age_minutes=age_minutes,
            )

        return transactions

    async def get_user_transactions(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
    ) -> tuple[list[CreditTransaction], int]:
        """
        Get paginated transaction history for a user.

        Args:
            user_id: User identifier
            page: Page number (1-indexed)
            page_size: Number of transactions per page
            status: Optional status filter (PENDING, COMPLETED, FAILED)

        Returns:
            Tuple of (transactions list, total count)
        """
        # Build query filter
        query_filter = {"user_id": user_id}
        if status:
            query_filter["status"] = status

        # Get total count
        total = await self.collection.count_documents(query_filter)

        # Get paginated results
        skip = (page - 1) * page_size
        cursor = (
            self.collection.find(query_filter)
            .sort("created_at", -1)  # Newest first
            .skip(skip)
            .limit(page_size)
        )

        transactions = []
        async for transaction_dict in cursor:
            transaction_dict.pop("_id", None)
            transactions.append(CreditTransaction(**transaction_dict))

        logger.info(
            "Fetched user transactions",
            user_id=user_id,
            page=page,
            page_size=page_size,
            count=len(transactions),
            total=total,
        )

        return transactions, total

    async def get_by_message_id(self, message_id: str) -> CreditTransaction | None:
        """
        Get transaction by message ID.

        Args:
            message_id: Message identifier

        Returns:
            Transaction if found, None otherwise
        """
        transaction_dict = await self.collection.find_one({"message_id": message_id})

        if not transaction_dict:
            return None

        # Remove MongoDB _id field
        transaction_dict.pop("_id", None)

        return CreditTransaction(**transaction_dict)
