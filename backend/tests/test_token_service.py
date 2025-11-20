"""
Unit tests for JWT token service.

Tests JWT access/refresh token management including:
- Token pair creation (access + refresh tokens)
- Token refresh with rotation
- Token verification and validation
- Token revocation
- Security (hash token)
"""

import hashlib
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from jose import jwt

from src.models.refresh_token import RefreshToken
from src.models.user import User
from src.services.token_service import TokenService


# ===== Fixtures =====


@pytest.fixture
def mock_settings():
    """Mock settings with test secret key"""
    with patch("src.services.token_service.settings") as mock_settings:
        mock_settings.secret_key = "test_secret_key_for_testing"
        yield mock_settings


@pytest.fixture
def mock_refresh_token_repo():
    """Mock refresh token repository"""
    repo = Mock()
    repo.create = AsyncMock()
    repo.find_by_hash = AsyncMock()
    repo.update_last_used = AsyncMock()
    repo.revoke_by_hash = AsyncMock()
    repo.revoke_all_for_user = AsyncMock()
    repo.rotate_token_atomic = AsyncMock()
    return repo


@pytest.fixture
def token_service(mock_refresh_token_repo, mock_settings):
    """Token service instance"""
    return TokenService(mock_refresh_token_repo)


@pytest.fixture
def mock_user():
    """Mock user object"""
    return User(
        user_id="user_123456789012",
        email="test@example.com",
        username="testuser",
        password_hash=None,
        email_verified=True,
        is_admin=False,
        created_at=datetime.utcnow(),
        last_login=None,
    )


# ===== Token Pair Creation Tests =====


class TestCreateTokenPair:
    """Test access + refresh token pair creation"""

    @pytest.mark.asyncio
    async def test_create_token_pair_success(
        self, token_service, mock_user, mock_refresh_token_repo
    ):
        """Test successful token pair creation"""
        # Arrange
        user_agent = "Mozilla/5.0"
        ip_address = "192.168.1.100"

        # Act
        token_pair = await token_service.create_token_pair(
            mock_user, user_agent, ip_address
        )

        # Assert
        assert token_pair.access_token is not None
        assert token_pair.refresh_token is not None
        assert token_pair.token_type == "bearer"
        assert token_pair.expires_in == 30 * 60  # 30 minutes in seconds
        assert token_pair.refresh_expires_in == 7 * 24 * 3600  # 7 days in seconds

        # Verify refresh token was stored in database
        mock_refresh_token_repo.create.assert_called_once()
        stored_token = mock_refresh_token_repo.create.call_args[0][0]
        assert stored_token.user_id == mock_user.user_id
        assert stored_token.user_agent == user_agent
        assert stored_token.ip_address == ip_address
        assert stored_token.revoked is False

    @pytest.mark.asyncio
    async def test_create_token_pair_without_metadata(
        self, token_service, mock_user, mock_refresh_token_repo
    ):
        """Test token pair creation without user_agent/ip_address"""
        # Act
        token_pair = await token_service.create_token_pair(mock_user)

        # Assert
        assert token_pair.access_token is not None
        assert token_pair.refresh_token is not None

        # Verify stored token has None for metadata
        stored_token = mock_refresh_token_repo.create.call_args[0][0]
        assert stored_token.user_agent is None
        assert stored_token.ip_address is None

    @pytest.mark.asyncio
    async def test_create_token_pair_access_token_payload(
        self, token_service, mock_user, mock_settings
    ):
        """Test that access token contains correct payload"""
        # Act
        token_pair = await token_service.create_token_pair(mock_user)

        # Decode and verify payload (using same secret key from mock_settings fixture)
        payload = jwt.decode(
            token_pair.access_token, "test_secret_key_for_testing", algorithms=["HS256"]
        )

        # Assert
        assert payload["sub"] == mock_user.user_id
        assert payload["username"] == mock_user.username
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload
        assert "jti" in payload

    @pytest.mark.asyncio
    async def test_create_token_pair_refresh_token_payload(
        self, token_service, mock_user, mock_settings
    ):
        """Test that refresh token contains correct payload"""
        # Act
        token_pair = await token_service.create_token_pair(mock_user)

        # Decode and verify payload
        payload = jwt.decode(
            token_pair.refresh_token, "test_secret_key_for_testing", algorithms=["HS256"]
        )

        # Assert
        assert payload["sub"] == mock_user.user_id
        assert payload["type"] == "refresh"
        assert "token_value" in payload
        assert "exp" in payload
        assert "iat" in payload
        assert "jti" in payload


# ===== Access Token Creation Tests =====


class TestCreateAccessToken:
    """Test access token creation"""

    def test_create_access_token_structure(self, token_service, mock_user, mock_settings):
        """Test access token has correct structure and expiration"""
        # Act
        token = token_service._create_access_token(mock_user)
        payload = jwt.decode(token, "test_secret_key_for_testing", algorithms=["HS256"])

        # Assert
        assert payload["sub"] == mock_user.user_id
        assert payload["username"] == mock_user.username
        assert payload["type"] == "access"

        # Check expiration is approximately 30 minutes from now
        exp_timestamp = payload["exp"]
        exp_datetime = datetime.fromtimestamp(exp_timestamp)
        expected_exp = datetime.utcnow() + timedelta(minutes=30)
        assert abs((exp_datetime - expected_exp).total_seconds()) < 5  # Within 5 seconds

    def test_create_access_token_unique_jti(self, token_service, mock_user, mock_settings):
        """Test that each access token has unique JTI (JWT ID)"""
        # Act
        token1 = token_service._create_access_token(mock_user)
        token2 = token_service._create_access_token(mock_user)

        payload1 = jwt.decode(token1, "test_secret_key_for_testing", algorithms=["HS256"])
        payload2 = jwt.decode(token2, "test_secret_key_for_testing", algorithms=["HS256"])

        # Assert
        assert payload1["jti"] != payload2["jti"]


# ===== Token Hashing Tests =====


class TestHashToken:
    """Test token hashing"""

    def test_hash_token_produces_hex_string(self, token_service):
        """Test that hashing produces valid hex string"""
        # Arrange
        token = "test_token_value"

        # Act
        hashed = token_service._hash_token(token)

        # Assert
        assert isinstance(hashed, str)
        assert len(hashed) == 64  # SHA256 produces 64-character hex string
        # Verify all characters are hexadecimal
        assert all(c in "0123456789abcdef" for c in hashed)

    def test_hash_token_deterministic(self, token_service):
        """Test that same token always produces same hash"""
        # Arrange
        token = "consistent_token"

        # Act
        hash1 = token_service._hash_token(token)
        hash2 = token_service._hash_token(token)

        # Assert
        assert hash1 == hash2

    def test_hash_token_different_tokens_different_hashes(self, token_service):
        """Test that different tokens produce different hashes"""
        # Arrange
        token1 = "token_one"
        token2 = "token_two"

        # Act
        hash1 = token_service._hash_token(token1)
        hash2 = token_service._hash_token(token2)

        # Assert
        assert hash1 != hash2

    def test_hash_token_matches_hashlib_sha256(self, token_service):
        """Test that hashing matches hashlib.sha256"""
        # Arrange
        token = "verify_hash_algorithm"

        # Act
        service_hash = token_service._hash_token(token)
        expected_hash = hashlib.sha256(token.encode()).hexdigest()

        # Assert
        assert service_hash == expected_hash


# ===== Access Token Verification Tests =====


class TestVerifyAccessToken:
    """Test access token verification"""

    def test_verify_access_token_valid(self, token_service, mock_user, mock_settings):
        """Test verifying valid access token"""
        # Arrange
        token = token_service._create_access_token(mock_user)

        # Act
        user_id = token_service.verify_access_token(token)

        # Assert
        assert user_id == mock_user.user_id

    def test_verify_access_token_wrong_type(self, token_service, mock_settings):
        """Test verifying token with wrong type (refresh instead of access)"""
        # Arrange - create a refresh type token
        payload = {
            "sub": "user_123",
            "type": "refresh",  # Wrong type
            "exp": datetime.utcnow() + timedelta(days=7),
            "iat": datetime.utcnow(),
        }
        token = jwt.encode(payload, "test_secret_key_for_testing", algorithm="HS256")

        # Act
        user_id = token_service.verify_access_token(token)

        # Assert
        assert user_id is None

    def test_verify_access_token_expired(self, token_service):
        """Test verifying expired access token"""
        # Arrange - create expired token
        with patch("src.services.token_service.settings") as mock_settings:
            mock_settings.secret_key = "test_secret_key"
            payload = {
                "sub": "user_123",
                "type": "access",
                "exp": datetime.utcnow() - timedelta(minutes=1),  # Expired 1 min ago
                "iat": datetime.utcnow() - timedelta(minutes=31),
            }
            token = jwt.encode(payload, "test_secret_key", algorithm="HS256")

        # Act
        user_id = token_service.verify_access_token(token)

        # Assert
        assert user_id is None

    def test_verify_access_token_missing_sub(self, token_service):
        """Test verifying token missing user ID (sub)"""
        # Arrange - create token without sub
        with patch("src.services.token_service.settings") as mock_settings:
            mock_settings.secret_key = "test_secret_key"
            payload = {
                "type": "access",
                "exp": datetime.utcnow() + timedelta(minutes=30),
                "iat": datetime.utcnow(),
            }
            token = jwt.encode(payload, "test_secret_key", algorithm="HS256")

        # Act
        user_id = token_service.verify_access_token(token)

        # Assert
        assert user_id is None

    def test_verify_access_token_invalid_signature(self, token_service):
        """Test verifying token with invalid signature"""
        # Arrange - create token with different secret
        with patch("src.services.token_service.settings"):
            payload = {
                "sub": "user_123",
                "type": "access",
                "exp": datetime.utcnow() + timedelta(minutes=30),
                "iat": datetime.utcnow(),
            }
            token = jwt.encode(payload, "wrong_secret", algorithm="HS256")

        # Act
        user_id = token_service.verify_access_token(token)

        # Assert
        assert user_id is None

    def test_verify_access_token_malformed(self, token_service):
        """Test verifying malformed token"""
        # Arrange
        malformed_token = "not.a.valid.jwt.token"

        # Act
        user_id = token_service.verify_access_token(malformed_token)

        # Assert
        assert user_id is None


# ===== Token Revocation Tests =====


class TestRevokeToken:
    """Test token revocation"""

    @pytest.mark.asyncio
    async def test_revoke_token_success(
        self, token_service, mock_user, mock_refresh_token_repo
    ):
        """Test successful token revocation"""
        # Arrange
        with patch("src.services.token_service.settings") as mock_settings:
            mock_settings.secret_key = "test_secret_key"
            # Create refresh token
            token_value = "test_token_value"
            refresh_token = token_service._create_refresh_token_jwt(
                mock_user, token_value
            )

        mock_refresh_token_repo.revoke_by_hash.return_value = True

        # Act
        result = await token_service.revoke_token(refresh_token)

        # Assert
        assert result is True
        mock_refresh_token_repo.revoke_by_hash.assert_called_once()

    @pytest.mark.asyncio
    async def test_revoke_token_not_found(
        self, token_service, mock_user, mock_refresh_token_repo
    ):
        """Test revoking token that doesn't exist"""
        # Arrange
        with patch("src.services.token_service.settings") as mock_settings:
            mock_settings.secret_key = "test_secret_key"
            token_value = "nonexistent_token"
            refresh_token = token_service._create_refresh_token_jwt(
                mock_user, token_value
            )

        mock_refresh_token_repo.revoke_by_hash.return_value = False

        # Act
        result = await token_service.revoke_token(refresh_token)

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_revoke_token_malformed(
        self, token_service, mock_refresh_token_repo
    ):
        """Test revoking malformed token"""
        # Arrange
        malformed_token = "not.a.valid.token"

        # Act
        result = await token_service.revoke_token(malformed_token)

        # Assert
        assert result is False
        mock_refresh_token_repo.revoke_by_hash.assert_not_called()

    @pytest.mark.asyncio
    async def test_revoke_all_user_tokens(
        self, token_service, mock_refresh_token_repo
    ):
        """Test revoking all tokens for a user"""
        # Arrange
        user_id = "user_123"
        mock_refresh_token_repo.revoke_all_for_user.return_value = 3

        # Act
        count = await token_service.revoke_all_user_tokens(user_id)

        # Assert
        assert count == 3
        mock_refresh_token_repo.revoke_all_for_user.assert_called_once_with(user_id)


# ===== Token Refresh Tests =====


class TestRefreshAccessToken:
    """Test access token refresh with rotation"""

    @pytest.mark.asyncio
    async def test_refresh_access_token_with_rotation(
        self, token_service, mock_user, mock_refresh_token_repo
    ):
        """Test refreshing access token with refresh token rotation"""
        # Arrange
        with patch("src.services.token_service.settings") as mock_settings:
            mock_settings.secret_key = "test_secret_key"
            token_value = "original_token_value"
            refresh_token = token_service._create_refresh_token_jwt(
                mock_user, token_value
            )

        # Mock database lookup
        token_hash = token_service._hash_token(token_value)
        mock_db_token = RefreshToken(
            token_id="token_id_123",
            user_id=mock_user.user_id,
            token_hash=token_hash,
            expires_at=datetime.utcnow() + timedelta(days=7),
            user_agent="Mozilla/5.0",
            ip_address="192.168.1.100",
            revoked=False,
            revoked_at=None,
        )
        mock_refresh_token_repo.find_by_hash.return_value = mock_db_token

        # Act
        result = await token_service.refresh_access_token(refresh_token, rotate=True)

        # Assert
        assert result.access_token is not None
        assert result.refresh_token is not None
        assert result.access_token != refresh_token  # New access token
        assert result.refresh_token != refresh_token  # New refresh token

        # Verify rotation was called
        mock_refresh_token_repo.rotate_token_atomic.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_access_token_without_rotation(
        self, token_service, mock_user, mock_refresh_token_repo
    ):
        """Test refreshing access token without rotation"""
        # Arrange
        with patch("src.services.token_service.settings") as mock_settings:
            mock_settings.secret_key = "test_secret_key"
            token_value = "token_value"
            refresh_token = token_service._create_refresh_token_jwt(
                mock_user, token_value
            )

        token_hash = token_service._hash_token(token_value)
        mock_db_token = RefreshToken(
            token_id="token_id_123",
            user_id=mock_user.user_id,
            token_hash=token_hash,
            expires_at=datetime.utcnow() + timedelta(days=7),
            user_agent=None,
            ip_address=None,
            revoked=False,
            revoked_at=None,
        )
        mock_refresh_token_repo.find_by_hash.return_value = mock_db_token

        # Act
        access_token = await token_service.refresh_access_token(
            refresh_token, rotate=False
        )

        # Assert
        assert isinstance(access_token, str)
        assert access_token != refresh_token

        # Verify rotation was NOT called
        mock_refresh_token_repo.rotate_token_atomic.assert_not_called()
        # But last_used should be updated
        mock_refresh_token_repo.update_last_used.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_access_token_invalid_type(
        self, token_service, mock_user, mock_refresh_token_repo
    ):
        """Test refreshing with access token (wrong type)"""
        # Arrange - create access token instead of refresh token
        with patch("src.services.token_service.settings") as mock_settings:
            mock_settings.secret_key = "test_secret_key"
            access_token = token_service._create_access_token(mock_user)

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid token type"):
            await token_service.refresh_access_token(access_token)

    @pytest.mark.asyncio
    async def test_refresh_access_token_revoked(
        self, token_service, mock_user, mock_refresh_token_repo
    ):
        """Test refreshing with revoked token"""
        # Arrange
        with patch("src.services.token_service.settings") as mock_settings:
            mock_settings.secret_key = "test_secret_key"
            token_value = "revoked_token"
            refresh_token = token_service._create_refresh_token_jwt(
                mock_user, token_value
            )

        # Mock database returns revoked token
        token_hash = token_service._hash_token(token_value)
        mock_db_token = RefreshToken(
            token_id="token_id_123",
            user_id=mock_user.user_id,
            token_hash=token_hash,
            expires_at=datetime.utcnow() + timedelta(days=7),
            user_agent=None,
            ip_address=None,
            revoked=True,  # Revoked!
            revoked_at=datetime.utcnow(),
        )
        mock_refresh_token_repo.find_by_hash.return_value = mock_db_token

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid or revoked refresh token"):
            await token_service.refresh_access_token(refresh_token)

    @pytest.mark.asyncio
    async def test_refresh_access_token_not_in_database(
        self, token_service, mock_user, mock_refresh_token_repo
    ):
        """Test refreshing with token not in database"""
        # Arrange
        with patch("src.services.token_service.settings") as mock_settings:
            mock_settings.secret_key = "test_secret_key"
            token_value = "unknown_token"
            refresh_token = token_service._create_refresh_token_jwt(
                mock_user, token_value
            )

        mock_refresh_token_repo.find_by_hash.return_value = None

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid or revoked refresh token"):
            await token_service.refresh_access_token(refresh_token)

    @pytest.mark.asyncio
    async def test_refresh_access_token_expired_jwt(
        self, token_service, mock_refresh_token_repo
    ):
        """Test refreshing with expired JWT"""
        # Arrange - create expired token
        with patch("src.services.token_service.settings") as mock_settings:
            mock_settings.secret_key = "test_secret_key"
            payload = {
                "sub": "user_123",
                "type": "refresh",
                "token_value": "expired_token",
                "exp": datetime.utcnow() - timedelta(days=1),  # Expired
                "iat": datetime.utcnow() - timedelta(days=8),
            }
            expired_token = jwt.encode(payload, "test_secret_key", algorithm="HS256")

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid refresh token"):
            await token_service.refresh_access_token(expired_token)


# ===== Integration Tests =====


class TestTokenServiceIntegration:
    """Test integration scenarios"""

    @pytest.mark.asyncio
    async def test_full_token_lifecycle(self, token_service, mock_user, mock_refresh_token_repo):
        """Test complete token lifecycle: create → verify → refresh → revoke"""
        # Create token pair
        token_pair = await token_service.create_token_pair(mock_user)

        # Verify access token
        user_id = token_service.verify_access_token(token_pair.access_token)
        assert user_id == mock_user.user_id

        # Mock for refresh
        token_hash = hashlib.sha256(token_pair.refresh_token.encode()).hexdigest()
        mock_db_token = Mock()
        mock_db_token.is_valid = True
        mock_db_token.user_id = mock_user.user_id
        mock_db_token.user_agent = None
        mock_db_token.ip_address = None
        mock_refresh_token_repo.find_by_hash.return_value = mock_db_token

        # Revoke token
        mock_refresh_token_repo.revoke_by_hash.return_value = True
        revoked = await token_service.revoke_token(token_pair.refresh_token)
        assert revoked is True
