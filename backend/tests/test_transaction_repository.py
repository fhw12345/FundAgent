"""
Comprehensive unit tests for TransactionRepository.

Tests database access layer for credit transactions including:
- Transaction creation and retrieval
- Status updates (PENDING → COMPLETED/FAILED)
- Pagination and filtering
- Stuck transaction detection
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from motor.motor_asyncio import AsyncIOMotorCollection
from pymongo import ReturnDocument

from src.database.repositories.transaction_repository import TransactionRepository
from src.models.transaction import CreditTransaction, TransactionCreate


class AsyncIterator:
    """Helper to create async iterator from list."""

    def __init__(self, items):
        self.items = items
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.items):
            raise StopAsyncIteration
        item = self.items[self.index]
        self.index += 1
        return item


class FakeCursor:
    """Fake cursor that implements async iteration protocol."""

    def __init__(self, items):
        self.items = items
        self.sort = Mock(return_value=self)
        self.skip = Mock(return_value=self)
        self.limit = Mock(return_value=self)

    def __aiter__(self):
        return AsyncIterator(self.items)


@pytest.fixture
def mock_collection():
    """Create mock MongoDB collection."""
    mock = AsyncMock(spec=AsyncIOMotorCollection)
    # Explicitly configure async methods
    mock.create_index = AsyncMock()
    mock.insert_one = AsyncMock()
    mock.find_one = AsyncMock()
    mock.find_one_and_update = AsyncMock()
    mock.count_documents = AsyncMock()
    return mock


@pytest.fixture
def transaction_repo(mock_collection):
    """Create TransactionRepository with mocked collection."""
    return TransactionRepository(collection=mock_collection)


@pytest.mark.asyncio
class TestTransactionRepositoryIndexes:
    """Test index creation."""

    async def test_ensure_indexes(self, transaction_repo, mock_collection):
        """Test that all required indexes are created."""
        await transaction_repo.ensure_indexes()

        # Verify all indexes were created
        assert mock_collection.create_index.call_count == 4

        # Verify specific index calls
        calls = mock_collection.create_index.call_args_list
        assert any("transaction_id" in str(call) for call in calls)
        assert any("user_id" in str(call) for call in calls)
        assert any("status" in str(call) for call in calls)
        assert any("chat_id" in str(call) for call in calls)


@pytest.mark.asyncio
class TestTransactionRepositoryCreatePending:
    """Test creating pending transactions."""

    async def test_create_pending_success(self, transaction_repo, mock_collection):
        """Test successfully creating a PENDING transaction."""
        transaction_create = TransactionCreate(
            user_id="user123",
            chat_id="chat456",
            estimated_cost=10.0,
            model="qwen-plus",
            request_type="chat",
        )

        transaction = await transaction_repo.create_pending(transaction_create)

        assert transaction.transaction_id.startswith("txn_")
        assert transaction.user_id == "user123"
        assert transaction.chat_id == "chat456"
        assert transaction.status == "PENDING"
        assert transaction.estimated_cost == 10.0
        assert transaction.message_id is None
        assert transaction.actual_cost is None
        mock_collection.insert_one.assert_called_once()

    async def test_create_pending_transaction_id_format(
        self, transaction_repo, mock_collection
    ):
        """Test that transaction_id has correct format."""
        transaction_create = TransactionCreate(
            user_id="user123",
            chat_id="chat456",
            estimated_cost=5.0,
        )

        transaction = await transaction_repo.create_pending(transaction_create)

        # Transaction ID should be txn_ + 12 hex characters
        assert transaction.transaction_id.startswith("txn_")
        assert len(transaction.transaction_id) == 16  # "txn_" (4) + 12 hex

    async def test_create_pending_with_defaults(self, transaction_repo, mock_collection):
        """Test creating transaction with default model and request_type."""
        transaction_create = TransactionCreate(
            user_id="user123",
            chat_id="chat456",
            estimated_cost=5.0,
        )

        transaction = await transaction_repo.create_pending(transaction_create)

        assert transaction.model == "qwen-plus"
        assert transaction.request_type == "chat"


@pytest.mark.asyncio
class TestTransactionRepositoryGetById:
    """Test getting transactions by ID."""

    async def test_get_by_id_found(self, transaction_repo, mock_collection):
        """Test getting an existing transaction."""
        mock_transaction = {
            "_id": "mongo_id_123",
            "transaction_id": "txn123",
            "user_id": "user123",
            "chat_id": "chat456",
            "status": "COMPLETED",
            "estimated_cost": 10.0,
            "input_tokens": 500,
            "output_tokens": 1000,
            "total_tokens": 1500,
            "actual_cost": 7.5,
            "created_at": datetime.utcnow(),
            "completed_at": datetime.utcnow(),
            "model": "qwen-plus",
            "request_type": "chat",
        }
        mock_collection.find_one.return_value = mock_transaction

        transaction = await transaction_repo.get_by_id("txn123")

        assert transaction is not None
        assert transaction.transaction_id == "txn123"
        assert transaction.user_id == "user123"
        assert transaction.status == "COMPLETED"
        mock_collection.find_one.assert_called_once_with({"transaction_id": "txn123"})

    async def test_get_by_id_not_found(self, transaction_repo, mock_collection):
        """Test getting a non-existent transaction."""
        mock_collection.find_one.return_value = None

        transaction = await transaction_repo.get_by_id("nonexistent")

        assert transaction is None
        mock_collection.find_one.assert_called_once_with({"transaction_id": "nonexistent"})


@pytest.mark.asyncio
class TestTransactionRepositoryCompleteTransaction:
    """Test completing transactions."""

    async def test_complete_transaction_success(self, transaction_repo, mock_collection):
        """Test successfully completing a PENDING transaction."""
        updated_transaction = {
            "_id": "mongo_id_123",
            "transaction_id": "txn123",
            "user_id": "user123",
            "chat_id": "chat456",
            "message_id": "msg789",
            "status": "COMPLETED",
            "estimated_cost": 10.0,
            "input_tokens": 500,
            "output_tokens": 1000,
            "total_tokens": 1500,
            "actual_cost": 7.5,
            "created_at": datetime.utcnow(),
            "completed_at": datetime.utcnow(),
            "model": "qwen-plus",
            "request_type": "chat",
        }
        mock_collection.find_one_and_update.return_value = updated_transaction

        transaction = await transaction_repo.complete_transaction(
            transaction_id="txn123",
            message_id="msg789",
            input_tokens=500,
            output_tokens=1000,
            total_tokens=1500,
            actual_cost=7.5,
        )

        assert transaction is not None
        assert transaction.transaction_id == "txn123"
        assert transaction.status == "COMPLETED"
        assert transaction.message_id == "msg789"
        assert transaction.input_tokens == 500
        assert transaction.output_tokens == 1000
        assert transaction.total_tokens == 1500
        assert transaction.actual_cost == 7.5

        # Verify atomic update with status condition
        call_args = mock_collection.find_one_and_update.call_args
        assert call_args[0][0] == {"transaction_id": "txn123", "status": "PENDING"}
        assert call_args[1]["return_document"] == ReturnDocument.AFTER

    async def test_complete_transaction_with_session(
        self, transaction_repo, mock_collection
    ):
        """Test completing transaction with MongoDB session."""
        mock_session = Mock()
        updated_transaction = {
            "_id": "mongo_id_123",
            "transaction_id": "txn123",
            "user_id": "user123",
            "chat_id": "chat456",
            "message_id": "msg789",
            "status": "COMPLETED",
            "estimated_cost": 10.0,
            "input_tokens": 500,
            "output_tokens": 1000,
            "total_tokens": 1500,
            "actual_cost": 7.5,
            "created_at": datetime.utcnow(),
            "completed_at": datetime.utcnow(),
            "model": "qwen-plus",
            "request_type": "chat",
        }
        mock_collection.find_one_and_update.return_value = updated_transaction

        transaction = await transaction_repo.complete_transaction(
            transaction_id="txn123",
            message_id="msg789",
            input_tokens=500,
            output_tokens=1000,
            total_tokens=1500,
            actual_cost=7.5,
            session=mock_session,
        )

        assert transaction is not None
        # Verify session was passed to MongoDB operation
        call_args = mock_collection.find_one_and_update.call_args
        assert call_args[1]["session"] == mock_session

    async def test_complete_transaction_not_found(
        self, transaction_repo, mock_collection
    ):
        """Test completing a non-existent transaction."""
        mock_collection.find_one_and_update.return_value = None

        transaction = await transaction_repo.complete_transaction(
            transaction_id="nonexistent",
            message_id="msg789",
            input_tokens=500,
            output_tokens=1000,
            total_tokens=1500,
            actual_cost=7.5,
        )

        assert transaction is None

    async def test_complete_transaction_already_completed(
        self, transaction_repo, mock_collection
    ):
        """Test that already completed transactions return None."""
        mock_collection.find_one_and_update.return_value = None

        transaction = await transaction_repo.complete_transaction(
            transaction_id="txn123",
            message_id="msg789",
            input_tokens=500,
            output_tokens=1000,
            total_tokens=1500,
            actual_cost=7.5,
        )

        assert transaction is None


@pytest.mark.asyncio
class TestTransactionRepositoryFailTransaction:
    """Test failing transactions."""

    async def test_fail_transaction_success(self, transaction_repo, mock_collection):
        """Test successfully marking a transaction as FAILED."""
        failed_transaction = {
            "_id": "mongo_id_123",
            "transaction_id": "txn123",
            "user_id": "user123",
            "chat_id": "chat456",
            "status": "FAILED",
            "estimated_cost": 10.0,
            "created_at": datetime.utcnow(),
            "completed_at": datetime.utcnow(),
            "model": "qwen-plus",
            "request_type": "chat",
        }
        mock_collection.find_one_and_update.return_value = failed_transaction

        transaction = await transaction_repo.fail_transaction("txn123")

        assert transaction is not None
        assert transaction.status == "FAILED"
        assert transaction.completed_at is not None

        # Verify atomic update with status condition
        call_args = mock_collection.find_one_and_update.call_args
        assert call_args[0][0] == {"transaction_id": "txn123", "status": "PENDING"}

    async def test_fail_transaction_not_found(self, transaction_repo, mock_collection):
        """Test failing a non-existent transaction."""
        mock_collection.find_one_and_update.return_value = None

        transaction = await transaction_repo.fail_transaction("nonexistent")

        assert transaction is None


@pytest.mark.asyncio
class TestTransactionRepositoryFindStuck:
    """Test finding stuck transactions."""

    async def test_find_stuck_transactions(self, transaction_repo, mock_collection):
        """Test finding transactions stuck in PENDING."""
        now = datetime.utcnow()
        old_transaction = {
            "_id": "mongo_id_1",
            "transaction_id": "txn123",
            "user_id": "user123",
            "chat_id": "chat456",
            "status": "PENDING",
            "estimated_cost": 10.0,
            "created_at": now - timedelta(minutes=15),  # 15 minutes old
            "model": "qwen-plus",
            "request_type": "chat",
        }

        # Mock async cursor
        mock_cursor = FakeCursor([old_transaction])
        mock_collection.find = Mock(return_value=mock_cursor)

        stuck_transactions = await transaction_repo.find_stuck_transactions(age_minutes=10)

        assert len(stuck_transactions) == 1
        assert stuck_transactions[0].transaction_id == "txn123"
        assert stuck_transactions[0].status == "PENDING"

        # Verify query filter
        call_args = mock_collection.find.call_args[0][0]
        assert call_args["status"] == "PENDING"
        assert "$lt" in call_args["created_at"]

    async def test_find_stuck_transactions_none_found(
        self, transaction_repo, mock_collection
    ):
        """Test when no stuck transactions are found."""
        mock_cursor = FakeCursor([])
        mock_collection.find = Mock(return_value=mock_cursor)

        stuck_transactions = await transaction_repo.find_stuck_transactions(age_minutes=10)

        assert len(stuck_transactions) == 0

    async def test_find_stuck_transactions_custom_age(
        self, transaction_repo, mock_collection
    ):
        """Test finding stuck transactions with custom age threshold."""
        now = datetime.utcnow()
        old_transaction = {
            "_id": "mongo_id_1",
            "transaction_id": "txn123",
            "user_id": "user123",
            "chat_id": "chat456",
            "status": "PENDING",
            "estimated_cost": 10.0,
            "created_at": now - timedelta(minutes=25),  # 25 minutes old
            "model": "qwen-plus",
            "request_type": "chat",
        }

        mock_cursor = FakeCursor([old_transaction])
        mock_collection.find = Mock(return_value=mock_cursor)

        stuck_transactions = await transaction_repo.find_stuck_transactions(age_minutes=20)

        assert len(stuck_transactions) == 1


@pytest.mark.asyncio
class TestTransactionRepositoryGetUserTransactions:
    """Test getting user transaction history."""

    async def test_get_user_transactions_success(
        self, transaction_repo, mock_collection
    ):
        """Test getting paginated user transactions."""
        transactions = [
            {
                "_id": f"mongo_id_{i}",
                "transaction_id": f"txn{i}",
                "user_id": "user123",
                "chat_id": f"chat{i}",
                "status": "COMPLETED",
                "estimated_cost": 10.0,
                "created_at": datetime.utcnow(),
                "model": "qwen-plus",
                "request_type": "chat",
            }
            for i in range(5)
        ]

        mock_collection.count_documents.return_value = 100

        # Mock cursor with fake cursor
        mock_cursor = FakeCursor(transactions)
        mock_collection.find = Mock(return_value=mock_cursor)

        result_transactions, total = await transaction_repo.get_user_transactions(
            user_id="user123",
            page=1,
            page_size=5,
        )

        assert len(result_transactions) == 5
        assert total == 100
        mock_collection.count_documents.assert_called_once_with({"user_id": "user123"})

    async def test_get_user_transactions_with_status_filter(
        self, transaction_repo, mock_collection
    ):
        """Test getting transactions filtered by status."""
        transactions = [
            {
                "_id": "mongo_id_1",
                "transaction_id": "txn1",
                "user_id": "user123",
                "chat_id": "chat1",
                "status": "COMPLETED",
                "estimated_cost": 10.0,
                "created_at": datetime.utcnow(),
                "model": "qwen-plus",
                "request_type": "chat",
            }
        ]

        mock_collection.count_documents.return_value = 1

        # Mock cursor with fake cursor
        mock_cursor = FakeCursor(transactions)
        mock_collection.find = Mock(return_value=mock_cursor)

        result_transactions, total = await transaction_repo.get_user_transactions(
            user_id="user123",
            page=1,
            page_size=20,
            status="COMPLETED",
        )

        assert len(result_transactions) == 1
        assert total == 1
        mock_collection.count_documents.assert_called_once_with(
            {"user_id": "user123", "status": "COMPLETED"}
        )

    async def test_get_user_transactions_pagination(
        self, transaction_repo, mock_collection
    ):
        """Test pagination calculations."""
        mock_collection.count_documents.return_value = 0

        # Mock cursor with fake cursor
        mock_cursor = FakeCursor([])
        mock_collection.find = Mock(return_value=mock_cursor)

        await transaction_repo.get_user_transactions(
            user_id="user123",
            page=3,
            page_size=10,
        )

        # Verify skip and limit
        mock_cursor.skip.assert_called_once_with(20)  # (page 3 - 1) * 10
        mock_cursor.limit.assert_called_once_with(10)

    async def test_get_user_transactions_empty_result(
        self, transaction_repo, mock_collection
    ):
        """Test when user has no transactions."""
        mock_collection.count_documents.return_value = 0

        # Mock cursor with fake cursor
        mock_cursor = FakeCursor([])
        mock_collection.find = Mock(return_value=mock_cursor)

        result_transactions, total = await transaction_repo.get_user_transactions(
            user_id="user123",
            page=1,
            page_size=20,
        )

        assert len(result_transactions) == 0
        assert total == 0


@pytest.mark.asyncio
class TestTransactionRepositoryGetByMessageId:
    """Test getting transactions by message ID."""

    async def test_get_by_message_id_found(self, transaction_repo, mock_collection):
        """Test getting transaction by message_id."""
        mock_transaction = {
            "_id": "mongo_id_123",
            "transaction_id": "txn123",
            "user_id": "user123",
            "chat_id": "chat456",
            "message_id": "msg789",
            "status": "COMPLETED",
            "estimated_cost": 10.0,
            "input_tokens": 500,
            "output_tokens": 1000,
            "total_tokens": 1500,
            "actual_cost": 7.5,
            "created_at": datetime.utcnow(),
            "completed_at": datetime.utcnow(),
            "model": "qwen-plus",
            "request_type": "chat",
        }
        mock_collection.find_one.return_value = mock_transaction

        transaction = await transaction_repo.get_by_message_id("msg789")

        assert transaction is not None
        assert transaction.message_id == "msg789"
        assert transaction.transaction_id == "txn123"
        mock_collection.find_one.assert_called_once_with({"message_id": "msg789"})

    async def test_get_by_message_id_not_found(self, transaction_repo, mock_collection):
        """Test when no transaction is found for message_id."""
        mock_collection.find_one.return_value = None

        transaction = await transaction_repo.get_by_message_id("nonexistent")

        assert transaction is None
        mock_collection.find_one.assert_called_once_with({"message_id": "nonexistent"})
