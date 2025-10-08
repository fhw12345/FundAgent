"""
Email authentication provider using Tencent Cloud SES API.
Sends verification codes via email using templates.
"""

import json
import random

import structlog
from redis.asyncio import Redis
from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import (
    TencentCloudSDKException,
)
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.ses.v20201002 import models, ses_client

from ...core.config import get_settings
from .base import AuthProvider

logger = structlog.get_logger()
settings = get_settings()

# Verification code configuration
CODE_MIN = 100000  # 6-digit minimum
CODE_MAX = 999999  # 6-digit maximum


class EmailAuthProvider(AuthProvider):
    """Email-based authentication using Tencent Cloud SES."""

    def __init__(self, redis_cache: Redis | None = None):
        """
        Initialize email auth provider.

        Args:
            redis_cache: Optional Redis instance for storing codes
        """
        self.redis = redis_cache
        self.ses_client = None

        # Initialize SES client if credentials are available
        if settings.tencent_secret_id and settings.tencent_secret_key:
            try:
                cred = credential.Credential(
                    settings.tencent_secret_id, settings.tencent_secret_key
                )
                http_profile = HttpProfile()
                http_profile.endpoint = "ses.tencentcloudapi.com"

                client_profile = ClientProfile()
                client_profile.httpProfile = http_profile

                # Initialize client with region
                self.ses_client = ses_client.SesClient(
                    cred, settings.tencent_ses_region, client_profile
                )
                logger.info("Tencent Cloud SES client initialized")
            except Exception as e:
                logger.error("Failed to initialize SES client", error=str(e))

    def _make_redis_key(self, email: str) -> str:
        """Generate Redis key for email verification code."""
        return f"email_code:{email}"

    async def send_verification_code(self, email: str) -> str:
        """
        Send verification code to email address.

        In development bypass mode, uses fixed code and skips email sending.

        Args:
            email: Email address

        Returns:
            Verification code (6-digit)
        """
        # Use fixed code in dev bypass mode
        if settings.dev_bypass_email_verification:
            code = settings.dev_bypass_verification_code
            logger.warning(
                "DEV BYPASS MODE: Using fixed verification code (email NOT sent)",
                email=email,
                code=code,
                bypass_enabled=True,
            )
        else:
            # Generate random 6-digit code in production
            code = str(random.randint(CODE_MIN, CODE_MAX))

        # Store code in Redis with TTL from settings
        if self.redis:
            await self.redis.setex(
                self._make_redis_key(email), settings.email_code_ttl_seconds, code
            )

        # Send email via Tencent Cloud SES (skip in dev bypass mode)
        if settings.dev_bypass_email_verification:
            logger.info("DEV BYPASS: Email sending skipped", email=email, code=code)
        else:
            try:
                self._send_email_sync(email, code)
                logger.info("Verification code sent via Tencent Cloud SES", email=email)
            except Exception as e:
                logger.error("Failed to send email via SES", email=email, error=str(e))
                raise ValueError(f"Failed to send verification email: {str(e)}") from e

        return code

    async def verify_code(self, email: str, code: str) -> bool:
        """
        Verify email verification code.

        Args:
            email: Email address
            code: 6-digit verification code

        Returns:
            True if code is valid
        """
        # Check code from Redis
        if self.redis:
            redis_key = self._make_redis_key(email)
            stored_code = await self.redis.get(redis_key)
            logger.info(
                "Verifying code",
                email=email,
                provided_code=code,
                stored_code=stored_code,
                match=stored_code == code if stored_code else False,
            )
            if stored_code and str(stored_code) == str(code):
                # Delete code after successful verification
                await self.redis.delete(redis_key)
                return True
            return False

        # If Redis is unavailable, verification fails
        logger.error("Cannot verify code: Redis unavailable")
        return False

    def _send_email_sync(self, to_email: str, code: str) -> None:
        """
        Send email verification code using Tencent Cloud SES API with template.

        Args:
            to_email: Recipient email address
            code: 6-digit verification code
        """
        # Check SES client initialization
        if not self.ses_client:
            raise ValueError(
                "Tencent Cloud SES client not initialized. "
                "Set TENCENT_SECRET_ID and TENCENT_SECRET_KEY environment variables."
            )

        try:
            # Create SendEmail request
            req = models.SendEmailRequest()

            # Prepare request parameters according to Tencent Cloud SES API spec
            # TemplateData must match template variables: {{email}} and {{code}}
            template_data = {"email": to_email, "code": code}

            params = {
                "FromEmailAddress": f"{settings.tencent_ses_from_name} <{settings.tencent_ses_from_email}>",
                "Destination": [to_email],
                "Subject": settings.email_verification_subject,
                "Template": {
                    "TemplateID": settings.tencent_ses_template_id,
                    "TemplateData": json.dumps(template_data),
                },
            }

            logger.info(
                "Sending SES email",
                to_email=to_email,
                template_data=template_data,
                template_id=settings.tencent_ses_template_id,
            )

            req.from_json_string(json.dumps(params))

            # Send email via SES API
            resp = self.ses_client.SendEmail(req)

            logger.info(
                "Email sent successfully via Tencent Cloud SES",
                to_email=to_email,
                template_id=settings.tencent_ses_template_id,
                message_id=resp.MessageId if hasattr(resp, "MessageId") else None,
            )

        except TencentCloudSDKException as e:
            logger.error(
                "Tencent Cloud SES error",
                error=str(e),
                error_code=e.code if hasattr(e, "code") else None,
                request_id=e.requestId if hasattr(e, "requestId") else None,
                to_email=to_email,
            )
            raise
        except Exception as e:
            logger.error(
                "Unexpected error sending email",
                error=str(e),
                error_type=type(e).__name__,
                to_email=to_email,
            )
            raise
