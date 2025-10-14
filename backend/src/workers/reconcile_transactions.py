"""
Transaction reconciliation worker.

Completes stuck PENDING transactions by:
1. Finding transactions older than threshold (default: 5 minutes)
2. Looking up linked message for actual token usage
3. Completing transaction + deducting credits (or failing if message missing)

Run manually or via cron/Kubernetes CronJob:
    python -m src.workers.reconcile_transactions

Environment variables:
    MONGODB_URL: MongoDB connection string (required)
    DASHSCOPE_API_KEY: Required for settings (not used by worker)
"""

import asyncio
import sys
from datetime import datetime, timedelta

import structlog

from ..core.config import Settings, get_settings
from ..database.mongodb import MongoDB
from ..database.repositories.message_repository import MessageRepository
from ..database.repositories.transaction_repository import TransactionRepository
from ..database.repositories.user_repository import UserRepository
from ..services.credit_service import CreditService

logger = structlog.get_logger()


async def reconcile_stuck_transactions(
    transaction_repo: TransactionRepository,
    message_repo: MessageRepository,
    credit_service: CreditService,
    age_minutes: int = 5,
) -> dict[str, int]:
    """
    Find and reconcile stuck PENDING transactions.

    Args:
        transaction_repo: Transaction repository
        message_repo: Message repository
        credit_service: Credit service for completion
        age_minutes: Minimum age in minutes to consider stuck

    Returns:
        Dict with counts: {"completed": N, "failed": N, "skipped": N}
    """
    cutoff_time = datetime.utcnow() - timedelta(minutes=age_minutes)

    logger.info(
        "Starting transaction reconciliation",
        cutoff_time=cutoff_time.isoformat(),
        age_minutes=age_minutes,
    )

    # Find stuck transactions
    stuck_transactions = await transaction_repo.find_stuck_transactions(age_minutes)

    if not stuck_transactions:
        logger.info("No stuck transactions found")
        return {"completed": 0, "failed": 0, "skipped": 0}

    logger.info("Found stuck transactions", count=len(stuck_transactions))

    stats = {"completed": 0, "failed": 0, "skipped": 0}

    for transaction in stuck_transactions:
        transaction_id = transaction.transaction_id
        user_id = transaction.user_id
        chat_id = transaction.chat_id

        logger.info(
            "Processing stuck transaction",
            transaction_id=transaction_id,
            user_id=user_id,
            chat_id=chat_id,
            created_at=transaction.created_at.isoformat(),
        )

        # Find the message linked to this transaction
        # Note: Message might not exist if LLM call failed before message was saved
        # Use direct lookup by transaction_id to avoid N+1 query
        linked_message = await message_repo.get_by_transaction_id(transaction_id)

        if not linked_message:
            # No message found - LLM call likely failed
            logger.warning(
                "No message found for transaction, marking as FAILED",
                transaction_id=transaction_id,
            )
            await credit_service.fail_transaction(transaction_id)
            stats["failed"] += 1
            continue

        # Message exists - extract token usage from metadata
        if not linked_message.metadata:
            logger.error(
                "Message exists but missing metadata",
                transaction_id=transaction_id,
                message_id=linked_message.message_id,
            )
            await credit_service.fail_transaction(transaction_id)
            stats["failed"] += 1
            continue

        # Check for granular token breakdown
        input_tokens = linked_message.metadata.input_tokens
        output_tokens = linked_message.metadata.output_tokens

        if input_tokens is None or output_tokens is None:
            logger.error(
                "Message missing granular token breakdown",
                transaction_id=transaction_id,
                message_id=linked_message.message_id,
                has_total=linked_message.metadata.tokens is not None,
            )
            await credit_service.fail_transaction(transaction_id)
            stats["failed"] += 1
            continue

        # Check if transaction was already completed by another process
        current_transaction = await transaction_repo.get_by_id(transaction_id)
        if not current_transaction or current_transaction.status != "PENDING":
            logger.info(
                "Transaction already processed by another worker",
                transaction_id=transaction_id,
                current_status=(
                    current_transaction.status if current_transaction else "NOT_FOUND"
                ),
            )
            stats["skipped"] += 1
            continue

        # Complete transaction with actual token usage
        updated_transaction, updated_user = (
            await credit_service.complete_transaction_with_deduction(
                transaction_id=transaction_id,
                message_id=linked_message.message_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        )

        if updated_transaction and updated_user:
            logger.info(
                "Transaction reconciled successfully",
                transaction_id=transaction_id,
                tokens=updated_transaction.total_tokens,
                cost=updated_transaction.actual_cost,
                new_balance=updated_user.credits,
            )
            stats["completed"] += 1
        else:
            logger.error(
                "Failed to reconcile transaction",
                transaction_id=transaction_id,
            )
            stats["failed"] += 1

    logger.info(
        "Transaction reconciliation completed",
        completed=stats["completed"],
        failed=stats["failed"],
        skipped=stats["skipped"],
    )

    return stats


async def main() -> int:
    """
    Main entry point for reconciliation worker.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        # Get settings
        settings: Settings = get_settings()

        # Connect to MongoDB
        mongodb = MongoDB()
        await mongodb.connect(settings.mongodb_url)

        logger.info("MongoDB connected")

        # Initialize repositories
        transaction_repo = TransactionRepository(mongodb.get_collection("transactions"))
        message_repo = MessageRepository(mongodb.get_collection("messages"))
        user_repo = UserRepository(mongodb.get_collection("users"))

        # Initialize credit service
        credit_service = CreditService(user_repo, transaction_repo, mongodb, settings)

        # Run reconciliation
        stats = await reconcile_stuck_transactions(
            transaction_repo=transaction_repo,
            message_repo=message_repo,
            credit_service=credit_service,
            age_minutes=5,  # Consider transactions older than 5 minutes as stuck
        )

        # Disconnect
        await mongodb.disconnect()

        logger.info(
            "Reconciliation worker finished successfully",
            stats=stats,
        )

        return 0

    except Exception as e:
        logger.error("Reconciliation worker failed", error=str(e), exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
