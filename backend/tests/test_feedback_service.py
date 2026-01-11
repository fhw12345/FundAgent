"""
Unit tests for FeedbackService.

Tests feedback platform business logic including voting, comments, and status updates.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, MagicMock

import pytest

from src.models.feedback import Comment, CommentCreate, FeedbackItem, FeedbackItemCreate
from src.services.feedback_service import FeedbackService


# ===== Fixtures =====


@pytest.fixture
def mock_feedback_repo():
    """Mock FeedbackRepository"""
    repo = Mock()
    repo.get_by_id = AsyncMock()
    repo.create = AsyncMock()
    repo.list_by_type = AsyncMock()
    repo.increment_vote_count = AsyncMock()
    repo.increment_comment_count = AsyncMock()
    repo.update_status = AsyncMock()
    return repo


@pytest.fixture
def mock_comment_repo():
    """Mock CommentRepository"""
    repo = Mock()
    repo.create = AsyncMock()
    repo.list_by_item = AsyncMock()
    return repo


@pytest.fixture
def mock_user_repo():
    """Mock UserRepository"""
    repo = Mock()
    repo.get_by_id = AsyncMock()
    repo.get_by_ids = AsyncMock()
    repo.get_user_votes = AsyncMock()
    repo.add_vote = AsyncMock()
    repo.remove_vote = AsyncMock()
    return repo


@pytest.fixture
def mock_mongodb():
    """Mock MongoDB instance"""
    mongodb = Mock()
    mongodb.client = None  # No transactions by default
    return mongodb


@pytest.fixture
def feedback_service(mock_feedback_repo, mock_comment_repo, mock_user_repo, mock_mongodb):
    """Create FeedbackService with mocked dependencies"""
    return FeedbackService(
        feedback_repo=mock_feedback_repo,
        comment_repo=mock_comment_repo,
        user_repo=mock_user_repo,
        mongodb=mock_mongodb,
    )


@pytest.fixture
def sample_feedback_item():
    """Sample feedback item for tests"""
    return FeedbackItem(
        item_id="item_123",
        authorId="user_456",
        type="feature",
        title="Add dark mode",
        description="Please add dark mode support",
        status="under_consideration",
        voteCount=5,
        commentCount=2,
        createdAt=datetime.now(timezone.utc),
        updatedAt=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_user():
    """Sample user for tests"""
    user = Mock()
    user.user_id = "user_456"
    user.username = "testuser"
    return user


@pytest.fixture
def sample_comment():
    """Sample comment for tests"""
    return Comment(
        comment_id="comment_789",
        itemId="item_123",
        authorId="user_456",
        content="Great idea!",
        createdAt=datetime.now(timezone.utc),
    )


# ===== create_item Tests =====


class TestCreateItem:
    """Test create_item method"""

    @pytest.mark.asyncio
    async def test_create_item_success(
        self, feedback_service, mock_feedback_repo, mock_user_repo, sample_feedback_item, sample_user
    ):
        """Test successful feedback item creation"""
        mock_feedback_repo.create.return_value = sample_feedback_item
        mock_user_repo.get_by_id.return_value = sample_user

        item_create = FeedbackItemCreate(
            type="feature",
            title="Add dark mode",
            description="Please add dark mode support",
        )

        result = await feedback_service.create_item(item_create, "user_456")

        assert result.item_id == "item_123"
        assert result.authorUsername == "testuser"
        mock_feedback_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_item_no_author_found(
        self, feedback_service, mock_feedback_repo, mock_user_repo, sample_feedback_item
    ):
        """Test item creation when author not found"""
        mock_feedback_repo.create.return_value = sample_feedback_item
        mock_user_repo.get_by_id.return_value = None

        item_create = FeedbackItemCreate(
            type="bug",
            title="Bug report",
            description="Something is broken",
        )

        result = await feedback_service.create_item(item_create, "user_456")

        assert result.item_id == "item_123"
        assert result.authorUsername is None


# ===== get_item Tests =====


class TestGetItem:
    """Test get_item method"""

    @pytest.mark.asyncio
    async def test_get_item_success(
        self, feedback_service, mock_feedback_repo, mock_user_repo, sample_feedback_item, sample_user
    ):
        """Test successful item retrieval"""
        mock_feedback_repo.get_by_id.return_value = sample_feedback_item
        mock_user_repo.get_user_votes.return_value = ["item_123"]
        mock_user_repo.get_by_id.return_value = sample_user

        result = await feedback_service.get_item("item_123", "user_456")

        assert result.item_id == "item_123"
        assert result.hasVoted is True
        assert result.authorUsername == "testuser"

    @pytest.mark.asyncio
    async def test_get_item_not_voted(
        self, feedback_service, mock_feedback_repo, mock_user_repo, sample_feedback_item, sample_user
    ):
        """Test item retrieval when user hasn't voted"""
        mock_feedback_repo.get_by_id.return_value = sample_feedback_item
        mock_user_repo.get_user_votes.return_value = []  # No votes
        mock_user_repo.get_by_id.return_value = sample_user

        result = await feedback_service.get_item("item_123", "user_456")

        assert result.hasVoted is False

    @pytest.mark.asyncio
    async def test_get_item_not_found(self, feedback_service, mock_feedback_repo):
        """Test item not found"""
        mock_feedback_repo.get_by_id.return_value = None

        result = await feedback_service.get_item("nonexistent", "user_456")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_item_no_user_id(
        self, feedback_service, mock_feedback_repo, mock_user_repo, sample_feedback_item, sample_user
    ):
        """Test item retrieval without user_id"""
        mock_feedback_repo.get_by_id.return_value = sample_feedback_item
        mock_user_repo.get_by_id.return_value = sample_user

        result = await feedback_service.get_item("item_123", user_id=None)

        # hasVoted not set when no user_id
        assert result.item_id == "item_123"
        mock_user_repo.get_user_votes.assert_not_called()


# ===== list_items Tests =====


class TestListItems:
    """Test list_items method"""

    @pytest.mark.asyncio
    async def test_list_items_success(
        self, feedback_service, mock_feedback_repo, mock_user_repo, sample_feedback_item, sample_user
    ):
        """Test successful items listing"""
        mock_feedback_repo.list_by_type.return_value = [sample_feedback_item]
        mock_user_repo.get_user_votes.return_value = ["item_123"]
        mock_user_repo.get_by_ids.return_value = {"user_456": sample_user}

        result = await feedback_service.list_items(
            feedback_type="feature", user_id="user_456"
        )

        assert len(result) == 1
        assert result[0].hasVoted is True
        assert result[0].authorUsername == "testuser"

    @pytest.mark.asyncio
    async def test_list_items_empty(self, feedback_service, mock_feedback_repo):
        """Test empty items list"""
        mock_feedback_repo.list_by_type.return_value = []

        result = await feedback_service.list_items()

        assert result == []

    @pytest.mark.asyncio
    async def test_list_items_no_user_id(
        self, feedback_service, mock_feedback_repo, mock_user_repo, sample_feedback_item, sample_user
    ):
        """Test listing without user context"""
        mock_feedback_repo.list_by_type.return_value = [sample_feedback_item]
        mock_user_repo.get_by_ids.return_value = {"user_456": sample_user}

        result = await feedback_service.list_items(user_id=None)

        assert len(result) == 1
        mock_user_repo.get_user_votes.assert_not_called()


# ===== vote_item Tests =====


class TestVoteItem:
    """Test vote_item method"""

    @pytest.mark.asyncio
    async def test_vote_item_success(
        self, feedback_service, mock_feedback_repo, mock_user_repo, sample_feedback_item
    ):
        """Test successful vote"""
        mock_feedback_repo.get_by_id.return_value = sample_feedback_item
        mock_user_repo.get_user_votes.return_value = []  # Not voted yet
        mock_feedback_repo.increment_vote_count.return_value = True
        mock_user_repo.add_vote.return_value = True

        result = await feedback_service.vote_item("item_123", "user_456")

        assert result is True
        mock_feedback_repo.increment_vote_count.assert_called_once()
        mock_user_repo.add_vote.assert_called_once()

    @pytest.mark.asyncio
    async def test_vote_item_already_voted(
        self, feedback_service, mock_feedback_repo, mock_user_repo, sample_feedback_item
    ):
        """Test idempotent vote (already voted)"""
        mock_feedback_repo.get_by_id.return_value = sample_feedback_item
        mock_user_repo.get_user_votes.return_value = ["item_123"]  # Already voted

        result = await feedback_service.vote_item("item_123", "user_456")

        assert result is False
        mock_feedback_repo.increment_vote_count.assert_not_called()

    @pytest.mark.asyncio
    async def test_vote_item_not_found(self, feedback_service, mock_feedback_repo):
        """Test vote on non-existent item"""
        mock_feedback_repo.get_by_id.return_value = None

        result = await feedback_service.vote_item("nonexistent", "user_456")

        assert result is False

    @pytest.mark.asyncio
    async def test_vote_item_increment_fails(
        self, feedback_service, mock_feedback_repo, mock_user_repo, sample_feedback_item
    ):
        """Test vote when increment fails"""
        mock_feedback_repo.get_by_id.return_value = sample_feedback_item
        mock_user_repo.get_user_votes.return_value = []
        mock_feedback_repo.increment_vote_count.return_value = False

        result = await feedback_service.vote_item("item_123", "user_456")

        assert result is False


# ===== unvote_item Tests =====


class TestUnvoteItem:
    """Test unvote_item method"""

    @pytest.mark.asyncio
    async def test_unvote_item_success(
        self, feedback_service, mock_feedback_repo, mock_user_repo, sample_feedback_item
    ):
        """Test successful unvote"""
        mock_feedback_repo.get_by_id.return_value = sample_feedback_item
        mock_user_repo.get_user_votes.return_value = ["item_123"]  # Has voted
        mock_feedback_repo.increment_vote_count.return_value = True
        mock_user_repo.remove_vote.return_value = True

        result = await feedback_service.unvote_item("item_123", "user_456")

        assert result is True
        mock_feedback_repo.increment_vote_count.assert_called_once_with("item_123", delta=-1)

    @pytest.mark.asyncio
    async def test_unvote_item_not_voted(
        self, feedback_service, mock_feedback_repo, mock_user_repo, sample_feedback_item
    ):
        """Test idempotent unvote (not voted)"""
        mock_feedback_repo.get_by_id.return_value = sample_feedback_item
        mock_user_repo.get_user_votes.return_value = []  # Not voted

        result = await feedback_service.unvote_item("item_123", "user_456")

        assert result is False

    @pytest.mark.asyncio
    async def test_unvote_item_not_found(self, feedback_service, mock_feedback_repo):
        """Test unvote on non-existent item"""
        mock_feedback_repo.get_by_id.return_value = None

        result = await feedback_service.unvote_item("nonexistent", "user_456")

        assert result is False


# ===== add_comment Tests =====


class TestAddComment:
    """Test add_comment method"""

    @pytest.mark.asyncio
    async def test_add_comment_success(
        self, feedback_service, mock_feedback_repo, mock_comment_repo, mock_user_repo,
        sample_feedback_item, sample_comment, sample_user
    ):
        """Test successful comment addition"""
        mock_feedback_repo.get_by_id.return_value = sample_feedback_item
        mock_comment_repo.create.return_value = sample_comment
        mock_user_repo.get_by_id.return_value = sample_user

        comment_create = CommentCreate(content="Great idea!")

        result = await feedback_service.add_comment(
            "item_123", comment_create, "user_456"
        )

        assert result.comment_id == "comment_789"
        assert result.authorUsername == "testuser"
        mock_feedback_repo.increment_comment_count.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_comment_item_not_found(
        self, feedback_service, mock_feedback_repo
    ):
        """Test comment on non-existent item"""
        mock_feedback_repo.get_by_id.return_value = None

        comment_create = CommentCreate(content="Comment")
        result = await feedback_service.add_comment(
            "nonexistent", comment_create, "user_456"
        )

        assert result is None


# ===== get_comments Tests =====


class TestGetComments:
    """Test get_comments method"""

    @pytest.mark.asyncio
    async def test_get_comments_success(
        self, feedback_service, mock_comment_repo, mock_user_repo, sample_comment, sample_user
    ):
        """Test successful comments retrieval"""
        mock_comment_repo.list_by_item.return_value = [sample_comment]
        mock_user_repo.get_by_ids.return_value = {"user_456": sample_user}

        result = await feedback_service.get_comments("item_123")

        assert len(result) == 1
        assert result[0].authorUsername == "testuser"

    @pytest.mark.asyncio
    async def test_get_comments_empty(self, feedback_service, mock_comment_repo):
        """Test getting comments from item with no comments"""
        mock_comment_repo.list_by_item.return_value = []

        result = await feedback_service.get_comments("item_123")

        assert result == []


# ===== update_status Tests =====


class TestUpdateStatus:
    """Test update_status method"""

    @pytest.mark.asyncio
    async def test_update_status_success(
        self, feedback_service, mock_feedback_repo, mock_user_repo, sample_feedback_item, sample_user
    ):
        """Test successful status update"""
        updated_data = sample_feedback_item.model_dump()
        updated_data["status"] = "in_progress"
        updated_item = FeedbackItem(**updated_data)

        mock_feedback_repo.get_by_id.side_effect = [sample_feedback_item, updated_item]
        mock_feedback_repo.update_status.return_value = True
        mock_user_repo.get_by_id.return_value = sample_user

        result = await feedback_service.update_status("item_123", "in_progress")

        assert result.status == "in_progress"
        mock_feedback_repo.update_status.assert_called_once_with("item_123", "in_progress")

    @pytest.mark.asyncio
    async def test_update_status_item_not_found(
        self, feedback_service, mock_feedback_repo
    ):
        """Test status update on non-existent item"""
        mock_feedback_repo.get_by_id.return_value = None

        result = await feedback_service.update_status("nonexistent", "closed")

        assert result is None

    @pytest.mark.asyncio
    async def test_update_status_failed(
        self, feedback_service, mock_feedback_repo, sample_feedback_item
    ):
        """Test status update failure"""
        mock_feedback_repo.get_by_id.return_value = sample_feedback_item
        mock_feedback_repo.update_status.return_value = False

        result = await feedback_service.update_status("item_123", "closed")

        assert result is None
