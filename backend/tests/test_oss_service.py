"""
Tests for OSS (Object Storage Service) service.

Tests cover:
- File validation (type, size)
- Object key generation
- Presigned URL generation
- Upload/download operations
"""

from unittest.mock import Mock

import pytest

from src.services.oss_service import (
    ALLOWED_IMAGE_TYPES,
    MAX_FILE_SIZE,
    OSSService,
    get_oss_service,
)


class TestOSSServiceInitialization:
    """Test OSS service initialization."""

    def test_service_initialization(self):
        """Test that OSS service initializes correctly."""
        service = OSSService(
            access_key_id="test_key",
            access_key_secret="test_secret",
            endpoint="oss-cn-hangzhou.aliyuncs.com",
            bucket_name="test-bucket",
        )

        assert service.endpoint == "oss-cn-hangzhou.aliyuncs.com"
        assert service.bucket_name == "test-bucket"
        assert service.bucket is not None

    def test_factory_function(self):
        """Test that factory function creates service with correct defaults."""
        service = get_oss_service(
            access_key_id="test_key",
            access_key_secret="test_secret",
        )

        assert service.endpoint == "oss-cn-shanghai.aliyuncs.com"
        assert service.bucket_name == "klinecubic-financialagent-oss"


class TestObjectKeyGeneration:
    """Test object key generation for uploads."""

    @pytest.fixture
    def service(self):
        """Create OSS service instance."""
        return OSSService(
            access_key_id="test_key",
            access_key_secret="test_secret",
            endpoint="oss-cn-hangzhou.aliyuncs.com",
            bucket_name="test-bucket",
        )

    def test_generate_object_key_format(self, service):
        """Test that object keys follow the expected format."""
        key = service.generate_object_key(
            prefix="feedback",
            filename="screenshot.png",
            user_id="user_123",
        )

        # Should follow format: prefix/YYYY/MM/DD/user_id/hash_filename
        parts = key.split("/")
        assert parts[0] == "feedback"
        assert len(parts[1]) == 4  # Year (YYYY)
        assert len(parts[2]) == 2  # Month (MM)
        assert len(parts[3]) == 2  # Day (DD)
        assert parts[4] == "user_123"
        assert "screenshot.png" in parts[5]

    def test_generate_object_key_unique(self, service):
        """Test that object keys are unique for same inputs."""
        key1 = service.generate_object_key(
            prefix="feedback",
            filename="test.png",
            user_id="user_123",
        )
        key2 = service.generate_object_key(
            prefix="feedback",
            filename="test.png",
            user_id="user_123",
        )

        # Keys should be different due to timestamp in hash
        assert key1 != key2

    def test_generate_object_key_cleans_filename(self, service):
        """Test that filenames with spaces are cleaned."""
        key = service.generate_object_key(
            prefix="feedback",
            filename="my file name.png",
            user_id="user_123",
        )

        # Spaces should be replaced with underscores
        assert "my_file_name.png" in key
        assert " " not in key


class TestFileValidation:
    """Test file type and size validation."""

    @pytest.fixture
    def service(self):
        """Create OSS service instance."""
        return OSSService(
            access_key_id="test_key",
            access_key_secret="test_secret",
            endpoint="oss-cn-hangzhou.aliyuncs.com",
            bucket_name="test-bucket",
        )

    def test_validate_allowed_image_types(self, service):
        """Test that allowed image types are validated correctly."""
        assert service.validate_image_type("image/png") is True
        assert service.validate_image_type("image/jpeg") is True
        assert service.validate_image_type("image/gif") is True
        assert service.validate_image_type("image/webp") is True

    def test_validate_disallowed_types(self, service):
        """Test that disallowed types are rejected."""
        assert service.validate_image_type("image/svg+xml") is False
        assert service.validate_image_type("application/pdf") is False
        assert service.validate_image_type("text/plain") is False
        assert service.validate_image_type("video/mp4") is False

    def test_get_file_extension(self, service):
        """Test getting file extensions from content types."""
        assert service.get_file_extension("image/png") == ".png"
        assert service.get_file_extension("image/jpeg") == ".jpg"
        assert service.get_file_extension("image/gif") == ".gif"
        assert service.get_file_extension("image/webp") == ".webp"
        assert service.get_file_extension("application/pdf") is None


class TestPresignedURLGeneration:
    """Test presigned URL generation for uploads and downloads."""

    @pytest.fixture
    def service(self):
        """Create OSS service instance with mocked bucket."""
        service = OSSService(
            access_key_id="test_key",
            access_key_secret="test_secret",
            endpoint="oss-cn-hangzhou.aliyuncs.com",
            bucket_name="test-bucket",
        )
        # Mock the bucket.sign_url method
        service.bucket.sign_url = Mock(
            return_value="https://test-bucket.oss-cn-hangzhou.aliyuncs.com/test.png?signature=abc123"
        )
        return service

    def test_generate_presigned_upload_url(self, service):
        """Test generating presigned upload URL."""
        result = service.generate_presigned_upload_url(
            object_key="feedback/2025/10/30/user_123/test.png",
            content_type="image/png",
            expires_in_seconds=300,
        )

        assert "url" in result
        assert "object_key" in result
        assert result["object_key"] == "feedback/2025/10/30/user_123/test.png"
        assert "https://" in result["url"]

        # Verify bucket.sign_url was called correctly
        service.bucket.sign_url.assert_called_once_with(
            "PUT",
            "feedback/2025/10/30/user_123/test.png",
            300,
            headers={"Content-Type": "image/png"},
        )

    def test_generate_presigned_download_url(self, service):
        """Test generating presigned download URL."""
        url = service.generate_presigned_download_url(
            object_key="feedback/2025/10/30/user_123/test.png",
            expires_in_seconds=3600,
        )

        assert "https://" in url

        # Verify bucket.sign_url was called correctly
        service.bucket.sign_url.assert_called_once_with(
            "GET",
            "feedback/2025/10/30/user_123/test.png",
            3600,
        )


class TestFileOperations:
    """Test file upload and delete operations."""

    @pytest.fixture
    def service(self):
        """Create OSS service instance with mocked bucket."""
        service = OSSService(
            access_key_id="test_key",
            access_key_secret="test_secret",
            endpoint="oss-cn-hangzhou.aliyuncs.com",
            bucket_name="test-bucket",
        )
        # Mock bucket operations
        service.bucket.put_object = Mock(return_value=Mock(status=200))
        service.bucket.delete_object = Mock(return_value=Mock(status=204))
        return service

    def test_upload_file(self, service):
        """Test uploading file to OSS."""
        file_data = b"fake image data"
        object_key = "feedback/2025/10/30/user_123/test.png"
        content_type = "image/png"

        url = service.upload_file(
            object_key=object_key,
            file_data=file_data,
            content_type=content_type,
        )

        # Verify upload was called
        service.bucket.put_object.assert_called_once_with(
            object_key,
            file_data,
            headers={"Content-Type": content_type},
        )

        # Verify public URL is constructed correctly
        expected_url = f"https://test-bucket.oss-cn-hangzhou.aliyuncs.com/{object_key}"
        assert url == expected_url

    def test_delete_file_success(self, service):
        """Test deleting file from OSS."""
        object_key = "feedback/2025/10/30/user_123/test.png"

        result = service.delete_file(object_key)

        assert result is True
        service.bucket.delete_object.assert_called_once_with(object_key)

    def test_delete_file_failure(self, service):
        """Test handling delete failures."""
        # Mock delete_object to raise an exception
        service.bucket.delete_object = Mock(side_effect=Exception("Delete failed"))

        object_key = "feedback/2025/10/30/user_123/test.png"
        result = service.delete_file(object_key)

        assert result is False


class TestConstants:
    """Test module constants."""

    def test_allowed_image_types(self):
        """Test that allowed image types are defined correctly."""
        assert "image/png" in ALLOWED_IMAGE_TYPES
        assert "image/jpeg" in ALLOWED_IMAGE_TYPES
        assert "image/gif" in ALLOWED_IMAGE_TYPES
        assert "image/webp" in ALLOWED_IMAGE_TYPES
        assert len(ALLOWED_IMAGE_TYPES) == 4

    def test_max_file_size(self):
        """Test that max file size is 10MB."""
        assert MAX_FILE_SIZE == 10 * 1024 * 1024  # 10MB in bytes
