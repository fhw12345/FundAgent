"""
Credit service for token-based economy.
Business logic layer coordinating credit operations and transactions.
"""

import structlog

from ..core.config import Settings
from ..core.exceptions import ValidationError
from ..core.model_config import calculate_cost_in_credits, get_model_config
from ..database.mongodb import MongoDB
from ..database.repositories.transaction_repository import TransactionRepository
from ..database.repositories.user_repository import UserRepository
from ..models.transaction import CreditTransaction, TransactionCreate
from ..models.user import User

logger = structlog.get_logger()

# Constants
MIN_CREDIT_THRESHOLD = 10.0  # Minimum credits required to make a request


class CreditService:
    """Service for credit management and billing operations."""

    def __init__(
        self,
        user_repo: UserRepository,
        transaction_repo: TransactionRepository,
        mongodb: MongoDB,
        settings: Settings,
    ):
        """
        Initialize credit service.

        Args:
            user_repo: Repository for user data access
            transaction_repo: Repository for transaction data access
            mongodb: MongoDB connection for transactions
            settings: Application settings
        """
        self.user_repo = user_repo
        self.transaction_repo = transaction_repo
        self.mongodb = mongodb
        self.settings = settings

    @staticmethod
    def calculate_cost(
        input_tokens: int,
        output_tokens: int,
        model_id: str = "qwen-plus",
        thinking_enabled: bool = False,
    ) -> float:
        """
        Calculate credit cost based on model-specific pricing.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model_id: Model identifier (default: qwen-plus)
            thinking_enabled: Whether thinking mode is enabled

        Returns:
            Credit cost (rounded to 2 decimals)
        """
        model_config = get_model_config(model_id)

        return calculate_cost_in_credits(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model_config=model_config,
            thinking_enabled=thinking_enabled,
        )

    async def check_balance(self, user_id: str, estimated_cost: float) -> bool:
        """
        Check if user has sufficient credits for a request.

        Special handling for portfolio_agent:
        - Always returns True (no blocking)
        - Still tracks usage for monitoring

        Args:
            user_id: User identifier
            estimated_cost: Estimated cost in credits

        Returns:
            True if user has sufficient balance

        Raises:
            ValidationError: If estimated cost is invalid
        """
        if estimated_cost < 0:
            raise ValidationError(
                "Estimated cost cannot be negative", cost=estimated_cost
            )

        # Special handling for portfolio_agent - never block
        if user_id == "portfolio_agent":
            logger.info(
                "Portfolio agent bypass - credits checked but not blocked",
                user_id=user_id,
                estimated_cost=estimated_cost,
            )
            return True  # Always allow

        user = await self.user_repo.get_by_id(user_id)

        if not user:
            logger.error("User not found for balance check", user_id=user_id)
            return False

        has_sufficient = user.credits >= MIN_CREDIT_THRESHOLD

        if not has_sufficient:
            logger.warning(
                "Insufficient credits",
                user_id=user_id,
                balance=user.credits,
                threshold=MIN_CREDIT_THRESHOLD,
            )

        return has_sufficient

    async def create_pending_transaction(
        self,
        user_id: str,
        chat_id: str,
        estimated_cost: float,
        model: str = "qwen-plus",
    ) -> CreditTransaction:
        """
        Create a PENDING transaction (safety net before LLM call).

        Args:
            user_id: User identifier
            chat_id: Chat context
            estimated_cost: Estimated cost in credits
            model: Model identifier (default: qwen-plus)

        Returns:
            Created transaction with PENDING status
        """
        transaction_create = TransactionCreate(
            user_id=user_id,
            chat_id=chat_id,
            estimated_cost=estimated_cost,
            model=model,
            request_type="chat",
        )

        transaction = await self.transaction_repo.create_pending(transaction_create)

        logger.info(
            "Pending transaction created",
            transaction_id=transaction.transaction_id,
            user_id=user_id,
            model=model,
            estimated_cost=estimated_cost,
        )

        return transaction

    async def complete_transaction_with_deduction(
        self,
        transaction_id: str,
        message_id: str,
        input_tokens: int,
        output_tokens: int,
        model: str = "qwen-plus",
        thinking_enabled: bool = False,
    ) -> tuple[CreditTransaction | None, User | None]:
        """
        Complete transaction and deduct credits atomically.

        Uses MongoDB transactions to ensure:
        - Credits deducted + Transaction marked COMPLETED (both or neither)
        - No double-charging
        - No credit loss

        Args:
            transaction_id: Transaction identifier
            message_id: Assistant message identifier
            input_tokens: Input tokens (prompt + history)
            output_tokens: Output tokens (LLM response)
            model: Model identifier
            thinking_enabled: Whether thinking mode was used

        Returns:
            Tuple of (updated transaction, updated user) or (None, None) if failed
        """
        total_tokens = input_tokens + output_tokens
        actual_cost = self.calculate_cost(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model_id=model,
            thinking_enabled=thinking_enabled,
        )

        # Get transaction to find user_id
        transaction = await self.transaction_repo.get_by_id(transaction_id)

        if not transaction:
            logger.error("Transaction not found", transaction_id=transaction_id)
            return None, None

        if transaction.status != "PENDING":
            logger.warning(
                "Transaction not PENDING - already processed",
                transaction_id=transaction_id,
                status=transaction.status,
            )
            return None, None

        # Try MongoDB transaction (for Cosmos DB in prod)
        try:
            if not self.mongodb.client:
                logger.error("MongoDB client not available")
                return None, None

            async with await self.mongodb.client.start_session() as session:
                async with session.start_transaction():
                    # 1. Complete transaction
                    updated_transaction = (
                        await self.transaction_repo.complete_transaction(
                            transaction_id=transaction_id,
                            message_id=message_id,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            total_tokens=total_tokens,
                            actual_cost=actual_cost,
                            session=session,
                        )
                    )

                    if not updated_transaction:
                        logger.error(
                            "Failed to complete transaction",
                            transaction_id=transaction_id,
                        )
                        return None, None

                    # 2. Deduct credits
                    updated_user = await self.user_repo.deduct_credits(
                        user_id=transaction.user_id,
                        cost=actual_cost,
                        tokens=total_tokens,
                        session=session,
                    )

                    if not updated_user:
                        logger.error(
                            "Failed to deduct credits",
                            user_id=transaction.user_id,
                        )
                        return None, None

                    # Transaction auto-commits on success

            logger.info(
                "Transaction completed with credit deduction (ACID)",
                transaction_id=transaction_id,
                user_id=transaction.user_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost=actual_cost,
                new_balance=updated_user.credits,
            )

            return updated_transaction, updated_user

        except Exception as e:
            error_msg = str(e).lower()

            # Check if error is transaction-related (no transaction support)
            if "transaction" in error_msg or "replica" in error_msg:
                logger.warning(
                    "MongoDB transactions not supported - falling back to sequential",
                    error=str(e),
                )

                # Fallback: Sequential operations (best effort)
                try:
                    # 1. Complete transaction
                    updated_transaction = (
                        await self.transaction_repo.complete_transaction(
                            transaction_id=transaction_id,
                            message_id=message_id,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            total_tokens=total_tokens,
                            actual_cost=actual_cost,
                        )
                    )

                    if not updated_transaction:
                        return None, None

                    # 2. Deduct credits
                    updated_user = await self.user_repo.deduct_credits(
                        user_id=transaction.user_id,
                        cost=actual_cost,
                        tokens=total_tokens,
                    )

                    if not updated_user:
                        # Mark transaction as FAILED (user wasn't charged)
                        await self.transaction_repo.fail_transaction(transaction_id)
                        return None, None

                    logger.info(
                        "Transaction completed with credit deduction (fallback)",
                        transaction_id=transaction_id,
                        user_id=transaction.user_id,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        total_tokens=total_tokens,
                        cost=actual_cost,
                        new_balance=updated_user.credits,
                    )

                    return updated_transaction, updated_user

                except Exception as fallback_error:
                    logger.error(
                        "Fallback transaction completion failed",
                        error=str(fallback_error),
                        transaction_id=transaction_id,
                    )
                    return None, None

            else:
                # Other error - log and fail
                logger.error(
                    "Transaction completion failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    transaction_id=transaction_id,
                )
                return None, None

    async def fail_transaction(self, transaction_id: str) -> bool:
        """
        Mark transaction as FAILED (no charge to user).

        Args:
            transaction_id: Transaction identifier

        Returns:
            True if successful
        """
        updated = await self.transaction_repo.fail_transaction(transaction_id)

        if updated:
            logger.info("Transaction marked as failed", transaction_id=transaction_id)
            return True

        return False

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
            status: Optional status filter

        Returns:
            Tuple of (transactions list, total count)
        """
        if page < 1:
            raise ValidationError("Page must be >= 1", page=page)

        if page_size < 1 or page_size > 100:
            raise ValidationError("Page size must be 1-100", page_size=page_size)

        if status and status not in ["PENDING", "COMPLETED", "FAILED"]:
            raise ValidationError("Invalid status filter", status=status)

        return await self.transaction_repo.get_user_transactions(
            user_id=user_id,
            page=page,
            page_size=page_size,
            status=status,
        )

    async def adjust_credits_admin(
        self, user_id: str, amount: float, reason: str, admin_user_id: str
    ) -> User | None:
        """
        Manually adjust user credits (admin operation).

        Args:
            user_id: User identifier
            amount: Credits to add (positive) or deduct (negative)
            reason: Reason for adjustment (for audit trail)
            admin_user_id: Admin user performing adjustment

        Returns:
            Updated user if successful, None otherwise
        """
        updated_user = await self.user_repo.adjust_credits(user_id, amount, reason)

        if updated_user:
            logger.info(
                "Credits manually adjusted",
                user_id=user_id,
                amount=amount,
                reason=reason,
                admin_user_id=admin_user_id,
                new_balance=updated_user.credits,
            )

        return updated_user
