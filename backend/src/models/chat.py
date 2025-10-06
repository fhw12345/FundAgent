"""
Chat models for conversation management and UI state restoration.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class UIState(BaseModel):
    """
    UI state for restoring chat interface.
    Stores only current selections, not data (data lives in messages).
    """

    current_symbol: str | None = Field(None, description="Currently selected symbol")
    current_interval: str = Field(
        "1d", description="Current timeframe (1h, 1d, 1w, 1mo)"
    )
    current_date_range: dict[str, str | None] = Field(
        default_factory=lambda: {"start": None, "end": None},
        description="Custom date range if any",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "current_symbol": "AAPL",
                "current_interval": "1d",
                "current_date_range": {"start": "2025-01-01", "end": "2025-10-04"},
            }
        }


class ChatCreate(BaseModel):
    """Request model for creating a new chat."""

    title: str = Field("New Chat", description="Chat title")
    user_id: str = Field(..., description="User who owns this chat")


class ChatUpdate(BaseModel):
    """Request model for updating chat metadata."""

    title: str | None = None
    is_archived: bool | None = None
    ui_state: UIState | None = None


class Chat(BaseModel):
    """
    Chat model for database storage.
    Contains conversation metadata and UI state for restoration.
    """

    chat_id: str = Field(..., description="Unique chat identifier")
    user_id: str = Field(..., description="User who owns this chat")
    title: str = Field("New Chat", description="Chat title")
    is_archived: bool = Field(False, description="Archive status")

    # UI state for restoration (minimal - messages contain actual data)
    ui_state: UIState = Field(
        default_factory=UIState, description="UI restoration state"
    )

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_message_at: datetime | None = Field(None, description="Last message timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "chat_id": "chat_abc123",
                "user_id": "user_xyz789",
                "title": "AAPL Analysis",
                "is_archived": False,
                "ui_state": {
                    "current_symbol": "AAPL",
                    "current_interval": "1d",
                    "current_date_range": {"start": None, "end": None},
                },
                "created_at": "2025-10-05T10:00:00Z",
                "updated_at": "2025-10-05T10:15:00Z",
                "last_message_at": "2025-10-05T10:15:00Z",
            }
        }


class ChatInDB(Chat):
    """Chat model with database ID."""

    id: str = Field(alias="_id")
