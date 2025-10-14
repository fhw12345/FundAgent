"""
Dependencies for credit system API endpoints.
"""

from fastapi import Depends

from ...core.config import Settings, get_settings
from ...database.mongodb import MongoDB
from ...database.repositories.transaction_repository import TransactionRepository
from ...database.repositories.user_repository import UserRepository
from ...services.credit_service import CreditService
from .auth import get_mongodb  # Import shared auth

# ===== Repository Dependencies =====


def get_user_repository(mongodb: MongoDB = Depends(get_mongodb)) -> UserRepository:
    """Get user repository instance."""
    users_collection = mongodb.get_collection("users")
    return UserRepository(users_collection)


def get_transaction_repository(
    mongodb: MongoDB = Depends(get_mongodb),
) -> TransactionRepository:
    """Get transaction repository instance."""
    transactions_collection = mongodb.get_collection("transactions")
    return TransactionRepository(transactions_collection)


# ===== Service Dependencies =====


def get_credit_service(
    user_repo: UserRepository = Depends(get_user_repository),
    transaction_repo: TransactionRepository = Depends(get_transaction_repository),
    mongodb: MongoDB = Depends(get_mongodb),
    settings: Settings = Depends(get_settings),
) -> CreditService:
    """Get credit service instance."""
    return CreditService(user_repo, transaction_repo, mongodb, settings)


__all__ = ["get_credit_service", "get_transaction_repository", "get_user_repository"]
