"""
Unit tests for RefreshTokenRepository.

Tests MongoDB operations for refresh token management:
- Token creation
- Find by hash
- Find active tokens by user
- Update last used timestamp
- Revoke tokens
- Atomic token rotation
- Cleanup expired tokens
"""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.core.utils.date_utils import utcnow
from src.database.repositories.refresh_token_repository import RefreshTokenRepository
from src.models.refresh_token import RefreshToken


# ===== Fixtures =====


@pytest.fixture
def mock_collection():
    """Mock MongoDB collection"""
    collection = Mock()
    collection.insert_one = AsyncMock()
    collection.find_one = AsyncMock()
    collection.find = Mock()
    collection.find_one_and_update = AsyncMock()
    collection.update_one = AsyncMock()
    collection.update_many = AsyncMock()
    collection.delete_many = AsyncMock()
    collection.count_documents = AsyncMock()
    collection.index_information = AsyncMock()
    collection.create_index = AsyncMock()
    collection.database = Mock()
    collection.database.client = Mock()
    return collection


@pytest.fixture
def repository(mock_collection):
    """RefreshTokenRepository instance"""
    return RefreshTokenRepository(mock_collection)


@pytest.fixture
def sample_token():
    """Sample refresh token"""
    return RefreshToken(
        token_id="token_123",
        user_id="user_456",
        token_hash="abc123hash",
        expires_at=utcnow() + timedelta(days=7),
        created_at=utcnow(),
        user_agent="Mozilla/5.0",
        ip_address="192.168.1.1",
    )


@pytest.fixture
def sample_token_dict(sample_token):
    """Sample token as dictionary"""
    return sample_token.model_dump()


# ===== Index Management Tests =====


class TestEnsureIndexes:
    """Test index creation and management"""

    @pytest.mark.asyncio
    async def test_ensure_indexes_creates_all_indexes(
        self, repository, mock_collection
    ):
        """Test that all required indexes are created"""
        # Arrange - No existing indexes
        mock_collection.index_information.return_value = {"_id_": {}}

        # Act
        await repository.ensure_indexes()

        # Assert - All indexes should be created
        assert mock_collection.create_index.call_count >= 4  # At least 4 indexes

    @pytest.mark.asyncio
    async def test_ensure_indexes_skips_existing(self, repository, mock_collection):
        """Test that existing indexes are not recreated"""
        # Arrange - All indexes exist
        mock_collection.index_information.return_value = {
            "_id_": {},
            "token_hash_1": {},
            "user_id_1": {},
            "expires_at_1": {},
            "user_id_1_revoked_1": {},
            "revoked_at_1": {},
        }

        # Act
        await repository.ensure_indexes()

        # Assert - No indexes should be created
        mock_collection.create_index.assert_not_called()

    @pytest.mark.asyncio
    async def test_ensure_indexes_handles_error_gracefully(
        self, repository, mock_collection
    ):
        """Test that index creation errors don't crash startup"""
        # Arrange
        mock_collection.index_information.side_effect = Exception("MongoDB error")

        # Act - Should not raise
        await repository.ensure_indexes()

        # Assert - No exception raised


# ===== Create Token Tests =====


class TestCreateToken:
    """Test token creation"""

    @pytest.mark.asyncio
    async def test_create_token_success(
        self, repository, mock_collection, sample_token
    ):
        """Test successful token creation"""
        # Act
        result = await repository.create(sample_token)

        # Assert
        assert result == sample_token
        mock_collection.insert_one.assert_called_once()
        call_args = mock_collection.insert_one.call_args[0][0]
        assert call_args["token_id"] == "token_123"
        assert call_args["user_id"] == "user_456"


# ===== Find by Hash Tests =====


class TestFindByHash:
    """Test finding tokens by hash"""

    @pytest.mark.asyncio
    async def test_find_by_hash_found(
        self, repository, mock_collection, sample_token_dict
    ):
        """Test finding existing token"""
        # Arrange
        sample_token_dict["_id"] = "mongodb_id"
        mock_collection.find_one.return_value = sample_token_dict

        # Act
        result = await repository.find_by_hash("abc123hash")

        # Assert
        assert result is not None
        assert result.token_hash == "abc123hash"
        mock_collection.find_one.assert_called_once_with({"token_hash": "abc123hash"})

    @pytest.mark.asyncio
    async def test_find_by_hash_not_found(self, repository, mock_collection):
        """Test finding non-existent token"""
        # Arrange
        mock_collection.find_one.return_value = None

        # Act
        result = await repository.find_by_hash("nonexistent_hash")

        # Assert
        assert result is None


# ===== Find Active by User Tests =====


class TestFindActiveByUser:
    """Test finding active tokens for a user"""

    @pytest.mark.asyncio
    async def test_find_active_by_user_returns_tokens(
        self, repository, mock_collection, sample_token_dict
    ):
        """Test finding active tokens"""
        # Arrange - Mock async cursor
        sample_token_dict["_id"] = "mongodb_id"

        async def async_cursor():
            yield sample_token_dict

        mock_cursor = Mock()
        mock_cursor.__aiter__ = lambda self: async_cursor()
        mock_collection.find.return_value = mock_cursor

        # Act
        result = await repository.find_active_by_user("user_456")

        # Assert
        assert len(result) == 1
        assert result[0].user_id == "user_456"

    @pytest.mark.asyncio
    async def test_find_active_by_user_empty(self, repository, mock_collection):
        """Test finding no active tokens"""
        # Arrange - Empty cursor
        async def empty_cursor():
            return
            yield  # Make it a generator

        mock_cursor = Mock()
        mock_cursor.__aiter__ = lambda self: empty_cursor()
        mock_collection.find.return_value = mock_cursor

        # Act
        result = await repository.find_active_by_user("user_no_tokens")

        # Assert
        assert len(result) == 0


# ===== Update Last Used Tests =====


class TestUpdateLastUsed:
    """Test updating last_used_at timestamp"""

    @pytest.mark.asyncio
    async def test_update_last_used_success(
        self, repository, mock_collection, sample_token_dict
    ):
        """Test successful last_used update"""
        # Arrange
        sample_token_dict["_id"] = "mongodb_id"
        mock_collection.find_one_and_update.return_value = sample_token_dict

        # Act
        result = await repository.update_last_used("abc123hash")

        # Assert
        assert result is not None
        mock_collection.find_one_and_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_last_used_not_found(self, repository, mock_collection):
        """Test update on non-existent token"""
        # Arrange
        mock_collection.find_one_and_update.return_value = None

        # Act
        result = await repository.update_last_used("nonexistent_hash")

        # Assert
        assert result is None


# ===== Revoke by Hash Tests =====


class TestRevokeByHash:
    """Test revoking tokens by hash"""

    @pytest.mark.asyncio
    async def test_revoke_by_hash_success(self, repository, mock_collection):
        """Test successful token revocation"""
        # Arrange
        mock_result = Mock()
        mock_result.modified_count = 1
        mock_collection.update_one.return_value = mock_result

        # Act
        result = await repository.revoke_by_hash("abc123hash")

        # Assert
        assert result is True
        mock_collection.update_one.assert_called_once()
        call_args = mock_collection.update_one.call_args
        assert call_args[0][0] == {"token_hash": "abc123hash"}
        assert call_args[0][1]["$set"]["revoked"] is True

    @pytest.mark.asyncio
    async def test_revoke_by_hash_not_found(self, repository, mock_collection):
        """Test revoking non-existent token"""
        # Arrange
        mock_result = Mock()
        mock_result.modified_count = 0
        mock_collection.update_one.return_value = mock_result

        # Act
        result = await repository.revoke_by_hash("nonexistent_hash")

        # Assert
        assert result is False


# ===== Atomic Token Rotation Tests =====


class TestRotateTokenAtomic:
    """Test atomic token rotation"""

    @pytest.mark.asyncio
    async def test_rotate_token_non_atomic_fallback(
        self, repository, mock_collection, sample_token, sample_token_dict
    ):
        """Test token rotation with non-atomic fallback"""
        # Arrange - Simulate transaction not supported
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.start_transaction = Mock()
        mock_session.start_transaction.return_value.__aenter__ = AsyncMock()
        mock_session.start_transaction.return_value.__aexit__ = AsyncMock()

        # Make start_session raise transaction error
        mock_collection.database.client.start_session = AsyncMock(
            side_effect=Exception("Transaction numbers are only allowed on a replica set")
        )

        # Setup fallback path
        sample_token_dict["_id"] = "mongodb_id"
        sample_token_dict["revoked"] = False
        mock_collection.find_one.return_value = sample_token_dict
        mock_result = Mock()
        mock_result.modified_count = 1
        mock_collection.update_one.return_value = mock_result

        new_token = RefreshToken(
            token_id="new_token_789",
            user_id="user_456",
            token_hash="new_hash_xyz",
            expires_at=utcnow() + timedelta(days=7),
            created_at=utcnow(),
        )

        # Act
        result = await repository.rotate_token_atomic("old_hash", new_token)

        # Assert
        assert result == new_token
        mock_collection.insert_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_rotate_token_old_token_not_found(
        self, repository, mock_collection, sample_token
    ):
        """Test rotation when old token doesn't exist"""
        # Arrange
        mock_collection.database.client.start_session = AsyncMock(
            side_effect=Exception("Transaction not supported")
        )
        mock_collection.find_one.return_value = None

        new_token = RefreshToken(
            token_id="new_token",
            user_id="user_456",
            token_hash="new_hash",
            expires_at=utcnow() + timedelta(days=7),
            created_at=utcnow(),
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Old refresh token not found"):
            await repository.rotate_token_atomic("nonexistent_hash", new_token)

    @pytest.mark.asyncio
    async def test_rotate_token_already_revoked(
        self, repository, mock_collection, sample_token_dict
    ):
        """Test rotation when old token is already revoked"""
        # Arrange
        mock_collection.database.client.start_session = AsyncMock(
            side_effect=Exception("Transaction not supported")
        )
        sample_token_dict["_id"] = "mongodb_id"
        sample_token_dict["revoked"] = True  # Already revoked
        mock_collection.find_one.return_value = sample_token_dict

        new_token = RefreshToken(
            token_id="new_token",
            user_id="user_456",
            token_hash="new_hash",
            expires_at=utcnow() + timedelta(days=7),
            created_at=utcnow(),
        )

        # Act & Assert
        with pytest.raises(ValueError, match="already revoked"):
            await repository.rotate_token_atomic("old_hash", new_token)


# ===== Revoke All for User Tests =====


class TestRevokeAllForUser:
    """Test revoking all tokens for a user"""

    @pytest.mark.asyncio
    async def test_revoke_all_for_user_success(self, repository, mock_collection):
        """Test revoking all user tokens"""
        # Arrange
        mock_result = Mock()
        mock_result.modified_count = 3
        mock_collection.update_many.return_value = mock_result

        # Act
        count = await repository.revoke_all_for_user("user_456")

        # Assert
        assert count == 3
        mock_collection.update_many.assert_called_once()
        call_args = mock_collection.update_many.call_args
        assert call_args[0][0]["user_id"] == "user_456"
        assert call_args[0][0]["revoked"] is False

    @pytest.mark.asyncio
    async def test_revoke_all_for_user_no_tokens(self, repository, mock_collection):
        """Test revoking for user with no active tokens"""
        # Arrange
        mock_result = Mock()
        mock_result.modified_count = 0
        mock_collection.update_many.return_value = mock_result

        # Act
        count = await repository.revoke_all_for_user("user_no_tokens")

        # Assert
        assert count == 0


# ===== Cleanup Expired Tests =====


class TestCleanupExpired:
    """Test expired token cleanup"""

    @pytest.mark.asyncio
    async def test_cleanup_expired_deletes_tokens(self, repository, mock_collection):
        """Test cleaning up expired tokens"""
        # Arrange
        mock_result = Mock()
        mock_result.deleted_count = 5
        mock_collection.delete_many.return_value = mock_result

        # Act
        count = await repository.cleanup_expired()

        # Assert
        assert count == 5
        mock_collection.delete_many.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_expired_no_expired_tokens(
        self, repository, mock_collection
    ):
        """Test cleanup when no expired tokens exist"""
        # Arrange
        mock_result = Mock()
        mock_result.deleted_count = 0
        mock_collection.delete_many.return_value = mock_result

        # Act
        count = await repository.cleanup_expired()

        # Assert
        assert count == 0


# ===== Count Active by User Tests =====


class TestCountActiveByUser:
    """Test counting active tokens for a user"""

    @pytest.mark.asyncio
    async def test_count_active_by_user(self, repository, mock_collection):
        """Test counting active tokens"""
        # Arrange
        mock_collection.count_documents.return_value = 3

        # Act
        count = await repository.count_active_by_user("user_456")

        # Assert
        assert count == 3
        mock_collection.count_documents.assert_called_once()
        call_args = mock_collection.count_documents.call_args[0][0]
        assert call_args["user_id"] == "user_456"
        assert call_args["revoked"] is False

    @pytest.mark.asyncio
    async def test_count_active_by_user_zero(self, repository, mock_collection):
        """Test counting when user has no active tokens"""
        # Arrange
        mock_collection.count_documents.return_value = 0

        # Act
        count = await repository.count_active_by_user("user_no_tokens")

        # Assert
        assert count == 0
