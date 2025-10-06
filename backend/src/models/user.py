"""
User models for authentication and user management.
"""

from datetime import datetime
from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    """Request model for creating a new user."""

    email: str | None = Field(None, description="Email address")
    phone_number: str | None = Field(None, description="Phone number with country code")
    wechat_openid: str | None = Field(None, description="WeChat OpenID")
    username: str | None = Field(None, description="Display name")


class User(BaseModel):
    """User model for database storage. Supports multiple auth methods."""

    user_id: str = Field(..., description="Unique user identifier")
    email: str | None = Field(None, description="Email address (unique if set)")
    phone_number: str | None = Field(None, description="Phone number (unique if set)")
    wechat_openid: str | None = Field(None, description="WeChat OpenID (unique if set)")
    username: str = Field(..., description="Display name")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: datetime | None = Field(None, description="Last login timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_abc123",
                "email": "user@163.com",
                "phone_number": None,
                "wechat_openid": None,
                "username": "User_163",
                "created_at": "2025-10-05T10:00:00Z",
                "last_login": "2025-10-05T10:00:00Z",
            }
        }


class UserInDB(User):
    """User model with database ID."""

    id: str = Field(alias="_id")
