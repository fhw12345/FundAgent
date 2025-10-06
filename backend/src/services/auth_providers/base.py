"""
Base authentication provider interface.
All auth providers (email, SMS, WeChat) implement this interface.
"""

from abc import ABC, abstractmethod


class AuthProvider(ABC):
    """Base class for authentication providers."""

    @abstractmethod
    async def send_verification_code(self, identifier: str) -> str:
        """
        Send verification code to user.

        Args:
            identifier: Email, phone number, or other identifier

        Returns:
            Verification code (for dev/testing only)
        """
        pass

    @abstractmethod
    async def verify_code(self, identifier: str, code: str) -> bool:
        """
        Verify the code is valid.

        Args:
            identifier: Email, phone number, or other identifier
            code: Verification code

        Returns:
            True if code is valid
        """
        pass
