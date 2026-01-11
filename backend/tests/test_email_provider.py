"""
Unit tests for EmailAuthProvider.

Tests email verification code generation, Redis storage, and Tencent Cloud SES integration.
"""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.services.auth_providers.email_provider import (
    CODE_MAX,
    CODE_MIN,
    EmailAuthProvider,
    _get_or_create_ses_client,
    _ses_client_initialized,
    _ses_client_singleton,
)


# ===== Fixtures =====


@pytest.fixture
def mock_redis():
    """Mock Redis instance."""
    redis = AsyncMock()
    redis.setex = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.delete = AsyncMock()
    return redis


@pytest.fixture
def email_provider(mock_redis):
    """Create EmailAuthProvider with mocked Redis."""
    with patch(
        "src.services.auth_providers.email_provider._get_or_create_ses_client"
    ) as mock_ses:
        mock_ses.return_value = Mock()
        provider = EmailAuthProvider(redis_cache=mock_redis)
        return provider


@pytest.fixture
def email_provider_no_redis():
    """Create EmailAuthProvider without Redis."""
    with patch(
        "src.services.auth_providers.email_provider._get_or_create_ses_client"
    ) as mock_ses:
        mock_ses.return_value = Mock()
        provider = EmailAuthProvider(redis_cache=None)
        return provider


# ===== _make_redis_key Tests =====


class TestMakeRedisKey:
    """Test _make_redis_key method."""

    def test_make_redis_key(self, email_provider):
        """Test Redis key generation."""
        result = email_provider._make_redis_key("test@example.com")
        assert result == "email_code:test@example.com"

    def test_make_redis_key_different_emails(self, email_provider):
        """Test different emails produce different keys."""
        key1 = email_provider._make_redis_key("user1@example.com")
        key2 = email_provider._make_redis_key("user2@example.com")
        assert key1 != key2
        assert "user1@example.com" in key1
        assert "user2@example.com" in key2


# ===== send_verification_code Tests =====


class TestSendVerificationCode:
    """Test send_verification_code method."""

    @pytest.mark.asyncio
    async def test_send_code_dev_bypass(self, mock_redis):
        """Test sending code in dev bypass mode."""
        with patch(
            "src.services.auth_providers.email_provider.settings"
        ) as mock_settings:
            mock_settings.dev_bypass_email_verification = True
            mock_settings.dev_bypass_verification_code = "123456"
            mock_settings.email_code_ttl_seconds = 300

            with patch(
                "src.services.auth_providers.email_provider._get_or_create_ses_client"
            ) as mock_ses:
                mock_ses.return_value = Mock()
                provider = EmailAuthProvider(redis_cache=mock_redis)
                code = await provider.send_verification_code("test@example.com")

                assert code == "123456"
                mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_code_production_mode(self, mock_redis):
        """Test sending code in production mode."""
        with patch(
            "src.services.auth_providers.email_provider.settings"
        ) as mock_settings:
            mock_settings.dev_bypass_email_verification = False
            mock_settings.email_code_ttl_seconds = 300

            with patch(
                "src.services.auth_providers.email_provider._get_or_create_ses_client"
            ) as mock_ses:
                mock_ses_client = Mock()
                mock_ses.return_value = mock_ses_client

                provider = EmailAuthProvider(redis_cache=mock_redis)

                # Mock _send_email_sync to avoid actual SES call
                provider._send_email_sync = Mock()

                code = await provider.send_verification_code("test@example.com")

                # Code should be 6 digits
                assert len(code) == 6
                assert code.isdigit()
                assert CODE_MIN <= int(code) <= CODE_MAX

                # Should store in Redis
                mock_redis.setex.assert_called_once()

                # Should attempt to send email
                provider._send_email_sync.assert_called_once_with("test@example.com", code)

    @pytest.mark.asyncio
    async def test_send_code_no_redis(self, email_provider_no_redis):
        """Test sending code without Redis."""
        with patch(
            "src.services.auth_providers.email_provider.settings"
        ) as mock_settings:
            mock_settings.dev_bypass_email_verification = True
            mock_settings.dev_bypass_verification_code = "123456"

            code = await email_provider_no_redis.send_verification_code("test@example.com")
            assert code == "123456"

    @pytest.mark.asyncio
    async def test_send_code_email_failure(self, mock_redis):
        """Test handling email send failure."""
        with patch(
            "src.services.auth_providers.email_provider.settings"
        ) as mock_settings:
            mock_settings.dev_bypass_email_verification = False
            mock_settings.email_code_ttl_seconds = 300

            with patch(
                "src.services.auth_providers.email_provider._get_or_create_ses_client"
            ) as mock_ses:
                mock_ses.return_value = Mock()
                provider = EmailAuthProvider(redis_cache=mock_redis)
                provider._send_email_sync = Mock(side_effect=Exception("SES Error"))

                with pytest.raises(ValueError, match="Failed to send verification email"):
                    await provider.send_verification_code("test@example.com")


# ===== verify_code Tests =====


class TestVerifyCode:
    """Test verify_code method."""

    @pytest.mark.asyncio
    async def test_verify_code_success(self, mock_redis):
        """Test successful code verification."""
        mock_redis.get.return_value = "123456"

        with patch(
            "src.services.auth_providers.email_provider._get_or_create_ses_client"
        ):
            provider = EmailAuthProvider(redis_cache=mock_redis)
            result = await provider.verify_code("test@example.com", "123456")

            assert result is True
            mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_code_wrong_code(self, mock_redis):
        """Test verification with wrong code."""
        mock_redis.get.return_value = "123456"

        with patch(
            "src.services.auth_providers.email_provider._get_or_create_ses_client"
        ):
            provider = EmailAuthProvider(redis_cache=mock_redis)
            result = await provider.verify_code("test@example.com", "654321")

            assert result is False
            mock_redis.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_verify_code_expired(self, mock_redis):
        """Test verification with expired/missing code."""
        mock_redis.get.return_value = None

        with patch(
            "src.services.auth_providers.email_provider._get_or_create_ses_client"
        ):
            provider = EmailAuthProvider(redis_cache=mock_redis)
            result = await provider.verify_code("test@example.com", "123456")

            assert result is False

    @pytest.mark.asyncio
    async def test_verify_code_no_redis(self, email_provider_no_redis):
        """Test verification fails without Redis."""
        result = await email_provider_no_redis.verify_code("test@example.com", "123456")
        assert result is False

    @pytest.mark.asyncio
    async def test_verify_code_string_numeric(self, mock_redis):
        """Test verification handles string/int comparison."""
        mock_redis.get.return_value = "123456"  # String from Redis

        with patch(
            "src.services.auth_providers.email_provider._get_or_create_ses_client"
        ):
            provider = EmailAuthProvider(redis_cache=mock_redis)
            # Pass code as integer to test str() conversion
            result = await provider.verify_code("test@example.com", 123456)

            assert result is True


# ===== _send_email_sync Tests =====


class TestSendEmailSync:
    """Test _send_email_sync method."""

    def test_send_email_no_ses_client(self):
        """Test error when SES client not initialized."""
        with patch(
            "src.services.auth_providers.email_provider._get_or_create_ses_client"
        ) as mock_ses:
            mock_ses.return_value = None
            provider = EmailAuthProvider(redis_cache=None)

            with pytest.raises(ValueError, match="SES client not initialized"):
                provider._send_email_sync("test@example.com", "123456")

    def test_send_email_success(self):
        """Test successful email sending."""
        with patch(
            "src.services.auth_providers.email_provider._get_or_create_ses_client"
        ) as mock_ses:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.MessageId = "msg-123"
            mock_client.SendEmail.return_value = mock_response
            mock_ses.return_value = mock_client

            with patch(
                "src.services.auth_providers.email_provider.settings"
            ) as mock_settings:
                mock_settings.tencent_ses_from_name = "KlineCubic"
                mock_settings.tencent_ses_from_email = "noreply@example.com"
                mock_settings.email_verification_subject = "Verification"
                mock_settings.tencent_ses_template_id = 12345

                provider = EmailAuthProvider(redis_cache=None)
                provider._send_email_sync("test@example.com", "123456")

                mock_client.SendEmail.assert_called_once()

    def test_send_email_tencent_sdk_exception(self):
        """Test handling Tencent SDK exception."""
        with patch(
            "src.services.auth_providers.email_provider._get_or_create_ses_client"
        ) as mock_ses:
            mock_client = Mock()

            # Create a proper mock exception
            from tencentcloud.common.exception.tencent_cloud_sdk_exception import (
                TencentCloudSDKException,
            )

            mock_client.SendEmail.side_effect = TencentCloudSDKException(
                "InvalidParameter", "Test error"
            )
            mock_ses.return_value = mock_client

            with patch(
                "src.services.auth_providers.email_provider.settings"
            ) as mock_settings:
                mock_settings.tencent_ses_from_name = "KlineCubic"
                mock_settings.tencent_ses_from_email = "noreply@example.com"
                mock_settings.email_verification_subject = "Verification"
                mock_settings.tencent_ses_template_id = 12345

                provider = EmailAuthProvider(redis_cache=None)

                with pytest.raises(TencentCloudSDKException):
                    provider._send_email_sync("test@example.com", "123456")

    def test_send_email_general_exception(self):
        """Test handling general exception."""
        with patch(
            "src.services.auth_providers.email_provider._get_or_create_ses_client"
        ) as mock_ses:
            mock_client = Mock()
            mock_client.SendEmail.side_effect = Exception("Network error")
            mock_ses.return_value = mock_client

            with patch(
                "src.services.auth_providers.email_provider.settings"
            ) as mock_settings:
                mock_settings.tencent_ses_from_name = "KlineCubic"
                mock_settings.tencent_ses_from_email = "noreply@example.com"
                mock_settings.email_verification_subject = "Verification"
                mock_settings.tencent_ses_template_id = 12345

                provider = EmailAuthProvider(redis_cache=None)

                with pytest.raises(Exception, match="Network error"):
                    provider._send_email_sync("test@example.com", "123456")


# ===== _get_or_create_ses_client Tests =====


class TestGetOrCreateSesClient:
    """Test _get_or_create_ses_client function."""

    def test_returns_cached_client(self):
        """Test that singleton returns cached client."""
        # Reset the global state
        import src.services.auth_providers.email_provider as module

        module._ses_client_initialized = True
        mock_client = Mock()
        module._ses_client_singleton = mock_client

        result = _get_or_create_ses_client()
        assert result is mock_client

        # Cleanup
        module._ses_client_initialized = False
        module._ses_client_singleton = None

    def test_no_credentials(self):
        """Test returns None when credentials not configured."""
        import src.services.auth_providers.email_provider as module

        module._ses_client_initialized = False
        module._ses_client_singleton = None

        with patch(
            "src.services.auth_providers.email_provider.settings"
        ) as mock_settings:
            mock_settings.tencent_secret_id = None
            mock_settings.tencent_secret_key = None

            result = _get_or_create_ses_client()
            assert result is None

        # Cleanup
        module._ses_client_initialized = False
        module._ses_client_singleton = None

    def test_creates_client_with_credentials(self):
        """Test creates client when credentials are set."""
        import src.services.auth_providers.email_provider as module

        module._ses_client_initialized = False
        module._ses_client_singleton = None

        with patch(
            "src.services.auth_providers.email_provider.settings"
        ) as mock_settings:
            mock_settings.tencent_secret_id = "test_id"
            mock_settings.tencent_secret_key = "test_key"
            mock_settings.tencent_ses_region = "ap-hongkong"

            with patch(
                "src.services.auth_providers.email_provider.credential.Credential"
            ):
                with patch(
                    "src.services.auth_providers.email_provider.ses_client.SesClient"
                ) as mock_ses_client:
                    mock_client_instance = Mock()
                    mock_ses_client.return_value = mock_client_instance

                    result = _get_or_create_ses_client()
                    assert result is mock_client_instance

        # Cleanup
        module._ses_client_initialized = False
        module._ses_client_singleton = None

    def test_handles_init_exception(self):
        """Test handles exception during initialization."""
        import src.services.auth_providers.email_provider as module

        module._ses_client_initialized = False
        module._ses_client_singleton = None

        with patch(
            "src.services.auth_providers.email_provider.settings"
        ) as mock_settings:
            mock_settings.tencent_secret_id = "test_id"
            mock_settings.tencent_secret_key = "test_key"

            with patch(
                "src.services.auth_providers.email_provider.credential.Credential"
            ) as mock_cred:
                mock_cred.side_effect = Exception("Credential error")

                result = _get_or_create_ses_client()
                assert result is None

        # Cleanup
        module._ses_client_initialized = False
        module._ses_client_singleton = None
