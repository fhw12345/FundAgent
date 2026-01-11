"""
Comprehensive unit tests for Auth API endpoints.

Tests all authentication endpoints including:
- Send verification code
- Verify code and login
- Register new user
- Login with password
- Reset password
- Get current user (with Authorization header)
- Refresh access token
- Logout
- Logout from all devices

Story 3.2: Tests Authorization header pattern (security improvement).
"""

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.api.auth import (
    get_auth_service,
    get_current_user_endpoint,
    get_refresh_token_repository,
    get_token_service,
    login_with_password,
    logout,
    logout_all_devices,
    refresh_access_token,
    register_user,
    reset_password,
    send_verification_code,
    verify_code_and_login,
)
from src.api.schemas.auth_schemas import (
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SendCodeRequest,
    VerifyCodeRequest,
)
from src.models.refresh_token import TokenPair
from src.models.user import User


# ===== Fixtures =====


@pytest.fixture
def mock_auth_service():
    """Mock AuthService"""
    service = Mock()
    service.send_code_email = AsyncMock()
    service.verify_and_login = AsyncMock()
    service.register_user = AsyncMock()
    service.login_with_password = AsyncMock()
    service.reset_password = AsyncMock()
    service.get_current_user = AsyncMock()
    return service


@pytest.fixture
def mock_token_service():
    """Mock TokenService"""
    service = Mock()
    service.create_token_pair = AsyncMock()
    service.refresh_access_token = AsyncMock()
    service.revoke_token = AsyncMock()
    service.revoke_all_user_tokens = AsyncMock()
    return service


@pytest.fixture
def sample_user():
    """Sample user for testing"""
    return User(
        user_id="user_123",
        username="testuser",
        email="test@example.com",
        hashed_password="hashed_password",
        is_active=True,
        created_at=datetime.now(),
    )


@pytest.fixture
def sample_token_pair():
    """Sample token pair for testing"""
    return TokenPair(
        access_token="access_token_123",
        refresh_token="refresh_token_456",
        token_type="bearer",
        expires_in=1800,  # 30 minutes
        refresh_expires_in=604800,  # 7 days
    )


@pytest.fixture
def mock_http_request():
    """Mock FastAPI Request object"""
    request = Mock()
    request.headers = {"user-agent": "Mozilla/5.0 Test"}
    request.client = Mock()
    request.client.host = "127.0.0.1"
    return request


# ===== Send Verification Code Tests =====


class TestSendVerificationCode:
    """Test POST /api/auth/send-code endpoint"""

    @pytest.mark.asyncio
    async def test_send_code_email_success(self, mock_auth_service):
        """Test successful email verification code sending"""
        # Arrange
        mock_auth_service.send_code_email.return_value = None
        request = SendCodeRequest(auth_type="email", identifier="test@example.com")

        # Act
        response = await send_verification_code(request, mock_auth_service)

        # Assert
        assert response.message == "Verification code sent to test@example.com"
        assert response.code is None  # Code should never be returned
        mock_auth_service.send_code_email.assert_called_once_with("test@example.com")

    @pytest.mark.asyncio
    async def test_send_code_phone_not_implemented(self, mock_auth_service):
        """Test phone verification returns 501 Not Implemented"""
        # Arrange
        request = SendCodeRequest(auth_type="phone", identifier="+1234567890")

        # Act & Assert
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await send_verification_code(request, mock_auth_service)

        assert exc_info.value.status_code == 501
        assert "not yet implemented" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_send_code_service_error(self, mock_auth_service):
        """Test service error returns 500"""
        # Arrange
        mock_auth_service.send_code_email.side_effect = Exception("SMTP error")
        request = SendCodeRequest(auth_type="email", identifier="test@example.com")

        # Act & Assert
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await send_verification_code(request, mock_auth_service)

        assert exc_info.value.status_code == 500
        assert "SMTP error" in exc_info.value.detail


# ===== Verify Code and Login Tests =====


class TestVerifyCodeAndLogin:
    """Test POST /api/auth/verify-code endpoint"""

    @pytest.mark.asyncio
    async def test_verify_code_success(
        self,
        mock_auth_service,
        mock_token_service,
        mock_http_request,
        sample_user,
        sample_token_pair,
    ):
        """Test successful code verification and login"""
        # Arrange
        mock_auth_service.verify_and_login.return_value = (sample_user, "old_token")
        mock_token_service.create_token_pair.return_value = sample_token_pair
        request = VerifyCodeRequest(
            auth_type="email", identifier="test@example.com", code="123456"
        )

        # Act
        response = await verify_code_and_login(
            request, mock_http_request, mock_auth_service, mock_token_service
        )

        # Assert
        assert response.access_token == "access_token_123"
        assert response.refresh_token == "refresh_token_456"
        assert response.user.user_id == "user_123"
        mock_auth_service.verify_and_login.assert_called_once_with(
            auth_type="email", identifier="test@example.com", code="123456"
        )

    @pytest.mark.asyncio
    async def test_verify_code_invalid(
        self, mock_auth_service, mock_token_service, mock_http_request
    ):
        """Test invalid verification code returns 401"""
        # Arrange
        mock_auth_service.verify_and_login.side_effect = ValueError(
            "Invalid verification code"
        )
        request = VerifyCodeRequest(
            auth_type="email", identifier="test@example.com", code="wrong"
        )

        # Act & Assert
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await verify_code_and_login(
                request, mock_http_request, mock_auth_service, mock_token_service
            )

        assert exc_info.value.status_code == 401


# ===== Register User Tests =====


class TestRegisterUser:
    """Test POST /api/auth/register endpoint"""

    @pytest.mark.asyncio
    async def test_register_success(
        self,
        mock_auth_service,
        mock_token_service,
        mock_http_request,
        sample_user,
        sample_token_pair,
    ):
        """Test successful user registration"""
        # Arrange
        mock_auth_service.register_user.return_value = (sample_user, "token")
        mock_token_service.create_token_pair.return_value = sample_token_pair
        request = RegisterRequest(
            email="new@example.com",
            code="123456",
            username="newuser",
            password="SecurePass123!",
        )

        # Act
        response = await register_user(
            request, mock_http_request, mock_auth_service, mock_token_service
        )

        # Assert
        assert response.access_token == "access_token_123"
        assert response.user.user_id == "user_123"
        mock_auth_service.register_user.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_duplicate_email(
        self, mock_auth_service, mock_token_service, mock_http_request
    ):
        """Test registration with duplicate email returns 400"""
        # Arrange
        mock_auth_service.register_user.side_effect = ValueError(
            "Email already registered"
        )
        request = RegisterRequest(
            email="existing@example.com",
            code="123456",
            username="newuser",
            password="Pass123!",
        )

        # Act & Assert
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await register_user(
                request, mock_http_request, mock_auth_service, mock_token_service
            )

        assert exc_info.value.status_code == 400
        assert "already registered" in exc_info.value.detail


# ===== Login with Password Tests =====


class TestLoginWithPassword:
    """Test POST /api/auth/login endpoint"""

    @pytest.mark.asyncio
    async def test_login_success(
        self,
        mock_auth_service,
        mock_token_service,
        mock_http_request,
        sample_user,
        sample_token_pair,
    ):
        """Test successful password login"""
        # Arrange
        mock_auth_service.login_with_password.return_value = (sample_user, "token")
        mock_token_service.create_token_pair.return_value = sample_token_pair
        request = LoginRequest(username="testuser", password="correct_password")

        # Act
        response = await login_with_password(
            request, mock_http_request, mock_auth_service, mock_token_service
        )

        # Assert
        assert response.access_token == "access_token_123"
        assert response.token_type == "bearer"
        assert response.expires_in == 1800

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(
        self, mock_auth_service, mock_token_service, mock_http_request
    ):
        """Test login with invalid credentials returns 401"""
        # Arrange
        mock_auth_service.login_with_password.side_effect = ValueError(
            "Invalid username or password"
        )
        request = LoginRequest(username="testuser", password="wrong_password")

        # Act & Assert
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await login_with_password(
                request, mock_http_request, mock_auth_service, mock_token_service
            )

        assert exc_info.value.status_code == 401


# ===== Reset Password Tests =====


class TestResetPassword:
    """Test POST /api/auth/reset-password endpoint"""

    @pytest.mark.asyncio
    async def test_reset_password_success(
        self,
        mock_auth_service,
        mock_token_service,
        mock_http_request,
        sample_user,
        sample_token_pair,
    ):
        """Test successful password reset"""
        # Arrange
        mock_auth_service.reset_password.return_value = (sample_user, "token")
        mock_token_service.create_token_pair.return_value = sample_token_pair
        request = ResetPasswordRequest(
            email="test@example.com", code="123456", new_password="NewPass123!"
        )

        # Act
        response = await reset_password(
            request, mock_http_request, mock_auth_service, mock_token_service
        )

        # Assert
        assert response.access_token == "access_token_123"
        mock_auth_service.reset_password.assert_called_once()

    @pytest.mark.asyncio
    async def test_reset_password_user_not_found(
        self, mock_auth_service, mock_token_service, mock_http_request
    ):
        """Test password reset for non-existent user returns 400"""
        # Arrange
        mock_auth_service.reset_password.side_effect = ValueError(
            "No account found with this email"
        )
        request = ResetPasswordRequest(
            email="nonexistent@example.com", code="123456", new_password="NewPass123!"
        )

        # Act & Assert
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await reset_password(
                request, mock_http_request, mock_auth_service, mock_token_service
            )

        assert exc_info.value.status_code == 400


# ===== Get Current User Tests (Authorization Header) =====


class TestGetCurrentUser:
    """
    Test GET /api/auth/me endpoint.

    Story 3.2: Tests Authorization header security pattern.
    """

    @pytest.mark.asyncio
    async def test_get_current_user_success(self, mock_auth_service, sample_user):
        """Test get current user with valid Authorization header"""
        # Arrange
        mock_auth_service.get_current_user.return_value = sample_user
        authorization = "Bearer valid_access_token"

        # Act
        user = await get_current_user_endpoint(authorization, mock_auth_service)

        # Assert
        assert user.user_id == "user_123"
        assert user.email == "test@example.com"
        mock_auth_service.get_current_user.assert_called_once_with("valid_access_token")

    @pytest.mark.asyncio
    async def test_get_current_user_missing_header(self, mock_auth_service):
        """Test missing Authorization header returns 401"""
        # Act & Assert
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_endpoint(None, mock_auth_service)

        assert exc_info.value.status_code == 401
        assert "Authorization header required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_header_format(self, mock_auth_service):
        """Test invalid Authorization header format returns 401"""
        # Act & Assert - Missing 'Bearer' prefix
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_endpoint("InvalidToken", mock_auth_service)

        assert exc_info.value.status_code == 401
        assert "Invalid authorization header format" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_bearer_format(self, mock_auth_service):
        """Test Authorization header with wrong format returns 401"""
        # Act & Assert - Too many parts
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_endpoint(
                "Bearer token extra_part", mock_auth_service
            )

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_expired_token(self, mock_auth_service):
        """Test expired token returns 401"""
        # Arrange
        mock_auth_service.get_current_user.return_value = None
        authorization = "Bearer expired_token"

        # Act & Assert
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_endpoint(authorization, mock_auth_service)

        assert exc_info.value.status_code == 401
        assert "Invalid or expired token" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_current_user_case_insensitive_bearer(
        self, mock_auth_service, sample_user
    ):
        """Test 'bearer' (lowercase) is accepted in Authorization header"""
        # Arrange
        mock_auth_service.get_current_user.return_value = sample_user
        authorization = "bearer valid_token"  # lowercase

        # Act
        user = await get_current_user_endpoint(authorization, mock_auth_service)

        # Assert
        assert user.user_id == "user_123"


# ===== Refresh Access Token Tests =====


class TestRefreshAccessToken:
    """Test POST /api/auth/refresh endpoint"""

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, mock_token_service, sample_token_pair):
        """Test successful token refresh with rotation"""
        # Arrange
        mock_token_service.refresh_access_token.return_value = sample_token_pair
        request = RefreshTokenRequest(refresh_token="old_refresh_token")

        # Act
        response = await refresh_access_token(request, mock_token_service)

        # Assert
        assert response.access_token == "access_token_123"
        assert response.refresh_token == "refresh_token_456"
        mock_token_service.refresh_access_token.assert_called_once_with(
            refresh_token="old_refresh_token", rotate=True
        )

    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self, mock_token_service):
        """Test invalid refresh token returns 401"""
        # Arrange
        mock_token_service.refresh_access_token.side_effect = ValueError(
            "Invalid or expired refresh token"
        )
        request = RefreshTokenRequest(refresh_token="invalid_token")

        # Act & Assert
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await refresh_access_token(request, mock_token_service)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token_rotation_failed(self, mock_token_service):
        """Test token rotation failure returns 500"""
        # Arrange - Simulate rotation returning just a string instead of TokenPair
        mock_token_service.refresh_access_token.return_value = "just_a_string"
        request = RefreshTokenRequest(refresh_token="refresh_token")

        # Act & Assert
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await refresh_access_token(request, mock_token_service)

        assert exc_info.value.status_code == 500
        # The inner HTTPException is caught and re-raised with generic message
        assert "Token" in exc_info.value.detail and "failed" in exc_info.value.detail


# ===== Logout Tests =====


class TestLogout:
    """Test POST /api/auth/logout endpoint"""

    @pytest.mark.asyncio
    async def test_logout_success(self, mock_token_service):
        """Test successful logout"""
        # Arrange
        mock_token_service.revoke_token.return_value = True
        request = LogoutRequest(refresh_token="valid_refresh_token")

        # Act
        response = await logout(request, mock_token_service)

        # Assert
        assert response["message"] == "Logged out successfully"
        mock_token_service.revoke_token.assert_called_once_with("valid_refresh_token")

    @pytest.mark.asyncio
    async def test_logout_invalid_token_still_succeeds(self, mock_token_service):
        """Test logout with invalid token still returns success"""
        # Arrange - Token not found or already revoked
        mock_token_service.revoke_token.return_value = False
        request = LogoutRequest(refresh_token="invalid_token")

        # Act
        response = await logout(request, mock_token_service)

        # Assert - Should still succeed gracefully
        assert response["message"] == "Logged out successfully"

    @pytest.mark.asyncio
    async def test_logout_service_error(self, mock_token_service):
        """Test logout service error returns 500"""
        # Arrange
        mock_token_service.revoke_token.side_effect = Exception("Database error")
        request = LogoutRequest(refresh_token="refresh_token")

        # Act & Assert
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await logout(request, mock_token_service)

        assert exc_info.value.status_code == 500


# ===== Logout All Devices Tests (Authorization Header) =====


class TestLogoutAllDevices:
    """
    Test POST /api/auth/logout-all endpoint.

    Story 3.2: Tests Authorization header security pattern.
    """

    @pytest.mark.asyncio
    async def test_logout_all_success(
        self, mock_auth_service, mock_token_service, sample_user
    ):
        """Test successful logout from all devices"""
        # Arrange
        mock_auth_service.get_current_user.return_value = sample_user
        mock_token_service.revoke_all_user_tokens.return_value = 3
        authorization = "Bearer valid_token"

        # Act
        response = await logout_all_devices(
            authorization, mock_auth_service, mock_token_service
        )

        # Assert
        assert "3 tokens revoked" in response["message"]
        mock_token_service.revoke_all_user_tokens.assert_called_once_with("user_123")

    @pytest.mark.asyncio
    async def test_logout_all_missing_header(
        self, mock_auth_service, mock_token_service
    ):
        """Test missing Authorization header returns 401"""
        # Act & Assert
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await logout_all_devices(None, mock_auth_service, mock_token_service)

        assert exc_info.value.status_code == 401
        assert "Authorization header required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_logout_all_invalid_header_format(
        self, mock_auth_service, mock_token_service
    ):
        """Test invalid Authorization header format returns 401"""
        # Act & Assert
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await logout_all_devices(
                "InvalidFormat", mock_auth_service, mock_token_service
            )

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_logout_all_expired_token(
        self, mock_auth_service, mock_token_service
    ):
        """Test expired token returns 401"""
        # Arrange
        mock_auth_service.get_current_user.return_value = None
        authorization = "Bearer expired_token"

        # Act & Assert
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await logout_all_devices(
                authorization, mock_auth_service, mock_token_service
            )

        assert exc_info.value.status_code == 401
        assert "Invalid or expired token" in exc_info.value.detail


# ===== Dependency Injection Tests =====


class TestDependencyInjection:
    """Test dependency injection functions"""

    def test_get_refresh_token_repository(self):
        """Test refresh token repository creation"""
        # Arrange
        mock_mongodb = Mock()
        mock_collection = Mock()
        mock_mongodb.get_collection.return_value = mock_collection

        # Act
        repo = get_refresh_token_repository(mock_mongodb)

        # Assert
        mock_mongodb.get_collection.assert_called_once_with("refresh_tokens")
        assert repo is not None

    def test_get_token_service(self):
        """Test token service creation"""
        # Arrange
        mock_repo = Mock()

        # Act
        service = get_token_service(mock_repo)

        # Assert
        assert service is not None

    def test_get_auth_service(self):
        """Test auth service creation"""
        # Arrange
        mock_user_repo = Mock()
        mock_redis = Mock()

        # Act
        service = get_auth_service(mock_user_repo, mock_redis)

        # Assert
        assert service is not None
