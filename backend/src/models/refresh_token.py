"""
Refresh token models for JWT token refresh mechanism.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class RefreshToken(BaseModel):
    """Refresh token model for database storage."""

    token_id: str = Field(..., description="Unique token identifier (UUID)")
    user_id: str = Field(..., description="User this token belongs to")
    token_hash: str = Field(..., description="SHA256 hash of the refresh token")
    expires_at: datetime = Field(..., description="Token expiration timestamp")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used_at: datetime = Field(default_factory=datetime.utcnow)
    revoked: bool = Field(False, description="Token revocation status")
    revoked_at: datetime | None = Field(None, description="Revocation timestamp")
    user_agent: str | None = Field(None, description="Browser/device user agent")
    ip_address: str | None = Field(None, description="IP address for security logging")

    @property
    def is_expired(self) -> bool:
        """Check if token has expired."""
        return datetime.utcnow() > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if token is valid (not revoked and not expired)."""
        return not self.revoked and not self.is_expired

    class Config:
        json_schema_extra = {
            "example": {
                "token_id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "user_abc123",
                "token_hash": "<SHA256_HASH_OF_REFRESH_TOKEN>",
                "expires_at": "2025-10-15T10:00:00Z",
                "created_at": "2025-10-08T10:00:00Z",
                "last_used_at": "2025-10-08T10:00:00Z",
                "revoked": False,
                "revoked_at": None,
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                "ip_address": "192.168.1.100",
            }
        }


class RefreshTokenInDB(RefreshToken):
    """Refresh token model with database ID."""

    id: str = Field(alias="_id")


class TokenPair(BaseModel):
    """Access token + refresh token pair returned on login/refresh."""

    access_token: str = Field(..., description="Short-lived JWT access token")
    refresh_token: str = Field(..., description="Long-lived refresh token")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(..., description="Seconds until access token expires")
    refresh_expires_in: int = Field(
        ..., description="Seconds until refresh token expires"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "<JWT_ACCESS_TOKEN>",
                "refresh_token": "<JWT_REFRESH_TOKEN>",
                "token_type": "bearer",
                "expires_in": 1800,  # 30 minutes
                "refresh_expires_in": 604800,  # 7 days
            }
        }
