"""
Comprehensive unit tests for CreditService.

Tests credit management business logic including:
- Cost calculation
- Balance checking
- Transaction creation and completion
- MongoDB transaction support (ACID + fallback)
- Error handling and edge cases
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from src.core.config import Settings
from src.core.exceptions import ValidationError
from src.database.mongodb import MongoDB
from src.database.repositories.transaction_repository import TransactionRepository
from src.database.repositories.user_repository import UserRepository
from src.models.transaction import CreditTransaction, TransactionCreate
from src.models.user import User
from src.services.credit_service import CreditService


class TestCreditServiceCostCalculation:
    """Test cost calculation logic with new model-based pricing."""

    def test_calculate_cost_qwen_plus_basic(self):
        """Test cost calculation for qwen-plus model."""
        # qwen-plus: input ¥0.0008/1K, output ¥0.002/1K, 1 credit = ¥0.001
        # 500 input + 1000 output = (500/1000)*0.0008 + (1000/1000)*0.002 = 0.0004 + 0.002 = 0.0024 CNY = 2.4 credits
        assert CreditService.calculate_cost(500, 1000, "qwen-plus") == 2.4

    def test_calculate_cost_with_thinking_mode(self):
        """Test cost calculation with thinking mode (4x output multiplier)."""
        # qwen-plus with thinking: output cost * 4
        # 500 input + 1000 output thinking = (500/1000)*0.0008 + (1000/1000)*0.002*4 = 0.0004 + 0.008 = 0.0084 CNY = 8.4 credits
        assert CreditService.calculate_cost(500, 1000, "qwen-plus", thinking_enabled=True) == 8.4

    def test_calculate_cost_zero_tokens(self):
        """Test cost calculation with zero tokens."""
        assert CreditService.calculate_cost(0, 0, "qwen-plus") == 0.0

    def test_calculate_cost_different_models(self):
        """Test that different models have different costs."""
        # qwen3-max is more expensive than qwen-plus
        qwen_plus_cost = CreditService.calculate_cost(1000, 1000, "qwen-plus")
        qwen_max_cost = CreditService.calculate_cost(1000, 1000, "qwen3-max")
        assert qwen_max_cost > qwen_plus_cost


@pytest.mark.asyncio
class TestCreditServiceBalanceCheck:
    """Test balance checking logic."""

    @pytest.fixture
    def mock_user_repo(self):
        """Create mock UserRepository."""
        return AsyncMock(spec=UserRepository)

    @pytest.fixture
    def mock_transaction_repo(self):
        """Create mock TransactionRepository."""
        return AsyncMock(spec=TransactionRepository)

    @pytest.fixture
    def mock_mongodb(self):
        """Create mock MongoDB."""
        return MagicMock(spec=MongoDB)

    @pytest.fixture
    def mock_settings(self):
        """Create mock Settings."""
        return MagicMock(spec=Settings)

    @pytest.fixture
    def credit_service(
        self, mock_user_repo, mock_transaction_repo, mock_mongodb, mock_settings
    ):
        """Create CreditService with mocked dependencies."""
        return CreditService(
            user_repo=mock_user_repo,
            transaction_repo=mock_transaction_repo,
            mongodb=mock_mongodb,
            settings=mock_settings,
        )

    async def test_check_balance_sufficient(
        self, credit_service, mock_user_repo
    ):
        """Test balance check when user has sufficient credits."""
        user = User(
            user_id="user123",
            username="testuser",
            credits=100.0,
        )
        mock_user_repo.get_by_id.return_value = user

        result = await credit_service.check_balance("user123", 5.0)

        assert result is True
        mock_user_repo.get_by_id.assert_called_once_with("user123")

    async def test_check_balance_insufficient(
        self, credit_service, mock_user_repo
    ):
        """Test balance check when user has insufficient credits."""
        user = User(
            user_id="user123",
            username="testuser",
            credits=5.0,  # Below MIN_CREDIT_THRESHOLD (10.0)
        )
        mock_user_repo.get_by_id.return_value = user

        result = await credit_service.check_balance("user123", 5.0)

        assert result is False

    async def test_check_balance_user_not_found(
        self, credit_service, mock_user_repo
    ):
        """Test balance check when user doesn't exist."""
        mock_user_repo.get_by_id.return_value = None

        result = await credit_service.check_balance("nonexistent", 5.0)

        assert result is False

    async def test_check_balance_negative_cost_raises_error(
        self, credit_service, mock_user_repo
    ):
        """Test that negative estimated cost raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            await credit_service.check_balance("user123", -5.0)

        assert "Estimated cost cannot be negative" in str(exc_info.value)

    async def test_check_balance_exactly_at_threshold(
        self, credit_service, mock_user_repo
    ):
        """Test balance check when user has exactly MIN_CREDIT_THRESHOLD."""
        user = User(
            user_id="user123",
            username="testuser",
            credits=10.0,  # Exactly MIN_CREDIT_THRESHOLD
        )
        mock_user_repo.get_by_id.return_value = user

        result = await credit_service.check_balance("user123", 5.0)

        assert result is True


@pytest.mark.asyncio
class TestCreditServicePendingTransaction:
    """Test pending transaction creation."""

    @pytest.fixture
    def credit_service(self):
        """Create CreditService with mocked dependencies."""
        return CreditService(
            user_repo=AsyncMock(spec=UserRepository),
            transaction_repo=AsyncMock(spec=TransactionRepository),
            mongodb=MagicMock(spec=MongoDB),
            settings=MagicMock(spec=Settings),
        )

    async def test_create_pending_transaction_success(self, credit_service):
        """Test creating a pending transaction."""
        expected_transaction = CreditTransaction(
            transaction_id="txn123",
            user_id="user123",
            chat_id="chat456",
            status="PENDING",
            estimated_cost=10.0,
            model="qwen-plus",
            request_type="chat",
        )
        credit_service.transaction_repo.create_pending.return_value = (
            expected_transaction
        )

        result = await credit_service.create_pending_transaction(
            user_id="user123",
            chat_id="chat456",
            estimated_cost=10.0,
        )

        assert result == expected_transaction
        credit_service.transaction_repo.create_pending.assert_called_once()
        call_args = credit_service.transaction_repo.create_pending.call_args[0][0]
        assert isinstance(call_args, TransactionCreate)
        assert call_args.user_id == "user123"
        assert call_args.chat_id == "chat456"
        assert call_args.estimated_cost == 10.0


@pytest.mark.asyncio
class TestCreditServiceCompleteTransaction:
    """Test transaction completion with credit deduction."""

    @pytest.fixture
    def credit_service(self):
        """Create CreditService with mocked dependencies."""
        mock_mongodb = MagicMock(spec=MongoDB)
        mock_mongodb.client = MagicMock()

        return CreditService(
            user_repo=AsyncMock(spec=UserRepository),
            transaction_repo=AsyncMock(spec=TransactionRepository),
            mongodb=mock_mongodb,
            settings=MagicMock(spec=Settings),
        )

    async def test_complete_transaction_success_with_acid(self, credit_service):
        """Test successful transaction completion with MongoDB ACID transaction."""
        # Setup existing transaction
        existing_transaction = CreditTransaction(
            transaction_id="txn123",
            user_id="user123",
            chat_id="chat456",
            status="PENDING",
            estimated_cost=10.0,
            model="qwen-plus",
            request_type="chat",
        )
        credit_service.transaction_repo.get_by_id.return_value = existing_transaction

        # Setup successful completion
        completed_transaction = CreditTransaction(
            transaction_id="txn123",
            user_id="user123",
            chat_id="chat456",
            message_id="msg789",
            status="COMPLETED",
            estimated_cost=10.0,
            input_tokens=500,
            output_tokens=1000,
            total_tokens=1500,
            actual_cost=2.4,  # qwen-plus: 500 input + 1000 output = 2.4 credits
            model="qwen-plus",
            request_type="chat",
        )

        updated_user = User(
            user_id="user123",
            username="testuser",
            credits=97.6,  # 100 - 2.4
            total_tokens_used=1500,
            total_credits_spent=2.4,
        )

        # Mock MongoDB transaction support with proper async context manager
        mock_session = Mock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_transaction = Mock()
        mock_transaction.__aenter__ = AsyncMock(return_value=None)
        mock_transaction.__aexit__ = AsyncMock(return_value=None)
        mock_session.start_transaction = Mock(return_value=mock_transaction)

        # Mock start_session to return an awaitable that resolves to mock_session
        credit_service.mongodb.client.start_session = AsyncMock(return_value=mock_session)

        credit_service.transaction_repo.complete_transaction.return_value = (
            completed_transaction
        )
        credit_service.user_repo.deduct_credits.return_value = updated_user

        result = await credit_service.complete_transaction_with_deduction(
            transaction_id="txn123",
            message_id="msg789",
            input_tokens=500,
            output_tokens=1000,
        )

        transaction, user = result

        assert transaction == completed_transaction
        assert user == updated_user
        assert user.credits == 97.6
        credit_service.transaction_repo.complete_transaction.assert_called_once()
        credit_service.user_repo.deduct_credits.assert_called_once_with(
            user_id="user123",
            cost=2.4,
            tokens=1500,
            session=mock_session,
        )

    async def test_complete_transaction_not_found(self, credit_service):
        """Test transaction completion when transaction doesn't exist."""
        credit_service.transaction_repo.get_by_id.return_value = None

        result = await credit_service.complete_transaction_with_deduction(
            transaction_id="nonexistent",
            message_id="msg789",
            input_tokens=500,
            output_tokens=1000,
        )

        assert result == (None, None)

    async def test_complete_transaction_not_pending(self, credit_service):
        """Test that already completed transactions are not processed again."""
        existing_transaction = CreditTransaction(
            transaction_id="txn123",
            user_id="user123",
            chat_id="chat456",
            status="COMPLETED",  # Already completed
            estimated_cost=10.0,
            model="qwen-plus",
            request_type="chat",
        )
        credit_service.transaction_repo.get_by_id.return_value = existing_transaction

        result = await credit_service.complete_transaction_with_deduction(
            transaction_id="txn123",
            message_id="msg789",
            input_tokens=500,
            output_tokens=1000,
        )

        assert result == (None, None)

    async def test_complete_transaction_fallback_mode(self, credit_service):
        """Test fallback to sequential operations when MongoDB doesn't support transactions."""
        # Setup existing transaction
        existing_transaction = CreditTransaction(
            transaction_id="txn123",
            user_id="user123",
            chat_id="chat456",
            status="PENDING",
            estimated_cost=10.0,
            model="qwen-plus",
            request_type="chat",
        )
        credit_service.transaction_repo.get_by_id.return_value = existing_transaction

        # Mock MongoDB transaction failure
        mock_session = Mock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.start_transaction = Mock(
            side_effect=Exception("Transaction not supported on standalone instance")
        )

        credit_service.mongodb.client.start_session = AsyncMock(return_value=mock_session)

        # Setup successful sequential operations
        completed_transaction = CreditTransaction(
            transaction_id="txn123",
            user_id="user123",
            chat_id="chat456",
            message_id="msg789",
            status="COMPLETED",
            estimated_cost=10.0,
            input_tokens=500,
            output_tokens=1000,
            total_tokens=1500,
            actual_cost=2.4,  # qwen-plus: 500 input + 1000 output = 2.4 credits
            model="qwen-plus",
            request_type="chat",
        )

        updated_user = User(
            user_id="user123",
            username="testuser",
            credits=97.6,
            total_tokens_used=1500,
            total_credits_spent=2.4,
        )

        credit_service.transaction_repo.complete_transaction.return_value = (
            completed_transaction
        )
        credit_service.user_repo.deduct_credits.return_value = updated_user

        result = await credit_service.complete_transaction_with_deduction(
            transaction_id="txn123",
            message_id="msg789",
            input_tokens=500,
            output_tokens=1000,
        )

        transaction, user = result

        assert transaction == completed_transaction
        assert user == updated_user
        # Should fall back to sequential operations (without session parameter)
        credit_service.user_repo.deduct_credits.assert_called_once_with(
            user_id="user123",
            cost=2.4,
            tokens=1500,
        )

    async def test_complete_transaction_mongodb_client_unavailable(
        self, credit_service
    ):
        """Test transaction completion when MongoDB client is not available."""
        existing_transaction = CreditTransaction(
            transaction_id="txn123",
            user_id="user123",
            chat_id="chat456",
            status="PENDING",
            estimated_cost=10.0,
            model="qwen-plus",
            request_type="chat",
        )
        credit_service.transaction_repo.get_by_id.return_value = existing_transaction
        credit_service.mongodb.client = None  # No client available

        result = await credit_service.complete_transaction_with_deduction(
            transaction_id="txn123",
            message_id="msg789",
            input_tokens=500,
            output_tokens=1000,
        )

        assert result == (None, None)

    async def test_complete_transaction_deduction_fails_in_fallback(
        self, credit_service
    ):
        """Test that transaction is marked FAILED if credit deduction fails in fallback mode."""
        existing_transaction = CreditTransaction(
            transaction_id="txn123",
            user_id="user123",
            chat_id="chat456",
            status="PENDING",
            estimated_cost=10.0,
            model="qwen-plus",
            request_type="chat",
        )
        credit_service.transaction_repo.get_by_id.return_value = existing_transaction

        # Mock transaction not supported
        mock_session = Mock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.start_transaction = Mock(side_effect=Exception("Transaction not supported"))

        credit_service.mongodb.client.start_session = AsyncMock(return_value=mock_session)

        # Transaction completes but deduction fails
        completed_transaction = CreditTransaction(
            transaction_id="txn123",
            user_id="user123",
            chat_id="chat456",
            message_id="msg789",
            status="COMPLETED",
            estimated_cost=10.0,
            input_tokens=500,
            output_tokens=1000,
            total_tokens=1500,
            actual_cost=2.4,  # qwen-plus: 500 input + 1000 output = 2.4 credits
            model="qwen-plus",
            request_type="chat",
        )

        credit_service.transaction_repo.complete_transaction.return_value = (
            completed_transaction
        )
        credit_service.user_repo.deduct_credits.return_value = None  # Deduction fails

        result = await credit_service.complete_transaction_with_deduction(
            transaction_id="txn123",
            message_id="msg789",
            input_tokens=500,
            output_tokens=1000,
        )

        assert result == (None, None)
        # Should mark transaction as failed
        credit_service.transaction_repo.fail_transaction.assert_called_once_with("txn123")


@pytest.mark.asyncio
class TestCreditServiceFailTransaction:
    """Test transaction failure logic."""

    @pytest.fixture
    def credit_service(self):
        """Create CreditService with mocked dependencies."""
        return CreditService(
            user_repo=AsyncMock(spec=UserRepository),
            transaction_repo=AsyncMock(spec=TransactionRepository),
            mongodb=MagicMock(spec=MongoDB),
            settings=MagicMock(spec=Settings),
        )

    async def test_fail_transaction_success(self, credit_service):
        """Test successfully marking transaction as failed."""
        credit_service.transaction_repo.fail_transaction.return_value = True

        result = await credit_service.fail_transaction("txn123")

        assert result is True
        credit_service.transaction_repo.fail_transaction.assert_called_once_with("txn123")

    async def test_fail_transaction_not_found(self, credit_service):
        """Test failing a non-existent transaction."""
        credit_service.transaction_repo.fail_transaction.return_value = False

        result = await credit_service.fail_transaction("nonexistent")

        assert result is False


@pytest.mark.asyncio
class TestCreditServiceGetUserTransactions:
    """Test user transaction history retrieval."""

    @pytest.fixture
    def credit_service(self):
        """Create CreditService with mocked dependencies."""
        return CreditService(
            user_repo=AsyncMock(spec=UserRepository),
            transaction_repo=AsyncMock(spec=TransactionRepository),
            mongodb=MagicMock(spec=MongoDB),
            settings=MagicMock(spec=Settings),
        )

    async def test_get_user_transactions_success(self, credit_service):
        """Test retrieving user transaction history."""
        transactions = [
            CreditTransaction(
                transaction_id=f"txn{i}",
                user_id="user123",
                chat_id=f"chat{i}",
                status="COMPLETED",
                estimated_cost=10.0,
                model="qwen-plus",
                request_type="chat",
            )
            for i in range(10)
        ]
        credit_service.transaction_repo.get_user_transactions.return_value = (
            transactions,
            100,  # total count
        )

        result_transactions, total = await credit_service.get_user_transactions(
            user_id="user123",
            page=1,
            page_size=10,
        )

        assert len(result_transactions) == 10
        assert total == 100
        credit_service.transaction_repo.get_user_transactions.assert_called_once_with(
            user_id="user123",
            page=1,
            page_size=10,
            status=None,
        )

    async def test_get_user_transactions_with_status_filter(self, credit_service):
        """Test retrieving transactions with status filter."""
        transactions = [
            CreditTransaction(
                transaction_id="txn1",
                user_id="user123",
                chat_id="chat1",
                status="COMPLETED",
                estimated_cost=10.0,
                model="qwen-plus",
                request_type="chat",
            )
        ]
        credit_service.transaction_repo.get_user_transactions.return_value = (
            transactions,
            1,
        )

        result_transactions, total = await credit_service.get_user_transactions(
            user_id="user123",
            page=1,
            page_size=20,
            status="COMPLETED",
        )

        assert len(result_transactions) == 1
        credit_service.transaction_repo.get_user_transactions.assert_called_once_with(
            user_id="user123",
            page=1,
            page_size=20,
            status="COMPLETED",
        )

    async def test_get_user_transactions_invalid_page(self, credit_service):
        """Test that page < 1 raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            await credit_service.get_user_transactions(
                user_id="user123",
                page=0,
                page_size=20,
            )

        assert "Page must be >= 1" in str(exc_info.value)

    async def test_get_user_transactions_invalid_page_size(self, credit_service):
        """Test that invalid page_size raises ValidationError."""
        with pytest.raises(ValidationError):
            await credit_service.get_user_transactions(
                user_id="user123",
                page=1,
                page_size=0,
            )

        with pytest.raises(ValidationError):
            await credit_service.get_user_transactions(
                user_id="user123",
                page=1,
                page_size=101,
            )

    async def test_get_user_transactions_invalid_status(self, credit_service):
        """Test that invalid status raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            await credit_service.get_user_transactions(
                user_id="user123",
                page=1,
                page_size=20,
                status="INVALID_STATUS",
            )

        assert "Invalid status filter" in str(exc_info.value)


@pytest.mark.asyncio
class TestCreditServiceAdminAdjustments:
    """Test admin credit adjustment operations."""

    @pytest.fixture
    def credit_service(self):
        """Create CreditService with mocked dependencies."""
        return CreditService(
            user_repo=AsyncMock(spec=UserRepository),
            transaction_repo=AsyncMock(spec=TransactionRepository),
            mongodb=MagicMock(spec=MongoDB),
            settings=MagicMock(spec=Settings),
        )

    async def test_adjust_credits_admin_add_credits(self, credit_service):
        """Test admin adding credits to user."""
        updated_user = User(
            user_id="user123",
            username="testuser",
            credits=1100.0,  # 1000 + 100
        )
        credit_service.user_repo.adjust_credits.return_value = updated_user

        result = await credit_service.adjust_credits_admin(
            user_id="user123",
            amount=100.0,
            reason="Promotional bonus",
            admin_user_id="admin456",
        )

        assert result == updated_user
        assert result.credits == 1100.0
        credit_service.user_repo.adjust_credits.assert_called_once_with(
            "user123", 100.0, "Promotional bonus"
        )

    async def test_adjust_credits_admin_deduct_credits(self, credit_service):
        """Test admin deducting credits from user."""
        updated_user = User(
            user_id="user123",
            username="testuser",
            credits=900.0,  # 1000 - 100
        )
        credit_service.user_repo.adjust_credits.return_value = updated_user

        result = await credit_service.adjust_credits_admin(
            user_id="user123",
            amount=-100.0,
            reason="Refund correction",
            admin_user_id="admin456",
        )

        assert result == updated_user
        assert result.credits == 900.0

    async def test_adjust_credits_admin_user_not_found(self, credit_service):
        """Test admin adjustment when user doesn't exist."""
        credit_service.user_repo.adjust_credits.return_value = None

        result = await credit_service.adjust_credits_admin(
            user_id="nonexistent",
            amount=100.0,
            reason="Test",
            admin_user_id="admin456",
        )

        assert result is None
