"""
Chat session state management.
Following Factor 5: Unified State Management.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass
class ChatMessage:
    """Single message in a conversation."""

    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChatMessage":
        """Create from dictionary."""
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ChatSession:
    """
    Chat session state for a single conversation.

    In v0.2.0: Stored in-memory only
    In v0.3.0+: Will be persisted to MongoDB
    """

    session_id: str
    messages: list[ChatMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    user_id: str | None = None

    # Analysis context (for future integration)
    current_symbol: str | None = None
    current_interval: str = "1d"
    current_period: str = "3mo"

    # Metadata
    metadata: dict = field(default_factory=dict)

    def add_message(
        self, role: Literal["user", "assistant", "system"], content: str
    ) -> None:
        """Add a message to the conversation."""
        message = ChatMessage(role=role, content=content)
        self.messages.append(message)
        self.updated_at = datetime.utcnow()

    def get_conversation_history(self, limit: int | None = None) -> list[ChatMessage]:
        """Get conversation history, optionally limited to recent messages."""
        if limit is None:
            return self.messages
        return self.messages[-limit:]

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "messages": [msg.to_dict() for msg in self.messages],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "user_id": self.user_id,
            "current_symbol": self.current_symbol,
            "current_interval": self.current_interval,
            "current_period": self.current_period,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChatSession":
        """Create from dictionary."""
        return cls(
            session_id=data["session_id"],
            messages=[ChatMessage.from_dict(msg) for msg in data["messages"]],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            user_id=data.get("user_id"),
            current_symbol=data.get("current_symbol"),
            current_interval=data.get("current_interval", "1d"),
            current_period=data.get("current_period", "3mo"),
            metadata=data.get("metadata", {}),
        )
