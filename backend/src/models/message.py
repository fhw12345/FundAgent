"""
Message models for chat conversations.
Everything is a message - user text, LLM responses, and analysis results.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MessageMetadata(BaseModel):
    """
    Flexible metadata for messages.
    Contains analysis data for Fibonacci, Stochastic, etc.
    """

    # Common fields for analysis messages
    symbol: str | None = Field(None, description="Stock symbol")
    timeframe: str | None = Field(None, description="Analysis timeframe")

    # Fibonacci-specific
    fibonacci_levels: list[dict] | None = Field(
        None, description="Fibonacci retracement levels"
    )
    trend_direction: str | None = Field(None, description="uptrend or downtrend")
    swing_high: dict | None = Field(None, description="Swing high price and date")
    swing_low: dict | None = Field(None, description="Swing low price and date")
    confidence_score: float | None = Field(None, description="Analysis confidence")

    # Stochastic-specific
    stochastic_k: float | None = Field(None, description="%K value")
    stochastic_d: float | None = Field(None, description="%D value")
    overbought: bool | None = Field(None, description="Overbought condition")
    oversold: bool | None = Field(None, description="Oversold condition")

    # LLM-specific
    model: str | None = Field(None, description="LLM model used")
    tokens: int | None = Field(None, description="Token count")

    # Extensible - any additional data
    raw_data: dict | None = Field(None, description="Raw analysis data")

    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "AAPL",
                "timeframe": "1d",
                "fibonacci_levels": [
                    {"level": 0, "price": 150.0, "percentage": "0%"},
                    {"level": 0.618, "price": 186.18, "percentage": "61.8%"},
                ],
                "trend_direction": "uptrend",
                "swing_high": {"price": 210.0, "date": "2025-10-01"},
                "swing_low": {"price": 150.0, "date": "2025-09-01"},
                "confidence_score": 0.85,
            }
        }


class MessageCreate(BaseModel):
    """Request model for creating a new message."""

    chat_id: str
    role: Literal["user", "assistant", "system"]
    content: str
    source: Literal["user", "llm", "fibonacci", "stochastic", "macro"]
    metadata: MessageMetadata = Field(default_factory=MessageMetadata)


class Message(BaseModel):
    """
    Message model for database storage.
    Represents user messages, LLM responses, and analysis results.
    """

    message_id: str = Field(..., description="Unique message identifier")
    chat_id: str = Field(..., description="Chat this message belongs to")

    role: Literal["user", "assistant", "system"] = Field(
        ..., description="Message role"
    )
    content: str = Field(..., description="Message text content")
    source: Literal["user", "llm", "fibonacci", "stochastic", "macro"] = Field(
        ..., description="Message source/type"
    )

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: MessageMetadata = Field(
        default_factory=MessageMetadata,
        description="Flexible metadata for analysis data",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message_id": "msg_abc123",
                "chat_id": "chat_xyz789",
                "role": "assistant",
                "content": "## Fibonacci Analysis - AAPL\n\nLevels calculated...",
                "source": "fibonacci",
                "timestamp": "2025-10-05T10:15:00Z",
                "metadata": {
                    "symbol": "AAPL",
                    "timeframe": "1d",
                    "fibonacci_levels": [
                        {"level": 0.618, "price": 186.18, "percentage": "61.8%"}
                    ],
                },
            }
        }


class MessageInDB(Message):
    """Message model with database ID."""

    id: str = Field(alias="_id")
