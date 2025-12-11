"""
Comprehensive unit tests for AuthService.

Tests authentication service including:
- User registration
- Login with password
- Email verification
- JWT token creation and validation
- Password reset
- User retrieval
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from jose import jwt

from src.database.repositories.user_repository import UserRepository
from src.models.user import User
from src.services.auth_service import AuthService

# ===== Fixtures =====


@pytest.fixture
def mock_user_repo():
    """Mock UserRepository"""
    repo = Mock(spec=UserRepository)
    repo.create = AsyncMock()
    repo.get_by_email = AsyncMock()
    repo.get_by_username = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.update = AsyncMock()
    repo.update_last_login = AsyncMock()
    # Mock collection for direct MongoDB operations
    repo.collection = Mock()
    repo.collection.update_one = AsyncMock()
    return repo


@pytest.fixture
def mock_redis():
    """Mock Redis cache"""
    redis = Mock()
    redis.get = AsyncMock()
    redis.set = AsyncMock()
    redis.delete = AsyncMock()
    return redis


@pytest.fixture
def auth_service(mock_user_repo, mock_redis):
    """Create AuthService instance"""
    return AuthService(mock_user_repo, mock_redis)


@pytest.fixture
def sample_user():
    """Sample user object"""
    return User(
        user_id="user_123",
        username="testuser",
        email="test@example.com",
        hashed_password="$2b$12$hashed_password_here",
        is_active=True,
        created_at=datetime.now()
    )


# ===== Registration Tests =====


class TestUserRegistration:
    """Test user registration functionality"""

    @pytest.mark.asyncio
    async def test_register_user_success(self, auth_service, mock_user_repo):
        """Test successful user registration"""
        # Arrange
        # Mock email verification
        auth_service.email_provider.verify_code = AsyncMock(return_value=True)

        # Mock repository checks
        mock_user_repo.get_by_email.return_value = None  # Email doesn't exist
        mock_user_repo.get_by_username.return_value = None  # Username doesn't exist

        new_user = User(
            user_id="user_456",
            username="newuser",
            email="new@example.com",
            hashed_password="hashed_pass",
            is_active=True,
            email_verified=True,
            created_at=datetime.now()
        )
        mock_user_repo.create.return_value = new_user

        # Act
        user, token = await auth_service.register_user(
            email="new@example.com",
            code="123456",
            username="newuser",
            password="SecureP@ssw0rd"
        )

        # Assert
        assert user.username == "newuser"
        assert user.email == "new@example.com"
        assert token is not None
        assert isinstance(token, str)
        auth_service.email_provider.verify_code.assert_called_once_with("new@example.com", "123456")
        mock_user_repo.get_by_email.assert_called_once_with("new@example.com")
        mock_user_repo.get_by_username.assert_called_once_with("newuser")
        mock_user_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_user_duplicate_email(self, auth_service, mock_user_repo, sample_user):
        """Test registration with duplicate email"""
        # Arrange
        # Mock email verification
        auth_service.email_provider.verify_code = AsyncMock(return_value=True)

        # Mock repository - email exists
        mock_user_repo.get_by_email.return_value = sample_user  # Email exists

        # Act & Assert
        with pytest.raises(ValueError, match="Email already registered"):
            await auth_service.register_user(
                email="test@example.com",
                code="123456",
                username="duplicate",
                password="Password123"
            )


# ===== Login Tests =====


class TestLoginWithPassword:
    """Test password-based login"""

    @pytest.mark.asyncio
    @patch("src.services.auth_service.verify_password")
    async def test_login_success(self, mock_verify, auth_service, mock_user_repo, sample_user):
        """Test successful login with correct password"""
        # Arrange
        # Add password_hash attribute to sample_user
        sample_user.password_hash = "$2b$12$hashed_password_here"
        mock_user_repo.get_by_username.return_value = sample_user
        mock_user_repo.update_last_login.return_value = sample_user
        mock_verify.return_value = True

        # Act
        user, token = await auth_service.login_with_password("testuser", "correct_password")

        # Assert
        assert user.username == "testuser"
        assert token is not None
        assert isinstance(token, str)
        mock_verify.assert_called_once_with("correct_password", sample_user.password_hash)

    @pytest.mark.asyncio
    async def test_login_user_not_found(self, auth_service, mock_user_repo):
        """Test login with non-existent username"""
        # Arrange
        mock_user_repo.get_by_username.return_value = None

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid username or password"):
            await auth_service.login_with_password("nonexistent", "password")

    @pytest.mark.asyncio
    @patch("src.services.auth_service.verify_password")
    async def test_login_wrong_password(self, mock_verify, auth_service, mock_user_repo, sample_user):
        """Test login with wrong password"""
        # Arrange
        # Add password_hash attribute to sample_user
        sample_user.password_hash = "$2b$12$hashed_password_here"
        mock_user_repo.get_by_username.return_value = sample_user
        mock_verify.return_value = False

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid username or password"):
            await auth_service.login_with_password("testuser", "wrong_password")


# ===== Email Verification Tests =====


class TestEmailVerification:
    """Test email verification code flow"""

    @pytest.mark.asyncio
    async def test_send_code_email(self, auth_service):
        """Test sending verification code to email"""
        # Mock email provider
        auth_service.email_provider.send_verification_code = AsyncMock(return_value="123456")

        # Act
        code = await auth_service.send_code_email("test@example.com")

        # Assert
        assert code == "123456"
        auth_service.email_provider.send_verification_code.assert_called_once_with("test@example.com")

    @pytest.mark.asyncio
    async def test_verify_and_login_email_success(self, auth_service, mock_user_repo, sample_user):
        """Test verify email code and login"""
        # Arrange
        auth_service.email_provider.verify_code = AsyncMock(return_value=True)
        mock_user_repo.get_by_email.return_value = sample_user
        mock_user_repo.update_last_login.return_value = sample_user

        # Act
        user, token = await auth_service.verify_and_login("email", "test@example.com", code="123456")

        # Assert
        assert user.email == "test@example.com"
        assert token is not None
        auth_service.email_provider.verify_code.assert_called_once_with("test@example.com", "123456")

    @pytest.mark.asyncio
    async def test_verify_and_login_email_invalid_code(self, auth_service):
        """Test email login with invalid code"""
        # Arrange
        auth_service.email_provider.verify_code = AsyncMock(return_value=False)

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid verification code"):
            await auth_service.verify_and_login("email", "test@example.com", code="wrong")

    @pytest.mark.asyncio
    async def test_verify_and_login_missing_code(self, auth_service):
        """Test email login without providing code"""
        # Act & Assert
        with pytest.raises(ValueError, match="Verification code required"):
            await auth_service.verify_and_login("email", "test@example.com", code=None)


# ===== JWT Token Tests =====


class TestJWTTokens:
    """Test JWT token creation and validation"""

    def test_create_access_token(self, auth_service):
        """Test access token creation"""
        # Act
        token = auth_service.create_access_token("user_123")

        # Assert
        assert token is not None
        assert isinstance(token, str)

        # Verify token structure
        from src.core.config import get_settings
        settings = get_settings()
        payload = jwt.decode(token, settings.secret_key, algorithms=[AuthService.ALGORITHM])
        assert payload["sub"] == "user_123"
        assert "exp" in payload

    def test_verify_token_valid(self, auth_service):
        """Test verification of valid token"""
        # Arrange
        token = auth_service.create_access_token("user_123")

        # Act
        user_id = auth_service.verify_token(token)

        # Assert
        assert user_id == "user_123"

    def test_verify_token_expired(self, auth_service):
        """Test verification of expired token"""
        # Arrange - Create token that expired 1 hour ago
        from src.core.config import get_settings
        settings = get_settings()

        expire = datetime.utcnow() - timedelta(hours=1)  # Expired
        payload = {"sub": "user_123", "exp": expire}
        expired_token = jwt.encode(payload, settings.secret_key, algorithm=AuthService.ALGORITHM)

        # Act
        user_id = auth_service.verify_token(expired_token)

        # Assert
        assert user_id is None  # Expired tokens should return None

    def test_verify_token_invalid_signature(self, auth_service):
        """Test verification of token with invalid signature"""
        # Arrange - Create token with wrong secret
        payload = {"sub": "user_123", "exp": datetime.utcnow() + timedelta(days=1)}
        invalid_token = jwt.encode(payload, "wrong_secret_key", algorithm=AuthService.ALGORITHM)

        # Act
        user_id = auth_service.verify_token(invalid_token)

        # Assert
        assert user_id is None


# ===== Password Reset Tests =====


class TestPasswordReset:
    """Test password reset functionality"""

    @pytest.mark.asyncio
    async def test_reset_password_success(self, auth_service, mock_user_repo, sample_user):
        """Test successful password reset"""
        # Arrange
        # Mock email verification
        auth_service.email_provider.verify_code = AsyncMock(return_value=True)
        mock_user_repo.get_by_email.return_value = sample_user
        mock_user_repo.update_last_login.return_value = sample_user

        # Act
        user, token = await auth_service.reset_password("test@example.com", "123456", "NewP@ssw0rd123")

        # Assert
        assert user.email == "test@example.com"
        assert token is not None
        assert isinstance(token, str)
        auth_service.email_provider.verify_code.assert_called_once_with("test@example.com", "123456")
        # Check that collection.update_one was called to update password
        mock_user_repo.collection.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_reset_password_user_not_found(self, auth_service, mock_user_repo):
        """Test password reset for non-existent user"""
        # Arrange
        # Mock email verification
        auth_service.email_provider.verify_code = AsyncMock(return_value=True)
        mock_user_repo.get_by_email.return_value = None

        # Act & Assert
        with pytest.raises(ValueError, match="No account found with this email address"):
            await auth_service.reset_password("nonexistent@example.com", "123456", "NewPassword123")


# ===== User Retrieval Tests =====


class TestGetCurrentUser:
    """Test user retrieval by token"""

    @pytest.mark.asyncio
    async def test_get_current_user_success(self, auth_service, mock_user_repo, sample_user):
        """Test get user with valid token"""
        # Arrange
        token = auth_service.create_access_token("user_123")
        mock_user_repo.get_by_id.return_value = sample_user

        # Act
        user = await auth_service.get_current_user(token)

        # Assert
        assert user is not None
        assert user.user_id == "user_123"
        mock_user_repo.get_by_id.assert_called_once_with("user_123")

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, auth_service, mock_user_repo):
        """Test get user with invalid token"""
        # Act
        user = await auth_service.get_current_user("invalid_token")

        # Assert
        assert user is None
        mock_user_repo.get_by_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_current_user_not_found(self, auth_service, mock_user_repo):
        """Test get user when user doesn't exist in DB"""
        # Arrange
        token = auth_service.create_access_token("user_999")
        mock_user_repo.get_by_id.return_value = None

        # Act
        user = await auth_service.get_current_user(token)

        # Assert
        assert user is None


# ===== Edge Cases & Error Handling =====


class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.mark.asyncio
    async def test_verify_and_login_unsupported_auth_type(self, auth_service):
        """Test with unsupported authentication type"""
        # Act & Assert
        with pytest.raises(ValueError, match="Unsupported auth type"):
            await auth_service.verify_and_login("unsupported", "identifier", code="123")

    def test_token_expiry_configuration(self, auth_service):
        """Test that token expiry is properly configured"""
        assert AuthService.ACCESS_TOKEN_EXPIRE_MINUTES == 60 * 24 * 7  # 7 days
        assert AuthService.ALGORITHM == "HS256"
