"""
Message models for chat conversations.
Everything is a message - user text, LLM responses, and analysis results.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

class ToolCall(BaseModel):
    """Tool invocation metadata for UI rendering."""

    tool_name: str = Field(..., description="Name of the tool invoked")
    tool_input: dict[str, Any] | None = Field(None, description="Input parameters")
    tool_output: str | None = Field(None, description="Tool output text")


class MessageMetadata(BaseModel):
    """
    Flexible metadata for messages.
    Contains analysis data for Fibonacci, Stochastic, etc.
    """

    # Common fields
    symbol: str | None = Field(default=None, description="Fund code or symbol")
    timeframe: str | None = Field(default=None, description="Analysis timeframe")

    # LLM-specific
    model: str | None = Field(default=None, description="LLM model used")
    tokens: int | None = Field(default=None, description="Total token count")
    input_tokens: int | None = Field(default=None, description="Input tokens consumed")
    output_tokens: int | None = Field(
        default=None, description="Output tokens generated"
    )

    # Credit transaction linkage
    transaction_id: str | None = Field(
        default=None, description="Links to credit transaction for this message"
    )

    # LangGraph agent tracing
    trace_id: str | None = Field(
        default=None, description="OpenTelemetry trace ID for observability"
    )
    selected_tool: str | None = Field(
        default=None,
        description="Tool selected by LangGraph agent (fibonacci/stochastic)",
    )
    has_tool_result: bool | None = Field(
        default=None, description="Whether agent executed a tool in this response"
    )

    # Context compaction
    is_summary: bool = Field(
        default=False,
        description="True if this message is a compacted summary of older messages",
    )
    summarized_message_count: int | None = Field(
        default=None,
        description="Number of messages that were summarized into this message",
    )

    # Extensible - any additional data
    raw_data: dict[str, Any] | None = Field(
        default=None, description="Raw analysis data"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "110011",
                "timeframe": "1y",
            }
        }


class MessageCreate(BaseModel):
    """Request model for creating a new message."""

    chat_id: str
    role: Literal["user", "assistant", "system"]
    content: str
    source: Literal["user", "llm", "tool"]
    metadata: MessageMetadata = MessageMetadata()
    tool_call: ToolCall | None = None


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
    source: Literal["user", "llm", "tool"] = Field(
        ...,
        description="Message source: 'user' (user input), 'llm' (LLM response), 'tool' (tool output). Use metadata.selected_tool to identify specific tool.",
    )

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: MessageMetadata = Field(
        default=MessageMetadata(),
        description="Flexible metadata for analysis data",
    )

    # Tool invocation metadata for UI rendering
    tool_call: ToolCall | None = Field(
        default=None,
        description="Tool invocation metadata for collapsible UI wrapper (when source='tool')",
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
