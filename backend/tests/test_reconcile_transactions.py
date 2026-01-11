"""
Unit tests for transaction reconciliation worker.

Tests stuck transaction handling, message lookup, and credit completion.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.workers.reconcile_transactions import (
    main,
    reconcile_stuck_transactions,
)


# ===== Fixtures =====


@pytest.fixture
def mock_transaction_repo():
    """Mock transaction repository."""
    repo = AsyncMock()
    repo.find_stuck_transactions = AsyncMock(return_value=[])
    repo.get_by_id = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_message_repo():
    """Mock message repository."""
    repo = AsyncMock()
    repo.get_by_transaction_id = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_credit_service():
    """Mock credit service."""
    service = AsyncMock()
    service.fail_transaction = AsyncMock()
    service.complete_transaction_with_deduction = AsyncMock(return_value=(None, None))
    return service


@pytest.fixture
def mock_transaction():
    """Create a mock stuck transaction."""
    transaction = Mock()
    transaction.transaction_id = "txn_123"
    transaction.user_id = "user_456"
    transaction.chat_id = "chat_789"
    transaction.created_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    transaction.status = "PENDING"
    return transaction


@pytest.fixture
def mock_message():
    """Create a mock message with token data."""
    message = Mock()
    message.message_id = "msg_abc"
    message.metadata = Mock()
    message.metadata.input_tokens = 100
    message.metadata.output_tokens = 200
    message.metadata.tokens = 300
    return message


# ===== reconcile_stuck_transactions Tests =====


class TestReconcileStuckTransactions:
    """Test reconcile_stuck_transactions function."""

    @pytest.mark.asyncio
    async def test_no_stuck_transactions(
        self, mock_transaction_repo, mock_message_repo, mock_credit_service
    ):
        """Test when no stuck transactions found."""
        mock_transaction_repo.find_stuck_transactions.return_value = []

        result = await reconcile_stuck_transactions(
            transaction_repo=mock_transaction_repo,
            message_repo=mock_message_repo,
            credit_service=mock_credit_service,
            age_minutes=5,
        )

        assert result == {"completed": 0, "failed": 0, "skipped": 0}
        mock_transaction_repo.find_stuck_transactions.assert_called_once_with(5)

    @pytest.mark.asyncio
    async def test_transaction_no_linked_message(
        self,
        mock_transaction_repo,
        mock_message_repo,
        mock_credit_service,
        mock_transaction,
    ):
        """Test transaction with no linked message gets failed."""
        mock_transaction_repo.find_stuck_transactions.return_value = [mock_transaction]
        mock_message_repo.get_by_transaction_id.return_value = None

        result = await reconcile_stuck_transactions(
            transaction_repo=mock_transaction_repo,
            message_repo=mock_message_repo,
            credit_service=mock_credit_service,
        )

        assert result["failed"] == 1
        assert result["completed"] == 0
        mock_credit_service.fail_transaction.assert_called_once_with("txn_123")

    @pytest.mark.asyncio
    async def test_transaction_message_missing_metadata(
        self,
        mock_transaction_repo,
        mock_message_repo,
        mock_credit_service,
        mock_transaction,
    ):
        """Test transaction with message missing metadata gets failed."""
        mock_transaction_repo.find_stuck_transactions.return_value = [mock_transaction]
        message = Mock()
        message.message_id = "msg_123"
        message.metadata = None
        mock_message_repo.get_by_transaction_id.return_value = message

        result = await reconcile_stuck_transactions(
            transaction_repo=mock_transaction_repo,
            message_repo=mock_message_repo,
            credit_service=mock_credit_service,
        )

        assert result["failed"] == 1
        mock_credit_service.fail_transaction.assert_called_once_with("txn_123")

    @pytest.mark.asyncio
    async def test_transaction_message_missing_input_tokens(
        self,
        mock_transaction_repo,
        mock_message_repo,
        mock_credit_service,
        mock_transaction,
    ):
        """Test transaction with message missing input_tokens gets failed."""
        mock_transaction_repo.find_stuck_transactions.return_value = [mock_transaction]
        message = Mock()
        message.message_id = "msg_123"
        message.metadata = Mock()
        message.metadata.input_tokens = None
        message.metadata.output_tokens = 200
        message.metadata.tokens = 200
        mock_message_repo.get_by_transaction_id.return_value = message

        result = await reconcile_stuck_transactions(
            transaction_repo=mock_transaction_repo,
            message_repo=mock_message_repo,
            credit_service=mock_credit_service,
        )

        assert result["failed"] == 1
        mock_credit_service.fail_transaction.assert_called_once_with("txn_123")

    @pytest.mark.asyncio
    async def test_transaction_message_missing_output_tokens(
        self,
        mock_transaction_repo,
        mock_message_repo,
        mock_credit_service,
        mock_transaction,
    ):
        """Test transaction with message missing output_tokens gets failed."""
        mock_transaction_repo.find_stuck_transactions.return_value = [mock_transaction]
        message = Mock()
        message.message_id = "msg_123"
        message.metadata = Mock()
        message.metadata.input_tokens = 100
        message.metadata.output_tokens = None
        message.metadata.tokens = 100
        mock_message_repo.get_by_transaction_id.return_value = message

        result = await reconcile_stuck_transactions(
            transaction_repo=mock_transaction_repo,
            message_repo=mock_message_repo,
            credit_service=mock_credit_service,
        )

        assert result["failed"] == 1
        mock_credit_service.fail_transaction.assert_called_once_with("txn_123")

    @pytest.mark.asyncio
    async def test_transaction_already_processed(
        self,
        mock_transaction_repo,
        mock_message_repo,
        mock_credit_service,
        mock_transaction,
        mock_message,
    ):
        """Test transaction already processed by another worker gets skipped."""
        mock_transaction_repo.find_stuck_transactions.return_value = [mock_transaction]
        mock_message_repo.get_by_transaction_id.return_value = mock_message

        # Return a completed transaction on re-check
        completed_txn = Mock()
        completed_txn.status = "COMPLETED"
        mock_transaction_repo.get_by_id.return_value = completed_txn

        result = await reconcile_stuck_transactions(
            transaction_repo=mock_transaction_repo,
            message_repo=mock_message_repo,
            credit_service=mock_credit_service,
        )

        assert result["skipped"] == 1
        assert result["completed"] == 0
        assert result["failed"] == 0
        mock_credit_service.complete_transaction_with_deduction.assert_not_called()

    @pytest.mark.asyncio
    async def test_transaction_not_found_on_recheck(
        self,
        mock_transaction_repo,
        mock_message_repo,
        mock_credit_service,
        mock_transaction,
        mock_message,
    ):
        """Test transaction not found on re-check gets skipped."""
        mock_transaction_repo.find_stuck_transactions.return_value = [mock_transaction]
        mock_message_repo.get_by_transaction_id.return_value = mock_message
        mock_transaction_repo.get_by_id.return_value = None

        result = await reconcile_stuck_transactions(
            transaction_repo=mock_transaction_repo,
            message_repo=mock_message_repo,
            credit_service=mock_credit_service,
        )

        assert result["skipped"] == 1

    @pytest.mark.asyncio
    async def test_transaction_completed_successfully(
        self,
        mock_transaction_repo,
        mock_message_repo,
        mock_credit_service,
        mock_transaction,
        mock_message,
    ):
        """Test transaction completed successfully."""
        mock_transaction_repo.find_stuck_transactions.return_value = [mock_transaction]
        mock_message_repo.get_by_transaction_id.return_value = mock_message

        # Still pending on re-check
        mock_transaction_repo.get_by_id.return_value = mock_transaction

        # Complete successfully
        updated_txn = Mock()
        updated_txn.total_tokens = 300
        updated_txn.actual_cost = 0.01
        updated_user = Mock()
        updated_user.credits = 99.99
        mock_credit_service.complete_transaction_with_deduction.return_value = (
            updated_txn,
            updated_user,
        )

        result = await reconcile_stuck_transactions(
            transaction_repo=mock_transaction_repo,
            message_repo=mock_message_repo,
            credit_service=mock_credit_service,
        )

        assert result["completed"] == 1
        assert result["failed"] == 0
        mock_credit_service.complete_transaction_with_deduction.assert_called_once_with(
            transaction_id="txn_123",
            message_id="msg_abc",
            input_tokens=100,
            output_tokens=200,
        )

    @pytest.mark.asyncio
    async def test_transaction_completion_fails(
        self,
        mock_transaction_repo,
        mock_message_repo,
        mock_credit_service,
        mock_transaction,
        mock_message,
    ):
        """Test transaction completion failure."""
        mock_transaction_repo.find_stuck_transactions.return_value = [mock_transaction]
        mock_message_repo.get_by_transaction_id.return_value = mock_message
        mock_transaction_repo.get_by_id.return_value = mock_transaction

        # Complete returns None (failure)
        mock_credit_service.complete_transaction_with_deduction.return_value = (
            None,
            None,
        )

        result = await reconcile_stuck_transactions(
            transaction_repo=mock_transaction_repo,
            message_repo=mock_message_repo,
            credit_service=mock_credit_service,
        )

        assert result["failed"] == 1
        assert result["completed"] == 0

    @pytest.mark.asyncio
    async def test_multiple_transactions_mixed_results(
        self, mock_transaction_repo, mock_message_repo, mock_credit_service
    ):
        """Test multiple transactions with mixed results."""
        # Create 3 transactions
        txn1 = Mock()
        txn1.transaction_id = "txn_1"
        txn1.user_id = "user_1"
        txn1.chat_id = "chat_1"
        txn1.created_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        txn1.status = "PENDING"

        txn2 = Mock()
        txn2.transaction_id = "txn_2"
        txn2.user_id = "user_2"
        txn2.chat_id = "chat_2"
        txn2.created_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        txn2.status = "PENDING"

        txn3 = Mock()
        txn3.transaction_id = "txn_3"
        txn3.user_id = "user_3"
        txn3.chat_id = "chat_3"
        txn3.created_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        txn3.status = "PENDING"

        mock_transaction_repo.find_stuck_transactions.return_value = [txn1, txn2, txn3]

        # txn_1: no message -> fail
        # txn_2: complete successfully
        # txn_3: already processed -> skip
        def get_message_by_txn(txn_id):
            if txn_id == "txn_1":
                return None
            elif txn_id == "txn_2":
                msg = Mock()
                msg.message_id = "msg_2"
                msg.metadata = Mock()
                msg.metadata.input_tokens = 50
                msg.metadata.output_tokens = 75
                return msg
            elif txn_id == "txn_3":
                msg = Mock()
                msg.message_id = "msg_3"
                msg.metadata = Mock()
                msg.metadata.input_tokens = 100
                msg.metadata.output_tokens = 150
                return msg
            return None

        mock_message_repo.get_by_transaction_id.side_effect = get_message_by_txn

        def get_txn_by_id(txn_id):
            if txn_id == "txn_2":
                return txn2  # Still pending
            elif txn_id == "txn_3":
                completed = Mock()
                completed.status = "COMPLETED"
                return completed
            return None

        mock_transaction_repo.get_by_id.side_effect = get_txn_by_id

        # txn_2 completes successfully
        updated_txn = Mock()
        updated_txn.total_tokens = 125
        updated_txn.actual_cost = 0.005
        updated_user = Mock()
        updated_user.credits = 99.5
        mock_credit_service.complete_transaction_with_deduction.return_value = (
            updated_txn,
            updated_user,
        )

        result = await reconcile_stuck_transactions(
            transaction_repo=mock_transaction_repo,
            message_repo=mock_message_repo,
            credit_service=mock_credit_service,
        )

        assert result["completed"] == 1  # txn_2
        assert result["failed"] == 1  # txn_1
        assert result["skipped"] == 1  # txn_3

    @pytest.mark.asyncio
    async def test_custom_age_minutes(
        self, mock_transaction_repo, mock_message_repo, mock_credit_service
    ):
        """Test custom age_minutes parameter."""
        mock_transaction_repo.find_stuck_transactions.return_value = []

        await reconcile_stuck_transactions(
            transaction_repo=mock_transaction_repo,
            message_repo=mock_message_repo,
            credit_service=mock_credit_service,
            age_minutes=10,
        )

        mock_transaction_repo.find_stuck_transactions.assert_called_once_with(10)


# ===== main() Tests =====


class TestMain:
    """Test main() entry point."""

    @pytest.mark.asyncio
    async def test_main_success(self):
        """Test main() successful execution."""
        with patch("src.workers.reconcile_transactions.get_settings") as mock_settings:
            mock_settings.return_value = Mock(mongodb_url="mongodb://localhost/test")

            with patch("src.workers.reconcile_transactions.MongoDB") as mock_db_class:
                mock_db = AsyncMock()
                mock_db.connect = AsyncMock()
                mock_db.disconnect = AsyncMock()
                mock_db.get_collection = Mock(return_value=Mock())
                mock_db_class.return_value = mock_db

                with patch(
                    "src.workers.reconcile_transactions.TransactionRepository"
                ):
                    with patch("src.workers.reconcile_transactions.MessageRepository"):
                        with patch("src.workers.reconcile_transactions.UserRepository"):
                            with patch(
                                "src.workers.reconcile_transactions.CreditService"
                            ):
                                with patch(
                                    "src.workers.reconcile_transactions.reconcile_stuck_transactions"
                                ) as mock_reconcile:
                                    mock_reconcile.return_value = {
                                        "completed": 5,
                                        "failed": 1,
                                        "skipped": 2,
                                    }

                                    exit_code = await main()

                                    assert exit_code == 0
                                    mock_db.connect.assert_called_once()
                                    mock_db.disconnect.assert_called_once()
                                    mock_reconcile.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_exception(self):
        """Test main() handles exceptions."""
        with patch("src.workers.reconcile_transactions.get_settings") as mock_settings:
            mock_settings.side_effect = Exception("Config error")

            exit_code = await main()

            assert exit_code == 1

    @pytest.mark.asyncio
    async def test_main_mongodb_connection_error(self):
        """Test main() handles MongoDB connection error."""
        with patch("src.workers.reconcile_transactions.get_settings") as mock_settings:
            mock_settings.return_value = Mock(mongodb_url="mongodb://localhost/test")

            with patch("src.workers.reconcile_transactions.MongoDB") as mock_db_class:
                mock_db = AsyncMock()
                mock_db.connect = AsyncMock(side_effect=Exception("Connection failed"))
                mock_db_class.return_value = mock_db

                exit_code = await main()

                assert exit_code == 1
