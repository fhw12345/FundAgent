"""Admin API response models."""

from pydantic import BaseModel, Field


class DatabaseStats(BaseModel):
    """Statistics for a single MongoDB collection."""

    collection: str = Field(..., description="Collection name")
    document_count: int = Field(..., description="Number of documents")
    size_bytes: int = Field(..., description="Total size in bytes")
    size_mb: float = Field(..., description="Total size in megabytes")
    avg_document_size_bytes: float = Field(..., description="Average document size in bytes")
