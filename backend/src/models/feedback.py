"""
Feedback models for user feature requests and bug reports.

This module defines the data models for the Feedback & Community Roadmap platform,
including feedback items (features/bugs) and comments.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# Type aliases for clarity
FeedbackType = Literal["feature", "bug"]
FeedbackStatus = Literal["under_consideration", "planned", "in_progress", "completed"]


# ===== Request Models =====


class FeedbackItemCreate(BaseModel):
    """Request model for creating a new feedback item."""

    title: str = Field(
        ...,
        min_length=5,
        max_length=200,
        description="Title of the feedback item",
    )
    description: str = Field(
        ...,
        min_length=10,
        max_length=10000,
        description="Detailed description in Markdown format",
    )
    type: FeedbackType = Field(
        ...,
        description="Type of feedback: 'feature' for feature requests, 'bug' for bug reports",
    )
    image_urls: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="Optional list of image URLs (max 5 images)",
    )


class FeedbackImageUploadRequest(BaseModel):
    """Request model for generating presigned upload URL for images."""

    filename: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Original filename with extension",
    )
    content_type: str = Field(
        ...,
        description="MIME type (e.g., 'image/png', 'image/jpeg')",
    )


class FeedbackImageUploadResponse(BaseModel):
    """Response model for presigned upload URL."""

    upload_url: str = Field(..., description="Presigned URL for uploading the image")
    object_key: str = Field(..., description="OSS object key (path)")
    public_url: str = Field(
        ..., description="Public URL for accessing the uploaded image"
    )
    expires_in: int = Field(..., description="URL expiration time in seconds")


class CommentCreate(BaseModel):
    """Request model for creating a new comment."""

    content: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Comment content in Markdown format",
    )


class FeedbackStatusUpdate(BaseModel):
    """Request model for updating feedback item status (admin only)."""

    status: FeedbackStatus = Field(
        ...,
        description="New status for the feedback item",
    )


# ===== Response Models =====


class FeedbackItem(BaseModel):
    """Response model for feedback items."""

    item_id: str = Field(..., description="Unique feedback item identifier")
    title: str = Field(..., description="Title of the feedback item")
    description: str = Field(..., description="Detailed description (Markdown)")
    authorId: str = Field(..., description="User ID of the author")
    type: FeedbackType = Field(..., description="Type: 'feature' or 'bug'")
    status: FeedbackStatus = Field(
        ...,
        description="Current status of the feedback item",
    )
    voteCount: int = Field(..., description="Total number of votes")
    commentCount: int = Field(..., description="Total number of comments")
    createdAt: datetime = Field(..., description="Creation timestamp")
    updatedAt: datetime = Field(..., description="Last update timestamp")
    image_urls: list[str] = Field(
        default_factory=list,
        description="List of attached image URLs",
    )

    # Computed field set by service layer based on user context
    hasVoted: bool = Field(
        False,
        description="Whether the current user has voted for this item",
    )

    # Author info (joined from users collection)
    authorUsername: str | None = Field(
        None,
        description="Username of the author (optional)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "item_id": "feedback_abc123",
                "title": "Add dark mode toggle",
                "description": "## Problem\nUsers want dark mode for better viewing at night...",
                "authorId": "user_xyz789",
                "type": "feature",
                "status": "under_consideration",
                "voteCount": 42,
                "commentCount": 8,
                "createdAt": "2025-10-12T10:00:00Z",
                "updatedAt": "2025-10-12T15:30:00Z",
                "hasVoted": True,
                "authorUsername": "johndoe",
            }
        }


class Comment(BaseModel):
    """Response model for comments."""

    comment_id: str = Field(..., description="Unique comment identifier")
    itemId: str = Field(..., description="Feedback item ID this comment belongs to")
    authorId: str = Field(..., description="User ID of the comment author")
    content: str = Field(..., description="Comment content (Markdown)")
    createdAt: datetime = Field(..., description="Creation timestamp")

    # Author info (joined from users collection)
    authorUsername: str | None = Field(
        None,
        description="Username of the comment author (optional)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "comment_id": "comment_abc123",
                "itemId": "feedback_abc123",
                "authorId": "user_xyz789",
                "content": "I agree, this would be very useful!",
                "createdAt": "2025-10-12T11:00:00Z",
                "authorUsername": "janedoe",
            }
        }


# ===== Database Models =====


class FeedbackItemInDB(BaseModel):
    """Database model for feedback items (internal use)."""

    item_id: str
    title: str
    description: str
    authorId: str
    type: FeedbackType
    status: FeedbackStatus
    voteCount: int
    commentCount: int
    createdAt: datetime
    updatedAt: datetime
    image_urls: list[str] = []


class CommentInDB(BaseModel):
    """Database model for comments (internal use)."""

    comment_id: str
    itemId: str
    authorId: str
    content: str
    createdAt: datetime
