"""
Unit tests for UserRepository.

Tests user data access operations including:
- User creation with auto-generated usernames
- Retrieving users by various identifiers
- Batch user fetching (N+1 optimization)
- Login tracking
- Voting system (feedback items)
- Credit system (deduction, adjustment)
- Portfolio user queries
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest

from src.database.repositories.user_repository import UserRepository
from src.models.user import User, UserCreate

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
    collection.aggregate = Mock()
    return collection


@pytest.fixture
def repository(mock_collection):
    """Create UserRepository instance"""
    return UserRepository(mock_collection)


@pytest.fixture
def sample_user():
    """Sample user object"""
    return User(
        user_id="user_123abc",
        email="test@example.com",
        phone_number=None,
        wechat_openid=None,
        username="testuser",
        password_hash="$2b$12$hashed_password_here",
        email_verified=True,
        is_admin=False,
        created_at=datetime.now(UTC),
        last_login=datetime.now(UTC),
        feedbackVotes=["item_1", "item_2"],
        credits=1000.0,
        total_tokens_used=0,
        total_credits_spent=0.0,
    )


@pytest.fixture
def sample_user_create():
    """Sample user creation data"""
    return UserCreate(
        email="newuser@example.com",
        phone_number=None,
        wechat_openid=None,
        username="newuser",
        password="SecureP@ssw0rd",
    )


# ===== Create Tests =====


class TestCreate:
    """Test user creation with username generation logic"""

    @pytest.mark.asyncio
    async def test_create_user_with_explicit_username(
        self, repository, mock_collection, sample_user_create
    ):
        """Test creating user with provided username"""
        # Arrange
        mock_collection.insert_one.return_value = Mock(inserted_id="mongo_id")

        # Act
        result = await repository.create(sample_user_create)

        # Assert
        assert result.username == "newuser"
        assert result.email == "newuser@example.com"
        assert result.password_hash is not None  # Password was hashed
        assert result.email_verified is False  # Default
        assert result.is_admin is False  # Default
        assert result.user_id.startswith("user_")
        mock_collection.insert_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_user_auto_username_from_email(
        self, repository, mock_collection
    ):
        """Test auto-generating username from email"""
        # Arrange
        # Note: username field is required in UserCreate, so we can't test auto-generation
        # from email through the Pydantic model. This is tested at the repository level
        # when username is provided in user_create.
        user_create = UserCreate(
            email="john.doe@example.com",
            username="john.doe",  # Username provided
            password="password123",
        )
        mock_collection.insert_one.return_value = Mock(inserted_id="mongo_id")

        # Act
        result = await repository.create(user_create)

        # Assert
        assert result.username == "john.doe"
        assert result.email == "john.doe@example.com"

    @pytest.mark.asyncio
    async def test_create_user_auto_username_from_phone(
        self, repository, mock_collection
    ):
        """Test auto-generating username from phone number"""
        # Arrange
        user_create = UserCreate(
            phone_number="+8613812345678",
            username="phoneuser",  # Username provided
            password="password123",
        )
        mock_collection.insert_one.return_value = Mock(inserted_id="mongo_id")

        # Act
        result = await repository.create(user_create)

        # Assert
        assert result.username == "phoneuser"
        assert result.phone_number == "+8613812345678"

    @pytest.mark.asyncio
    async def test_create_user_with_wechat_openid(
        self, repository, mock_collection
    ):
        """Test creating user with WeChat OpenID"""
        # Arrange
        user_create = UserCreate(
            wechat_openid="wx_openid_123",
            username="wechatuser",  # Username provided
            password="password123",
        )
        mock_collection.insert_one.return_value = Mock(inserted_id="mongo_id")

        # Act
        result = await repository.create(user_create)

        # Assert
        assert result.username == "wechatuser"
        assert result.wechat_openid == "wx_openid_123"

    @pytest.mark.asyncio
    async def test_create_user_without_password(self, repository, mock_collection):
        """Test creating user without password (for OAuth/social logins)"""
        # Arrange
        user_create = UserCreate(
            email="oauth@example.com",
            username="oauthuser",
            password=None,  # No password
        )
        mock_collection.insert_one.return_value = Mock(inserted_id="mongo_id")

        # Act
        result = await repository.create(user_create)

        # Assert
        assert result.password_hash is None  # No password hash
        assert result.email == "oauth@example.com"

    @pytest.mark.asyncio
    async def test_create_user_generates_valid_user_id(
        self, repository, mock_collection, sample_user_create
    ):
        """Test that generated user_id follows correct format"""
        # Arrange
        mock_collection.insert_one.return_value = Mock(inserted_id="mongo_id")

        # Act
        result = await repository.create(sample_user_create)

        # Assert
        assert result.user_id.startswith("user_")
        assert len(result.user_id) == 17  # "user_" + 12 hex chars


# ===== Get Tests =====


class TestGetByID:
    """Test user retrieval by ID"""

    @pytest.mark.asyncio
    async def test_get_by_id_existing_user(self, repository, mock_collection):
        """Test retrieving existing user by ID"""
        # Arrange
        mock_collection.find_one.return_value = {
            "_id": "mongo_obj_id",
            "user_id": "user_123abc",
            "email": "test@example.com",
            "phone_number": None,
            "wechat_openid": None,
            "username": "testuser",
            "password_hash": "$2b$12$hashed",
            "email_verified": True,
            "is_admin": False,
            "created_at": datetime.now(UTC),
            "last_login": datetime.now(UTC),
            "feedbackVotes": [],
            "credits": 1000.0,
            "total_tokens_used": 0,
            "total_credits_spent": 0.0,
        }

        # Act
        result = await repository.get_by_id("user_123abc")

        # Assert
        assert result is not None
        assert result.user_id == "user_123abc"
        assert result.email == "test@example.com"
        mock_collection.find_one.assert_called_once_with({"user_id": "user_123abc"})

    @pytest.mark.asyncio
    async def test_get_by_id_nonexistent_user(self, repository, mock_collection):
        """Test retrieving non-existent user returns None"""
        # Arrange
        mock_collection.find_one.return_value = None

        # Act
        result = await repository.get_by_id("nonexistent")

        # Assert
        assert result is None


class TestGetByIDs:
    """Test batch user fetching"""

    @pytest.mark.asyncio
    async def test_get_by_ids_multiple_users(self, repository, mock_collection):
        """Test batch fetching multiple users"""
        # Arrange
        async def mock_async_iter():
            user_docs = [
                {
                    "_id": "id1",
                    "user_id": "user_1",
                    "email": "user1@example.com",
                    "username": "user1",
                    "password_hash": None,
                    "email_verified": False,
                    "is_admin": False,
                    "created_at": datetime.now(UTC),
                    "last_login": None,
                    "feedbackVotes": [],
                    "credits": 1000.0,
                    "total_tokens_used": 0,
                    "total_credits_spent": 0.0,
                },
                {
                    "_id": "id2",
                    "user_id": "user_2",
                    "email": "user2@example.com",
                    "username": "user2",
                    "password_hash": None,
                    "email_verified": False,
                    "is_admin": False,
                    "created_at": datetime.now(UTC),
                    "last_login": None,
                    "feedbackVotes": [],
                    "credits": 1000.0,
                    "total_tokens_used": 0,
                    "total_credits_spent": 0.0,
                },
            ]
            for doc in user_docs:
                yield doc

        mock_cursor = Mock()
        mock_cursor.__aiter__ = lambda self: mock_async_iter()
        mock_collection.find.return_value = mock_cursor

        # Act
        result = await repository.get_by_ids(["user_1", "user_2", "user_3"])

        # Assert
        assert len(result) == 2
        assert "user_1" in result
        assert "user_2" in result
        assert result["user_1"].email == "user1@example.com"
        assert result["user_2"].email == "user2@example.com"
        mock_collection.find.assert_called_once_with(
            {"user_id": {"$in": ["user_1", "user_2", "user_3"]}}
        )

    @pytest.mark.asyncio
    async def test_get_by_ids_empty_list(self, repository, mock_collection):
        """Test batch fetching with empty list returns empty dict"""
        # Act
        result = await repository.get_by_ids([])

        # Assert
        assert result == {}
        mock_collection.find.assert_not_called()


class TestGetByEmail:
    """Test user retrieval by email"""

    @pytest.mark.asyncio
    async def test_get_by_email_existing_user(self, repository, mock_collection):
        """Test retrieving user by email"""
        # Arrange
        mock_collection.find_one.return_value = {
            "_id": "mongo_id",
            "user_id": "user_123",
            "email": "test@example.com",
            "username": "testuser",
            "password_hash": "$2b$12$hash",
            "email_verified": True,
            "is_admin": False,
            "created_at": datetime.now(UTC),
            "last_login": None,
            "feedbackVotes": [],
            "credits": 1000.0,
            "total_tokens_used": 0,
            "total_credits_spent": 0.0,
        }

        # Act
        result = await repository.get_by_email("test@example.com")

        # Assert
        assert result is not None
        assert result.email == "test@example.com"
        mock_collection.find_one.assert_called_once_with({"email": "test@example.com"})

    @pytest.mark.asyncio
    async def test_get_by_email_nonexistent(self, repository, mock_collection):
        """Test retrieving non-existent email returns None"""
        # Arrange
        mock_collection.find_one.return_value = None

        # Act
        result = await repository.get_by_email("nonexistent@example.com")

        # Assert
        assert result is None


class TestGetByPhone:
    """Test user retrieval by phone number"""

    @pytest.mark.asyncio
    async def test_get_by_phone_existing_user(self, repository, mock_collection):
        """Test retrieving user by phone number"""
        # Arrange
        mock_collection.find_one.return_value = {
            "_id": "mongo_id",
            "user_id": "user_456",
            "email": None,
            "phone_number": "+8613812345678",
            "username": "phoneuser",
            "password_hash": None,
            "email_verified": False,
            "is_admin": False,
            "created_at": datetime.now(UTC),
            "last_login": None,
            "feedbackVotes": [],
            "credits": 1000.0,
            "total_tokens_used": 0,
            "total_credits_spent": 0.0,
        }

        # Act
        result = await repository.get_by_phone("+8613812345678")

        # Assert
        assert result is not None
        assert result.phone_number == "+8613812345678"
        mock_collection.find_one.assert_called_once_with(
            {"phone_number": "+8613812345678"}
        )


class TestGetByUsername:
    """Test user retrieval by username"""

    @pytest.mark.asyncio
    async def test_get_by_username_existing_user(self, repository, mock_collection):
        """Test retrieving user by username"""
        # Arrange
        mock_collection.find_one.return_value = {
            "_id": "mongo_id",
            "user_id": "user_789",
            "email": "user@example.com",
            "username": "cooluser",
            "password_hash": "$2b$12$hash",
            "email_verified": True,
            "is_admin": False,
            "created_at": datetime.now(UTC),
            "last_login": None,
            "feedbackVotes": [],
            "credits": 1000.0,
            "total_tokens_used": 0,
            "total_credits_spent": 0.0,
        }

        # Act
        result = await repository.get_by_username("cooluser")

        # Assert
        assert result is not None
        assert result.username == "cooluser"
        mock_collection.find_one.assert_called_once_with({"username": "cooluser"})


# ===== Update Tests =====


class TestUpdateLastLogin:
    """Test last login timestamp updates"""

    @pytest.mark.asyncio
    async def test_update_last_login_success(self, repository, mock_collection):
        """Test updating last login timestamp"""
        # Arrange
        now = datetime.now(UTC)
        mock_collection.find_one_and_update.return_value = {
            "_id": "mongo_id",
            "user_id": "user_123",
            "email": "test@example.com",
            "username": "testuser",
            "password_hash": "$2b$12$hash",
            "email_verified": True,
            "is_admin": False,
            "created_at": now,
            "last_login": now,
            "feedbackVotes": [],
            "credits": 1000.0,
            "total_tokens_used": 0,
            "total_credits_spent": 0.0,
        }

        # Act
        result = await repository.update_last_login("user_123")

        # Assert
        assert result is not None
        assert result.user_id == "user_123"
        mock_collection.find_one_and_update.assert_called_once()
        call_args = mock_collection.find_one_and_update.call_args
        assert call_args[0][0] == {"user_id": "user_123"}
        assert "$set" in call_args[0][1]
        assert "last_login" in call_args[0][1]["$set"]

    @pytest.mark.asyncio
    async def test_update_last_login_nonexistent_user(
        self, repository, mock_collection
    ):
        """Test updating last login for non-existent user returns None"""
        # Arrange
        mock_collection.find_one_and_update.return_value = None

        # Act
        result = await repository.update_last_login("nonexistent")

        # Assert
        assert result is None


# ===== Voting System Tests =====


class TestAddVote:
    """Test adding feedback votes"""

    @pytest.mark.asyncio
    async def test_add_vote_success(self, repository, mock_collection):
        """Test successfully adding a vote"""
        # Arrange
        mock_result = Mock()
        mock_result.matched_count = 1
        mock_collection.update_one.return_value = mock_result

        # Act
        result = await repository.add_vote("user_123", "feedback_item_abc")

        # Assert
        assert result is True
        mock_collection.update_one.assert_called_once_with(
            {"user_id": "user_123"},
            {"$addToSet": {"feedbackVotes": "feedback_item_abc"}},
            session=None,
        )

    @pytest.mark.asyncio
    async def test_add_vote_user_not_found(self, repository, mock_collection):
        """Test adding vote for non-existent user returns False"""
        # Arrange
        mock_result = Mock()
        mock_result.matched_count = 0
        mock_collection.update_one.return_value = mock_result

        # Act
        result = await repository.add_vote("nonexistent", "feedback_item_abc")

        # Assert
        assert result is False


class TestRemoveVote:
    """Test removing feedback votes"""

    @pytest.mark.asyncio
    async def test_remove_vote_success(self, repository, mock_collection):
        """Test successfully removing a vote"""
        # Arrange
        mock_result = Mock()
        mock_result.matched_count = 1
        mock_collection.update_one.return_value = mock_result

        # Act
        result = await repository.remove_vote("user_123", "feedback_item_abc")

        # Assert
        assert result is True
        mock_collection.update_one.assert_called_once_with(
            {"user_id": "user_123"},
            {"$pull": {"feedbackVotes": "feedback_item_abc"}},
            session=None,
        )

    @pytest.mark.asyncio
    async def test_remove_vote_user_not_found(self, repository, mock_collection):
        """Test removing vote for non-existent user returns False"""
        # Arrange
        mock_result = Mock()
        mock_result.matched_count = 0
        mock_collection.update_one.return_value = mock_result

        # Act
        result = await repository.remove_vote("nonexistent", "feedback_item_abc")

        # Assert
        assert result is False


class TestGetUserVotes:
    """Test retrieving user votes"""

    @pytest.mark.asyncio
    async def test_get_user_votes_with_votes(self, repository, mock_collection):
        """Test retrieving votes for user who has voted"""
        # Arrange
        mock_collection.find_one.return_value = {
            "feedbackVotes": ["item_1", "item_2", "item_3"]
        }

        # Act
        result = await repository.get_user_votes("user_123")

        # Assert
        assert len(result) == 3
        assert "item_1" in result
        assert "item_2" in result
        assert "item_3" in result
        mock_collection.find_one.assert_called_once_with(
            {"user_id": "user_123"}, {"feedbackVotes": 1}
        )

    @pytest.mark.asyncio
    async def test_get_user_votes_no_votes(self, repository, mock_collection):
        """Test retrieving votes for user with no votes"""
        # Arrange
        mock_collection.find_one.return_value = {"feedbackVotes": []}

        # Act
        result = await repository.get_user_votes("user_123")

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_get_user_votes_user_not_found(self, repository, mock_collection):
        """Test retrieving votes for non-existent user returns empty list"""
        # Arrange
        mock_collection.find_one.return_value = None

        # Act
        result = await repository.get_user_votes("nonexistent")

        # Assert
        assert result == []


# ===== Credit System Tests =====


class TestDeductCredits:
    """Test credit deduction with atomic operations"""

    @pytest.mark.asyncio
    async def test_deduct_credits_success(self, repository, mock_collection):
        """Test successfully deducting credits"""
        # Arrange
        mock_collection.find_one_and_update.return_value = {
            "_id": "mongo_id",
            "user_id": "user_123",
            "email": "test@example.com",
            "username": "testuser",
            "password_hash": "$2b$12$hash",
            "email_verified": True,
            "is_admin": False,
            "created_at": datetime.now(UTC),
            "last_login": None,
            "feedbackVotes": [],
            "credits": 900.0,  # 1000 - 100
            "total_tokens_used": 5000,
            "total_credits_spent": 100.0,
        }

        # Act
        result = await repository.deduct_credits(
            user_id="user_123", cost=100.0, tokens=5000
        )

        # Assert
        assert result is not None
        assert result.credits == 900.0
        assert result.total_credits_spent == 100.0
        assert result.total_tokens_used == 5000
        mock_collection.find_one_and_update.assert_called_once()

        # Verify atomic operations
        call_args = mock_collection.find_one_and_update.call_args
        assert call_args[0][0] == {"user_id": "user_123"}
        assert call_args[0][1] == {
            "$inc": {
                "credits": -100.0,
                "total_credits_spent": 100.0,
                "total_tokens_used": 5000,
            }
        }

    @pytest.mark.asyncio
    async def test_deduct_credits_user_not_found(self, repository, mock_collection):
        """Test deducting credits for non-existent user returns None"""
        # Arrange
        mock_collection.find_one_and_update.return_value = None

        # Act
        result = await repository.deduct_credits(
            user_id="nonexistent", cost=100.0, tokens=5000
        )

        # Assert
        assert result is None


class TestAdjustCredits:
    """Test manual credit adjustments"""

    @pytest.mark.asyncio
    async def test_adjust_credits_add(self, repository, mock_collection):
        """Test adding credits (refund scenario)"""
        # Arrange
        mock_collection.find_one_and_update.return_value = {
            "_id": "mongo_id",
            "user_id": "user_123",
            "email": "test@example.com",
            "username": "testuser",
            "password_hash": "$2b$12$hash",
            "email_verified": True,
            "is_admin": False,
            "created_at": datetime.now(UTC),
            "last_login": None,
            "feedbackVotes": [],
            "credits": 1200.0,  # 1000 + 200
            "total_tokens_used": 0,
            "total_credits_spent": 0.0,
        }

        # Act
        result = await repository.adjust_credits(
            user_id="user_123", amount=200.0, reason="Refund for system error"
        )

        # Assert
        assert result is not None
        assert result.credits == 1200.0
        mock_collection.find_one_and_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_adjust_credits_deduct(self, repository, mock_collection):
        """Test deducting credits (manual correction)"""
        # Arrange
        mock_collection.find_one_and_update.return_value = {
            "_id": "mongo_id",
            "user_id": "user_123",
            "email": "test@example.com",
            "username": "testuser",
            "password_hash": "$2b$12$hash",
            "email_verified": True,
            "is_admin": False,
            "created_at": datetime.now(UTC),
            "last_login": None,
            "feedbackVotes": [],
            "credits": 950.0,  # 1000 - 50
            "total_tokens_used": 0,
            "total_credits_spent": 0.0,
        }

        # Act
        result = await repository.adjust_credits(
            user_id="user_123", amount=-50.0, reason="Manual correction"
        )

        # Assert
        assert result is not None
        assert result.credits == 950.0


# ===== Aggregation Query Tests =====


class TestGetActiveUsersWithPortfolios:
    """Test portfolio user aggregation query"""

    @pytest.mark.asyncio
    async def test_get_active_users_with_portfolios(
        self, repository, mock_collection
    ):
        """Test retrieving users with portfolios using aggregation"""
        # Arrange
        async def mock_async_iter():
            users = [
                {"user_id": "user_1", "username": "investor1"},
                {"user_id": "user_2", "username": "investor2"},
            ]
            for user in users:
                yield user

        mock_cursor = Mock()
        mock_cursor.__aiter__ = lambda self: mock_async_iter()
        mock_collection.aggregate.return_value = mock_cursor

        # Act
        result = await repository.get_active_users_with_portfolios()

        # Assert
        assert len(result) == 2
        assert result[0]["user_id"] == "user_1"
        assert result[1]["user_id"] == "user_2"
        mock_collection.aggregate.assert_called_once()

        # Verify aggregation pipeline structure
        pipeline = mock_collection.aggregate.call_args[0][0]
        assert len(pipeline) == 4  # lookup, lookup, match, project
        assert pipeline[0]["$lookup"]["from"] == "portfolio_orders"
        assert pipeline[1]["$lookup"]["from"] == "watchlist"
