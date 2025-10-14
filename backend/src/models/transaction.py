"""
Credit transaction models for the token-based economy.
Immutable audit trail of all credit operations.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CreditTransaction(BaseModel):
    """
    Credit transaction model for database storage.
    Represents a single credit deduction for an LLM operation.

    Status flow: PENDING → COMPLETED (or FAILED if error)
    """

    transaction_id: str = Field(..., description="Unique transaction identifier")
    user_id: str = Field(..., description="User who made the request")
    chat_id: str = Field(..., description="Chat context for this transaction")
    message_id: str | None = Field(
        None, description="Links to assistant message if completed"
    )

    # Status tracking
    status: Literal["PENDING", "COMPLETED", "FAILED"] = Field(
        ..., description="Transaction status"
    )

    # Cost details
    estimated_cost: float = Field(
        ..., description="Conservative cost estimate at request start"
    )
    input_tokens: int | None = Field(
        None, description="Actual input tokens (prompt + history)"
    )
    output_tokens: int | None = Field(
        None, description="Actual output tokens (LLM response)"
    )
    total_tokens: int | None = Field(None, description="Total tokens: input + output")
    actual_cost: float | None = Field(
        None, description="Actual cost calculated: total_tokens / 200"
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Transaction creation time"
    )
    completed_at: datetime | None = Field(
        None, description="Transaction completion or failure time"
    )

    # Metadata
    model: str = Field(default="qwen-plus", description="LLM model used")
    request_type: str = Field(
        default="chat", description="Type of request (chat, analysis, etc.)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "transaction_id": "txn_abc123",
                "user_id": "user_xyz789",
                "chat_id": "chat_def456",
                "message_id": "msg_ghi789",
                "status": "COMPLETED",
                "estimated_cost": 10.0,
                "input_tokens": 500,
                "output_tokens": 1200,
                "total_tokens": 1700,
                "actual_cost": 8.5,
                "created_at": "2025-10-13T10:00:00Z",
                "completed_at": "2025-10-13T10:00:15Z",
                "model": "qwen-plus",
                "request_type": "chat",
            }
        }


class CreditTransactionInDB(CreditTransaction):
    """Credit transaction model with database ID."""

    id: str = Field(alias="_id")


class TransactionCreate(BaseModel):
    """Request model for creating a new transaction."""

    user_id: str
    chat_id: str
    estimated_cost: float
    model: str = "qwen-plus"
    request_type: str = "chat"
