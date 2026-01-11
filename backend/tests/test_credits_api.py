"""
Unit tests for Credits API endpoints.

Tests user profile, transaction history, and admin credit adjustments.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.credits import (
    CreditAdjustmentRequest,
    CreditAdjustmentResponse,
    TransactionHistoryResponse,
    UserProfileResponse,
    router,
)
from src.api.dependencies.auth import get_current_user, require_admin
from src.api.dependencies.chat_deps import get_current_user_id
from src.api.dependencies.credit_deps import get_credit_service, get_user_repository
from src.models.user import User


# ===== Fixtures =====


@pytest.fixture
def mock_user():
    """Mock User object."""
    user = Mock(spec=User)
    user.user_id = "user_123"
    user.username = "testuser"
    user.email = "test@example.com"
    user.credits = 500.0
    user.total_tokens_used = 10000
    user.total_credits_spent = 50.0
    user.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    user.role = "user"
    return user


@pytest.fixture
def mock_admin_user():
    """Mock admin User object."""
    user = Mock(spec=User)
    user.user_id = "admin_123"
    user.username = "adminuser"
    user.email = "admin@example.com"
    user.credits = 1000.0
    user.total_tokens_used = 0
    user.total_credits_spent = 0.0
    user.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    user.role = "admin"
    return user


@pytest.fixture
def mock_credit_service():
    """Mock CreditService."""
    service = Mock()
    service.get_user_transactions = AsyncMock(return_value=([], 0))
    service.adjust_credits_admin = AsyncMock()
    return service


@pytest.fixture
def mock_user_repository():
    """Mock UserRepository."""
    repo = Mock()
    repo.get_by_id = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def client(mock_user, mock_credit_service, mock_user_repository):
    """Create test client with mocked dependencies."""
    app = FastAPI()
    app.include_router(router)

    # Override dependencies
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_current_user_id] = lambda: mock_user.user_id
    app.dependency_overrides[get_credit_service] = lambda: mock_credit_service
    app.dependency_overrides[get_user_repository] = lambda: mock_user_repository

    return TestClient(app)


@pytest.fixture
def admin_client(mock_admin_user, mock_credit_service, mock_user_repository):
    """Create test client with admin user."""
    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[get_current_user] = lambda: mock_admin_user
    app.dependency_overrides[require_admin] = lambda: mock_admin_user
    app.dependency_overrides[get_current_user_id] = lambda: mock_admin_user.user_id
    app.dependency_overrides[get_credit_service] = lambda: mock_credit_service
    app.dependency_overrides[get_user_repository] = lambda: mock_user_repository

    return TestClient(app)


# ===== Response Model Tests =====


class TestUserProfileResponse:
    """Test UserProfileResponse model."""

    def test_create_response(self):
        """Test creating user profile response."""
        response = UserProfileResponse(
            user_id="user_123",
            username="testuser",
            email="test@example.com",
            credits=500.0,
            total_tokens_used=10000,
            total_credits_spent=50.0,
            created_at="2025-01-01T00:00:00Z",
        )

        assert response.user_id == "user_123"
        assert response.credits == 500.0


# ===== get_current_user_profile Tests =====


class TestGetCurrentUserProfile:
    """Test get_current_user_profile endpoint."""

    def test_get_profile_success(self, client, mock_user):
        """Test getting current user profile."""
        response = client.get("/api/users/me")

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "user_123"
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
        assert data["credits"] == 500.0


# ===== get_transaction_history Tests =====


class TestGetTransactionHistory:
    """Test get_transaction_history endpoint."""

    def test_get_transactions_empty(self, client, mock_credit_service):
        """Test getting empty transaction history."""
        mock_credit_service.get_user_transactions.return_value = ([], 0)

        response = client.get("/api/credits/transactions")

        assert response.status_code == 200
        data = response.json()
        assert data["transactions"] == []
        assert data["pagination"]["total"] == 0

    def test_get_transactions_calls_service(self, client, mock_credit_service):
        """Test transaction history calls service correctly."""
        # Return empty list to avoid serialization issues with Mock objects
        mock_credit_service.get_user_transactions.return_value = ([], 10)

        response = client.get("/api/credits/transactions")

        assert response.status_code == 200
        mock_credit_service.get_user_transactions.assert_called_once()
        data = response.json()
        assert data["pagination"]["total"] == 10

    def test_get_transactions_with_pagination(self, client, mock_credit_service):
        """Test transaction history pagination."""
        mock_credit_service.get_user_transactions.return_value = ([], 50)

        response = client.get("/api/credits/transactions?page=2&page_size=10")

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["page"] == 2
        assert data["pagination"]["page_size"] == 10
        assert data["pagination"]["total"] == 50
        assert data["pagination"]["total_pages"] == 5

    def test_get_transactions_with_status_filter(self, client, mock_credit_service):
        """Test transaction history with status filter."""
        mock_credit_service.get_user_transactions.return_value = ([], 0)

        response = client.get("/api/credits/transactions?status=COMPLETED")

        assert response.status_code == 200
        mock_credit_service.get_user_transactions.assert_called_once_with(
            user_id="user_123",
            page=1,
            page_size=20,
            status="COMPLETED",
        )

    def test_get_transactions_error(self, client, mock_credit_service):
        """Test transaction history with service error."""
        mock_credit_service.get_user_transactions.side_effect = Exception("DB Error")

        response = client.get("/api/credits/transactions")

        assert response.status_code == 500
        assert "Failed to retrieve transaction history" in response.json()["detail"]


# ===== adjust_user_credits Tests =====


class TestAdjustUserCredits:
    """Test admin credit adjustment endpoint."""

    def test_adjust_credits_success(self, admin_client, mock_credit_service, mock_user_repository, mock_user):
        """Test successful credit adjustment."""
        target_user = Mock()
        target_user.credits = 100.0

        updated_user = Mock()
        updated_user.credits = 150.0

        mock_user_repository.get_by_id.return_value = target_user
        mock_credit_service.adjust_credits_admin.return_value = updated_user

        response = admin_client.post(
            "/api/admin/credits/adjust",
            json={
                "user_id": "user_456",
                "amount": 50.0,
                "reason": "Refund for system error on 2025-01-10",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "user_456"
        assert data["old_balance"] == 100.0
        assert data["adjustment"] == 50.0
        assert data["new_balance"] == 150.0

    def test_adjust_credits_user_not_found(self, admin_client, mock_user_repository):
        """Test credit adjustment for non-existent user."""
        mock_user_repository.get_by_id.return_value = None

        response = admin_client.post(
            "/api/admin/credits/adjust",
            json={
                "user_id": "nonexistent",
                "amount": 50.0,
                "reason": "Refund for system error on 2025-01-10",
            },
        )

        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]

    def test_adjust_credits_service_failure(self, admin_client, mock_credit_service, mock_user_repository):
        """Test credit adjustment service failure."""
        target_user = Mock()
        target_user.credits = 100.0
        mock_user_repository.get_by_id.return_value = target_user
        mock_credit_service.adjust_credits_admin.return_value = None

        response = admin_client.post(
            "/api/admin/credits/adjust",
            json={
                "user_id": "user_456",
                "amount": 50.0,
                "reason": "Refund for system error on 2025-01-10",
            },
        )

        assert response.status_code == 500
        assert "Failed to adjust credits" in response.json()["detail"]

    def test_adjust_credits_reason_too_short(self, admin_client):
        """Test credit adjustment with reason too short."""
        response = admin_client.post(
            "/api/admin/credits/adjust",
            json={
                "user_id": "user_456",
                "amount": 50.0,
                "reason": "Short",  # Less than 10 chars
            },
        )

        assert response.status_code == 422  # Validation error
