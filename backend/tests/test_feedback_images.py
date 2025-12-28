"""
Tests for feedback image attachments.

Tests cover:
- Feedback model validation with images
- Image URL storage and retrieval
- Image limits (max 5 images)
"""

import pytest

from src.models.feedback import (
    FeedbackImageUploadRequest,
    FeedbackImageUploadResponse,
    FeedbackItem,
    FeedbackItemCreate,
    FeedbackItemInDB,
)


from src.core.utils.date_utils import utcnow


class TestFeedbackImageModels:
    """Test feedback models with image support."""

    def test_feedback_create_with_images(self):
        """Test creating feedback with image URLs."""
        item = FeedbackItemCreate(
            title="Bug with dark mode",
            description="Dark mode toggle is broken. See screenshot attached.",
            type="bug",
            image_urls=[
                "https://oss.example.com/feedback/2025/10/30/user_123/bug1.png",
                "https://oss.example.com/feedback/2025/10/30/user_123/bug2.png",
            ],
        )

        assert len(item.image_urls) == 2
        assert item.image_urls[0].startswith("https://")

    def test_feedback_create_without_images(self):
        """Test creating feedback without images (default empty list)."""
        item = FeedbackItemCreate(
            title="Feature request",
            description="Add export to CSV",
            type="feature",
        )

        assert item.image_urls == []
        assert len(item.image_urls) == 0

    def test_feedback_create_validates_max_images(self):
        """Test that max 5 images are allowed."""
        # 5 images should be valid
        item_valid = FeedbackItemCreate(
            title="Bug report",
            description="Multiple screenshots",
            type="bug",
            image_urls=[f"https://example.com/img{i}.png" for i in range(5)],
        )
        assert len(item_valid.image_urls) == 5

        # 6 images should raise validation error
        with pytest.raises(ValueError):
            FeedbackItemCreate(
                title="Bug report",
                description="Too many screenshots",
                type="bug",
                image_urls=[f"https://example.com/img{i}.png" for i in range(6)],
            )

    def test_feedback_response_model_includes_images(self):
        """Test that feedback response model includes images."""
        from datetime import datetime

        item = FeedbackItem(
            item_id="feedback_abc123",
            title="Bug with images",
            description="See attached screenshots",
            authorId="user_123",
            type="bug",
            status="under_consideration",
            voteCount=5,
            commentCount=2,
            createdAt=utcnow(),
            updatedAt=utcnow(),
            image_urls=[
                "https://oss.example.com/feedback/img1.png",
                "https://oss.example.com/feedback/img2.png",
            ],
            hasVoted=False,
            authorUsername="johndoe",
        )

        assert len(item.image_urls) == 2
        assert isinstance(item.image_urls, list)

    def test_feedback_db_model_includes_images(self):
        """Test that database model includes images."""
        from datetime import datetime

        item = FeedbackItemInDB(
            item_id="feedback_abc123",
            title="Bug report",
            description="Test description",
            authorId="user_123",
            type="bug",
            status="under_consideration",
            voteCount=0,
            commentCount=0,
            createdAt=utcnow(),
            updatedAt=utcnow(),
            image_urls=[
                "https://oss.example.com/feedback/img1.png",
            ],
        )

        assert len(item.image_urls) == 1

    def test_feedback_db_model_default_empty_images(self):
        """Test that database model has empty images by default."""
        from datetime import datetime

        item = FeedbackItemInDB(
            item_id="feedback_abc123",
            title="Bug report",
            description="Test description",
            authorId="user_123",
            type="bug",
            status="under_consideration",
            voteCount=0,
            commentCount=0,
            createdAt=utcnow(),
            updatedAt=utcnow(),
        )

        assert item.image_urls == []


class TestImageUploadModels:
    """Test image upload request/response models."""

    def test_image_upload_request_validation(self):
        """Test image upload request validation."""
        request = FeedbackImageUploadRequest(
            filename="screenshot.png",
            content_type="image/png",
        )

        assert request.filename == "screenshot.png"
        assert request.content_type == "image/png"

    def test_image_upload_request_invalid_filename(self):
        """Test that empty filename is rejected."""
        with pytest.raises(ValueError):
            FeedbackImageUploadRequest(
                filename="",
                content_type="image/png",
            )

    def test_image_upload_request_long_filename(self):
        """Test that filename over 255 chars is rejected."""
        long_filename = "a" * 256 + ".png"
        with pytest.raises(ValueError):
            FeedbackImageUploadRequest(
                filename=long_filename,
                content_type="image/png",
            )

    def test_image_upload_response_structure(self):
        """Test image upload response structure."""
        response = FeedbackImageUploadResponse(
            upload_url="https://bucket.oss-cn-hangzhou.aliyuncs.com/path/file.png?signature=abc",
            object_key="feedback/2025/10/30/user_123/hash_file.png",
            public_url="https://bucket.oss-cn-hangzhou.aliyuncs.com/path/file.png",
            expires_in=300,
        )

        assert "https://" in response.upload_url
        assert "feedback/" in response.object_key
        assert response.expires_in == 300
        assert "https://" in response.public_url
