"""
Unit tests for auth dependencies.

Tests shared authentication dependencies for API endpoints:
- get_current_user_id: JWT token extraction and verification
- get_current_user: Full user retrieval for authenticated requests
- require_admin: Admin privilege verification (secret header and JWT)
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import HTTPException

from src.api.dependencies.auth import (
    get_auth_service,
    get_current_user,
    get_current_user_id,
    get_user_repository,
    require_admin,
)
from src.models.user import User


# ===== Fixtures =====


@pytest.fixture
def mock_auth_service():
    """Mock AuthService"""
    service = Mock()
    service.verify_token = Mock(return_value="user_123")
    return service


@pytest.fixture
def mock_user_repo():
    """Mock UserRepository"""
    repo = Mock()
    repo.get_by_id = AsyncMock()
    return repo


@pytest.fixture
def sample_user():
    """Sample user for tests"""
    return User(
        user_id="user_123",
        email="test@example.com",
        username="testuser",
        credits=100,
        is_admin=False,  # Regular user, not admin
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def admin_user():
    """Sample admin user"""
    return User(
        user_id="admin_456",
        email="admin@example.com",
        username="adminuser",
        credits=1000,
        is_admin=True,  # Use is_admin field, not admin property
        created_at=datetime.now(timezone.utc),
    )


# ===== get_current_user_id Tests =====


class TestGetCurrentUserId:
    """Test get_current_user_id dependency"""

    @pytest.mark.asyncio
    async def test_missing_authorization_header(self, mock_auth_service):
        """Test that missing Authorization header returns 401"""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id(None, mock_auth_service)

        assert exc_info.value.status_code == 401
        assert "Authorization header required" in exc_info.value.detail
        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}

    @pytest.mark.asyncio
    async def test_invalid_header_format_single_part(self, mock_auth_service):
        """Test single-part header (missing Bearer or token)"""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id("sometoken", mock_auth_service)

        assert exc_info.value.status_code == 401
        assert "Invalid authorization header format" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_invalid_header_format_wrong_scheme(self, mock_auth_service):
        """Test header with wrong scheme (not Bearer)"""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id("Basic credentials", mock_auth_service)

        assert exc_info.value.status_code == 401
        assert "Invalid authorization header format" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_invalid_header_format_too_many_parts(self, mock_auth_service):
        """Test header with too many parts"""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id("Bearer token extra", mock_auth_service)

        assert exc_info.value.status_code == 401
        assert "Invalid authorization header format" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self, mock_auth_service):
        """Test that invalid token returns 401"""
        mock_auth_service.verify_token.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id("Bearer invalid_token", mock_auth_service)

        assert exc_info.value.status_code == 401
        assert "Invalid or expired token" in exc_info.value.detail
        mock_auth_service.verify_token.assert_called_once_with("invalid_token")

    @pytest.mark.asyncio
    async def test_valid_token_returns_user_id(self, mock_auth_service):
        """Test successful token verification"""
        mock_auth_service.verify_token.return_value = "user_123"

        result = await get_current_user_id("Bearer valid_token", mock_auth_service)

        assert result == "user_123"
        mock_auth_service.verify_token.assert_called_once_with("valid_token")

    @pytest.mark.asyncio
    async def test_bearer_case_insensitive(self, mock_auth_service):
        """Test that Bearer keyword is case-insensitive"""
        mock_auth_service.verify_token.return_value = "user_123"

        # Test lowercase
        result = await get_current_user_id("bearer valid_token", mock_auth_service)
        assert result == "user_123"

        # Test uppercase
        mock_auth_service.verify_token.reset_mock()
        mock_auth_service.verify_token.return_value = "user_123"
        result = await get_current_user_id("BEARER valid_token", mock_auth_service)
        assert result == "user_123"


# ===== get_current_user Tests =====


class TestGetCurrentUser:
    """Test get_current_user dependency"""

    @pytest.mark.asyncio
    async def test_user_found_returns_user(self, mock_user_repo, sample_user):
        """Test successful user retrieval"""
        mock_user_repo.get_by_id.return_value = sample_user

        result = await get_current_user("user_123", mock_user_repo)

        assert result == sample_user
        assert result.user_id == "user_123"
        mock_user_repo.get_by_id.assert_called_once_with("user_123")

    @pytest.mark.asyncio
    async def test_user_not_found_returns_401(self, mock_user_repo):
        """Test user not found returns 401"""
        mock_user_repo.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user("nonexistent_user", mock_user_repo)

        assert exc_info.value.status_code == 401
        assert "User not found" in exc_info.value.detail
        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}


# ===== require_admin Tests =====


class TestRequireAdmin:
    """Test require_admin dependency"""

    @pytest.mark.asyncio
    async def test_valid_admin_secret_succeeds(self, mock_user_repo, mock_auth_service):
        """Test admin access via valid admin secret header"""
        with patch("src.core.config.get_settings") as mock_settings:
            mock_settings.return_value.admin_secret = "test_admin_secret"

            # Should not raise - valid admin secret
            result = await require_admin(
                x_admin_secret="test_admin_secret",
                authorization=None,
                user_repo=mock_user_repo,
                auth_service=mock_auth_service,
            )

            assert result is None  # Function returns None on success

    @pytest.mark.asyncio
    async def test_invalid_admin_secret_returns_401(
        self, mock_user_repo, mock_auth_service
    ):
        """Test admin access with invalid admin secret returns 401"""
        with patch("src.core.config.get_settings") as mock_settings:
            mock_settings.return_value.admin_secret = "correct_secret"

            with pytest.raises(HTTPException) as exc_info:
                await require_admin(
                    x_admin_secret="wrong_secret",
                    authorization=None,
                    user_repo=mock_user_repo,
                    auth_service=mock_auth_service,
                )

            assert exc_info.value.status_code == 401
            assert "Invalid admin secret" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_admin_jwt_token_succeeds(
        self, mock_user_repo, mock_auth_service, admin_user
    ):
        """Test admin access via JWT token with admin user"""
        mock_auth_service.verify_token.return_value = "admin_456"
        mock_user_repo.get_by_id.return_value = admin_user

        with patch("src.core.config.get_settings") as mock_settings:
            mock_settings.return_value.admin_secret = "some_secret"

            result = await require_admin(
                x_admin_secret=None,
                authorization="Bearer admin_token",
                user_repo=mock_user_repo,
                auth_service=mock_auth_service,
            )

            assert result is None  # Function returns None on success
            mock_auth_service.verify_token.assert_called_once_with("admin_token")
            mock_user_repo.get_by_id.assert_called_once_with("admin_456")

    @pytest.mark.asyncio
    async def test_non_admin_jwt_returns_403(
        self, mock_user_repo, mock_auth_service, sample_user
    ):
        """Test non-admin user JWT returns 403 Forbidden"""
        mock_auth_service.verify_token.return_value = "user_123"
        mock_user_repo.get_by_id.return_value = sample_user  # admin=False

        with patch("src.core.config.get_settings") as mock_settings:
            mock_settings.return_value.admin_secret = "some_secret"

            with pytest.raises(HTTPException) as exc_info:
                await require_admin(
                    x_admin_secret=None,
                    authorization="Bearer user_token",
                    user_repo=mock_user_repo,
                    auth_service=mock_auth_service,
                )

            assert exc_info.value.status_code == 403
            assert "Admin privileges required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_user_not_found_returns_403(self, mock_user_repo, mock_auth_service):
        """Test JWT with user not found returns 403"""
        mock_auth_service.verify_token.return_value = "user_123"
        mock_user_repo.get_by_id.return_value = None  # User not found

        with patch("src.core.config.get_settings") as mock_settings:
            mock_settings.return_value.admin_secret = "some_secret"

            with pytest.raises(HTTPException) as exc_info:
                await require_admin(
                    x_admin_secret=None,
                    authorization="Bearer user_token",
                    user_repo=mock_user_repo,
                    auth_service=mock_auth_service,
                )

            assert exc_info.value.status_code == 403
            assert "Admin privileges required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_invalid_jwt_token_returns_401(
        self, mock_user_repo, mock_auth_service
    ):
        """Test invalid JWT token returns 401"""
        mock_auth_service.verify_token.return_value = None

        with patch("src.core.config.get_settings") as mock_settings:
            mock_settings.return_value.admin_secret = "some_secret"

            with pytest.raises(HTTPException) as exc_info:
                await require_admin(
                    x_admin_secret=None,
                    authorization="Bearer invalid_token",
                    user_repo=mock_user_repo,
                    auth_service=mock_auth_service,
                )

            assert exc_info.value.status_code == 401
            assert "Admin authentication required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_no_auth_provided_returns_401(self, mock_user_repo, mock_auth_service):
        """Test no authentication method provided returns 401"""
        with patch("src.core.config.get_settings") as mock_settings:
            mock_settings.return_value.admin_secret = "some_secret"

            with pytest.raises(HTTPException) as exc_info:
                await require_admin(
                    x_admin_secret=None,
                    authorization=None,
                    user_repo=mock_user_repo,
                    auth_service=mock_auth_service,
                )

            assert exc_info.value.status_code == 401
            assert "Admin authentication required" in exc_info.value.detail
            assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}

    @pytest.mark.asyncio
    async def test_malformed_bearer_header_returns_401(
        self, mock_user_repo, mock_auth_service
    ):
        """Test malformed Bearer header falls through to 401"""
        with patch("src.core.config.get_settings") as mock_settings:
            mock_settings.return_value.admin_secret = "some_secret"

            with pytest.raises(HTTPException) as exc_info:
                await require_admin(
                    x_admin_secret=None,
                    authorization="NotBearer token",  # Wrong scheme
                    user_repo=mock_user_repo,
                    auth_service=mock_auth_service,
                )

            assert exc_info.value.status_code == 401
            assert "Admin authentication required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_admin_secret_takes_priority_over_jwt(
        self, mock_user_repo, mock_auth_service
    ):
        """Test admin secret header is checked before JWT"""
        with patch("src.core.config.get_settings") as mock_settings:
            mock_settings.return_value.admin_secret = "valid_secret"

            # Both admin secret and JWT provided, but secret is valid
            result = await require_admin(
                x_admin_secret="valid_secret",
                authorization="Bearer some_token",
                user_repo=mock_user_repo,
                auth_service=mock_auth_service,
            )

            assert result is None
            # verify_token should NOT be called because admin secret succeeded first
            mock_auth_service.verify_token.assert_not_called()


# ===== Dependency Factory Tests =====


class TestDependencyFactories:
    """Test dependency factory functions"""

    def test_get_user_repository(self):
        """Test get_user_repository creates repository from MongoDB"""
        mock_mongodb = Mock()
        mock_collection = Mock()
        mock_mongodb.get_collection.return_value = mock_collection

        repo = get_user_repository(mock_mongodb)

        mock_mongodb.get_collection.assert_called_once_with("users")
        # Verify it's a UserRepository instance
        from src.database.repositories.user_repository import UserRepository

        assert isinstance(repo, UserRepository)

    def test_get_auth_service(self):
        """Test get_auth_service creates AuthService from repository"""
        mock_user_repo = Mock()

        service = get_auth_service(mock_user_repo)

        # Verify it's an AuthService instance
        from src.services.auth_service import AuthService

        assert isinstance(service, AuthService)
