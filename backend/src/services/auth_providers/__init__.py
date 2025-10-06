"""
Modular authentication providers.
Supports email, SMS, WeChat, etc.
"""

from .base import AuthProvider
from .email_provider import EmailAuthProvider

__all__ = ["AuthProvider", "EmailAuthProvider"]
