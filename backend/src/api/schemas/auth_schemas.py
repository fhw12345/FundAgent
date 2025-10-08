"""
Authentication API request/response schemas.
Pydantic models for validation.
"""

from typing import Literal

from pydantic import BaseModel, Field

from ...models.user import User


class SendCodeRequest(BaseModel):
    """Request to send verification code (email or phone)."""

    auth_type: Literal["email", "phone"] = Field(..., description="Authentication type")
    identifier: str = Field(..., description="Email or phone number")


class SendCodeResponse(BaseModel):
    """Response for send code request."""

    message: str
    code: str | None = Field(
        None, description="Verification code (dev mode only)"
    )  # Only returned in dev


class VerifyCodeRequest(BaseModel):
    """Request to verify code and login."""

    auth_type: Literal["email", "phone"] = Field(..., description="Authentication type")
    identifier: str = Field(..., description="Email or phone number")
    code: str = Field(..., description="6-digit verification code")


class LoginResponse(BaseModel):
    """Response for login request with token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int
    user: User


class RegisterRequest(BaseModel):
    """Request to register a new user."""

    email: str = Field(..., description="Email address")
    code: str = Field(..., description="6-digit verification code")
    username: str = Field(..., min_length=3, max_length=20, description="Username")
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")


class LoginRequest(BaseModel):
    """Request to login with username and password."""

    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")


class ResetPasswordRequest(BaseModel):
    """Request to reset password using email verification."""

    email: str = Field(..., description="Email address")
    code: str = Field(..., description="6-digit verification code")
    new_password: str = Field(
        ..., min_length=8, description="New password (min 8 characters)"
    )


class RefreshTokenRequest(BaseModel):
    """Request to refresh access token."""

    refresh_token: str = Field(..., description="JWT refresh token")


class LogoutRequest(BaseModel):
    """Request to logout (revoke refresh token)."""

    refresh_token: str = Field(..., description="JWT refresh token to revoke")
