"""
Request/Response models for chat API endpoints.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

from ...models.chat import Chat, UIState
from ...models.message import Message, MessageMetadata

# ===== Request Models =====


class ChatRequest(BaseModel):
    """Chat request from user."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="User message or analysis results",
    )
    session_id: str | None = Field(
        None, description="Session ID for continuing conversation (legacy)"
    )
    chat_id: str | None = Field(
        None, description="Chat ID for persistent conversation (new MongoDB-based)"
    )
    title: str | None = Field(
        None,
        min_length=1,
        max_length=200,
        description="Optional title for new chat (defaults to 'New Chat')",
    )
    role: Literal["user", "assistant", "system"] = Field(
        "user",
        description="Message role: 'user', 'assistant', or 'system'",
    )
    source: Literal[
        "user", "llm", "fibonacci", "stochastic", "macro", "fundamentals"
    ] = Field(
        "user",
        description="Message source: 'user' (call LLM), 'fibonacci'/'stochastic'/'macro'/'fundamentals' (skip LLM), or 'llm'",
    )
    metadata: MessageMetadata | dict[str, Any] | None = Field(
        None,
        description="Analysis metadata for overlays (Fibonacci levels, Stochastic signals, etc.)",
    )


class UpdateUIStateRequest(BaseModel):
    """Request to update chat UI state."""

    ui_state: UIState


# ===== Response Models =====


class ChatListResponse(BaseModel):
    """Response for listing chats."""

    chats: list[Chat]
    total: int
    page: int
    page_size: int


class ChatDetailResponse(BaseModel):
    """Response for getting chat with messages."""

    chat: Chat
    messages: list[Message]
