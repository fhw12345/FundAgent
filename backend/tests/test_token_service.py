"""
Unit tests for TokenService.

Tests JWT access/refresh token management with rotation.
"""

import hashlib
from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from jose import jwt

from src.services.token_service import TokenService


# ===== Fixtures =====


@pytest.fixture
def mock_refresh_token_repo():
    """Create mock refresh token repository."""
    repo = AsyncMock()
    repo.create = AsyncMock()
    repo.find_by_hash = AsyncMock(return_value=None)
    repo.update_last_used = AsyncMock()
    repo.rotate_token_atomic = AsyncMock()
    repo.revoke_by_hash = AsyncMock(return_value=False)
    repo.revoke_all_for_user = AsyncMock(return_value=0)
    return repo


@pytest.fixture
def token_service(mock_refresh_token_repo):
    """Create TokenService with mocked repository."""
    return TokenService(refresh_token_repo=mock_refresh_token_repo)


@pytest.fixture
def mock_user():
    """Create mock User object."""
    user = Mock()
    user.user_id = "user_123"
    user.username = "testuser"
    user.email = "test@example.com"
    return user


# ===== Constants Tests =====


class TestTokenServiceConstants:
    """Test TokenService class constants."""

    def test_algorithm(self):
        """Test algorithm is HS256."""
        assert TokenService.ALGORITHM == "HS256"

    def test_access_token_expire_minutes(self):
        """Test access token expiry is 30 minutes."""
        assert TokenService.ACCESS_TOKEN_EXPIRE_MINUTES == 30

    def test_refresh_token_expire_days(self):
        """Test refresh token expiry is 7 days."""
        assert TokenService.REFRESH_TOKEN_EXPIRE_DAYS == 7


# ===== __init__ Tests =====


class TestTokenServiceInit:
    """Test TokenService initialization."""

    def test_init_sets_repo(self, mock_refresh_token_repo):
        """Test initialization sets repository."""
        service = TokenService(refresh_token_repo=mock_refresh_token_repo)
        assert service.refresh_token_repo == mock_refresh_token_repo


# ===== _hash_token Tests =====


class TestHashToken:
    """Test _hash_token method."""

    def test_hash_token_returns_sha256(self, token_service):
        """Test token is hashed with SHA256."""
        token = "test_token_value"
        result = token_service._hash_token(token)

        expected = hashlib.sha256(token.encode()).hexdigest()
        assert result == expected

    def test_hash_token_consistent(self, token_service):
        """Test same input produces same hash."""
        token = "consistent_token"
        hash1 = token_service._hash_token(token)
        hash2 = token_service._hash_token(token)
        assert hash1 == hash2

    def test_hash_token_different_inputs(self, token_service):
        """Test different inputs produce different hashes."""
        hash1 = token_service._hash_token("token1")
        hash2 = token_service._hash_token("token2")
        assert hash1 != hash2


# ===== create_token_pair Tests =====


class TestCreateTokenPair:
    """Test create_token_pair method."""

    @pytest.mark.asyncio
    async def test_create_token_pair_success(
        self, token_service, mock_refresh_token_repo, mock_user
    ):
        """Test successful token pair creation."""
        with patch("src.services.token_service.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key"

            result = await token_service.create_token_pair(
                user=mock_user,
                user_agent="Mozilla/5.0",
                ip_address="192.168.1.1",
            )

            assert result.token_type == "bearer"
            assert result.access_token is not None
            assert result.refresh_token is not None
            assert result.expires_in == 30 * 60
            assert result.refresh_expires_in == 7 * 24 * 3600
            mock_refresh_token_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_token_pair_without_optional_params(
        self, token_service, mock_refresh_token_repo, mock_user
    ):
        """Test token pair creation without user_agent and ip_address."""
        with patch("src.services.token_service.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key"

            result = await token_service.create_token_pair(user=mock_user)

            assert result.access_token is not None
            assert result.refresh_token is not None
            mock_refresh_token_repo.create.assert_called_once()


# ===== _create_access_token Tests =====


class TestCreateAccessToken:
    """Test _create_access_token method."""

    def test_create_access_token_returns_jwt(self, token_service, mock_user):
        """Test access token is a valid JWT."""
        with patch("src.services.token_service.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key"

            token = token_service._create_access_token(mock_user)

            payload = jwt.decode(
                token, "test-secret-key", algorithms=["HS256"]
            )
            assert payload["sub"] == "user_123"
            assert payload["username"] == "testuser"
            assert payload["type"] == "access"
            assert "exp" in payload
            assert "iat" in payload
            assert "jti" in payload


# ===== _create_refresh_token_jwt Tests =====


class TestCreateRefreshTokenJwt:
    """Test _create_refresh_token_jwt method."""

    def test_create_refresh_token_jwt(self, token_service, mock_user):
        """Test refresh token JWT creation."""
        with patch("src.services.token_service.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key"

            token = token_service._create_refresh_token_jwt(mock_user, "token_value_123")

            payload = jwt.decode(
                token, "test-secret-key", algorithms=["HS256"]
            )
            assert payload["sub"] == "user_123"
            assert payload["type"] == "refresh"
            assert payload["token_value"] == "token_value_123"


# ===== verify_access_token Tests =====


class TestVerifyAccessToken:
    """Test verify_access_token method."""

    def test_verify_valid_access_token(self, token_service, mock_user):
        """Test verifying valid access token."""
        with patch("src.services.token_service.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key"

            token = token_service._create_access_token(mock_user)
            user_id = token_service.verify_access_token(token)

            assert user_id == "user_123"

    def test_verify_expired_access_token(self, token_service):
        """Test verifying expired access token."""
        with patch("src.services.token_service.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key"

            with patch("src.services.token_service.utcnow") as mock_now:
                from datetime import datetime, timezone

                past_time = datetime(2020, 1, 1, tzinfo=timezone.utc)
                mock_now.return_value = past_time

                payload = {
                    "sub": "user_123",
                    "username": "testuser",
                    "type": "access",
                    "exp": past_time + timedelta(minutes=30),
                    "iat": past_time,
                    "jti": "test-jti",
                }
                expired_token = jwt.encode(
                    payload, "test-secret-key", algorithm="HS256"
                )

            user_id = token_service.verify_access_token(expired_token)
            assert user_id is None

    def test_verify_wrong_token_type(self, token_service, mock_user):
        """Test verifying token with wrong type."""
        with patch("src.services.token_service.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key"

            token = token_service._create_refresh_token_jwt(mock_user, "value")

            user_id = token_service.verify_access_token(token)
            assert user_id is None

    def test_verify_invalid_jwt(self, token_service):
        """Test verifying invalid JWT."""
        with patch("src.services.token_service.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key"

            user_id = token_service.verify_access_token("invalid.jwt.token")
            assert user_id is None

    def test_verify_missing_user_id(self, token_service):
        """Test verifying token with missing user ID."""
        with patch("src.services.token_service.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key"

            from datetime import datetime, timezone

            payload = {
                "username": "testuser",
                "type": "access",
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                "iat": datetime.now(timezone.utc),
                "jti": "test-jti",
            }
            token = jwt.encode(payload, "test-secret-key", algorithm="HS256")

            user_id = token_service.verify_access_token(token)
            assert user_id is None


# ===== refresh_access_token Tests =====


class TestRefreshAccessToken:
    """Test refresh_access_token method."""

    @pytest.mark.asyncio
    async def test_refresh_with_rotation(
        self, token_service, mock_refresh_token_repo, mock_user
    ):
        """Test refresh with token rotation."""
        with patch("src.services.token_service.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key"

            refresh_token = token_service._create_refresh_token_jwt(
                mock_user, "original_token_value"
            )

            db_token = Mock()
            db_token.is_valid = True
            db_token.user_agent = "Mozilla/5.0"
            db_token.ip_address = "192.168.1.1"
            mock_refresh_token_repo.find_by_hash.return_value = db_token

            result = await token_service.refresh_access_token(refresh_token, rotate=True)

            assert hasattr(result, "access_token")
            assert hasattr(result, "refresh_token")
            mock_refresh_token_repo.rotate_token_atomic.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_without_rotation(
        self, token_service, mock_refresh_token_repo, mock_user
    ):
        """Test refresh without token rotation."""
        with patch("src.services.token_service.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key"

            refresh_token = token_service._create_refresh_token_jwt(
                mock_user, "token_value"
            )

            db_token = Mock()
            db_token.is_valid = True
            mock_refresh_token_repo.find_by_hash.return_value = db_token

            result = await token_service.refresh_access_token(
                refresh_token, rotate=False
            )

            assert isinstance(result, str)
            mock_refresh_token_repo.rotate_token_atomic.assert_not_called()

    @pytest.mark.asyncio
    async def test_refresh_invalid_token_type(
        self, token_service, mock_refresh_token_repo, mock_user
    ):
        """Test refresh with wrong token type."""
        with patch("src.services.token_service.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key"

            access_token = token_service._create_access_token(mock_user)

            with pytest.raises(ValueError, match="Invalid token type"):
                await token_service.refresh_access_token(access_token)

    @pytest.mark.asyncio
    async def test_refresh_missing_token_value(self, token_service):
        """Test refresh with missing token_value in payload."""
        with patch("src.services.token_service.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key"

            from datetime import datetime, timezone

            payload = {
                "sub": "user_123",
                "type": "refresh",
                "exp": datetime.now(timezone.utc) + timedelta(days=7),
                "iat": datetime.now(timezone.utc),
                "jti": "test-jti",
            }
            bad_token = jwt.encode(payload, "test-secret-key", algorithm="HS256")

            with pytest.raises(ValueError, match="Missing token value"):
                await token_service.refresh_access_token(bad_token)

    @pytest.mark.asyncio
    async def test_refresh_revoked_token(
        self, token_service, mock_refresh_token_repo, mock_user
    ):
        """Test refresh with revoked token."""
        with patch("src.services.token_service.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key"

            refresh_token = token_service._create_refresh_token_jwt(
                mock_user, "revoked_token"
            )

            db_token = Mock()
            db_token.is_valid = False
            mock_refresh_token_repo.find_by_hash.return_value = db_token

            with pytest.raises(ValueError, match="Invalid or revoked refresh token"):
                await token_service.refresh_access_token(refresh_token)

    @pytest.mark.asyncio
    async def test_refresh_token_not_in_db(
        self, token_service, mock_refresh_token_repo, mock_user
    ):
        """Test refresh with token not found in database."""
        with patch("src.services.token_service.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key"

            refresh_token = token_service._create_refresh_token_jwt(
                mock_user, "unknown_token"
            )

            mock_refresh_token_repo.find_by_hash.return_value = None

            with pytest.raises(ValueError, match="Invalid or revoked refresh token"):
                await token_service.refresh_access_token(refresh_token)

    @pytest.mark.asyncio
    async def test_refresh_jwt_decode_error(self, token_service):
        """Test refresh with invalid JWT."""
        with patch("src.services.token_service.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key"

            with pytest.raises(ValueError, match="Invalid refresh token"):
                await token_service.refresh_access_token("invalid.token")


# ===== revoke_token Tests =====


class TestRevokeToken:
    """Test revoke_token method."""

    @pytest.mark.asyncio
    async def test_revoke_token_success(
        self, token_service, mock_refresh_token_repo, mock_user
    ):
        """Test successful token revocation."""
        with patch("src.services.token_service.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key"

            refresh_token = token_service._create_refresh_token_jwt(
                mock_user, "token_to_revoke"
            )

            mock_refresh_token_repo.revoke_by_hash.return_value = True

            result = await token_service.revoke_token(refresh_token)

            assert result is True
            mock_refresh_token_repo.revoke_by_hash.assert_called_once()

    @pytest.mark.asyncio
    async def test_revoke_token_not_found(
        self, token_service, mock_refresh_token_repo, mock_user
    ):
        """Test revocation of non-existent token."""
        with patch("src.services.token_service.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key"

            refresh_token = token_service._create_refresh_token_jwt(
                mock_user, "nonexistent_token"
            )

            mock_refresh_token_repo.revoke_by_hash.return_value = False

            result = await token_service.revoke_token(refresh_token)

            assert result is False

    @pytest.mark.asyncio
    async def test_revoke_invalid_jwt(self, token_service):
        """Test revocation of invalid JWT."""
        with patch("src.services.token_service.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key"

            result = await token_service.revoke_token("invalid.jwt")

            assert result is False

    @pytest.mark.asyncio
    async def test_revoke_missing_token_value(self, token_service):
        """Test revocation with missing token_value."""
        with patch("src.services.token_service.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key"

            from datetime import datetime, timezone

            payload = {
                "sub": "user_123",
                "type": "refresh",
                "exp": datetime.now(timezone.utc) + timedelta(days=7),
                "iat": datetime.now(timezone.utc),
            }
            token = jwt.encode(payload, "test-secret-key", algorithm="HS256")

            result = await token_service.revoke_token(token)

            assert result is False


# ===== revoke_all_user_tokens Tests =====


class TestRevokeAllUserTokens:
    """Test revoke_all_user_tokens method."""

    @pytest.mark.asyncio
    async def test_revoke_all_success(self, token_service, mock_refresh_token_repo):
        """Test revoking all user tokens."""
        mock_refresh_token_repo.revoke_all_for_user.return_value = 5

        result = await token_service.revoke_all_user_tokens("user_123")

        assert result == 5
        mock_refresh_token_repo.revoke_all_for_user.assert_called_once_with("user_123")

    @pytest.mark.asyncio
    async def test_revoke_all_no_tokens(self, token_service, mock_refresh_token_repo):
        """Test revoking when user has no tokens."""
        mock_refresh_token_repo.revoke_all_for_user.return_value = 0

        result = await token_service.revoke_all_user_tokens("user_no_tokens")

        assert result == 0


# ===== _create_access_token_from_payload Tests =====


class TestCreateAccessTokenFromPayload:
    """Test _create_access_token_from_payload method."""

    def test_create_access_token_from_payload(self, token_service):
        """Test creating access token from refresh payload."""
        with patch("src.services.token_service.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key"

            refresh_payload = {
                "sub": "user_456",
                "username": "anotheruser",
                "type": "refresh",
                "token_value": "some_value",
            }

            token = token_service._create_access_token_from_payload(refresh_payload)

            payload = jwt.decode(token, "test-secret-key", algorithms=["HS256"])
            assert payload["sub"] == "user_456"
            assert payload["username"] == "anotheruser"
            assert payload["type"] == "access"

    def test_create_access_token_from_payload_missing_username(self, token_service):
        """Test creating access token when username missing in payload."""
        with patch("src.services.token_service.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key"

            refresh_payload = {
                "sub": "user_789",
                "type": "refresh",
            }

            token = token_service._create_access_token_from_payload(refresh_payload)

            payload = jwt.decode(token, "test-secret-key", algorithms=["HS256"])
            assert payload["sub"] == "user_789"
            assert payload["username"] == ""


# ===== _create_refresh_token_jwt_from_user_id Tests =====


class TestCreateRefreshTokenJwtFromUserId:
    """Test _create_refresh_token_jwt_from_user_id method."""

    def test_create_refresh_token_from_user_id(self, token_service):
        """Test creating refresh token from user ID."""
        with patch("src.services.token_service.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key"

            token = token_service._create_refresh_token_jwt_from_user_id(
                "user_xyz", "new_token_value"
            )

            payload = jwt.decode(token, "test-secret-key", algorithms=["HS256"])
            assert payload["sub"] == "user_xyz"
            assert payload["type"] == "refresh"
            assert payload["token_value"] == "new_token_value"
