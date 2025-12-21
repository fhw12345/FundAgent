"""Pydantic models for Market Insights API responses."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MetricExplanationResponse(BaseModel):
    """Explanation for a metric."""

    summary: str = Field(..., description="One-liner summary")
    detail: str = Field(..., description="Detailed explanation")
    methodology: str = Field(..., description="How the metric is calculated")
    formula: str | None = Field(default=None, description="Mathematical formula")
    historical_context: str = Field(..., description="Historical comparison")
    actionable_insight: str = Field(..., description="What to do based on this")


class InsightMetricResponse(BaseModel):
    """Response model for a single metric."""

    id: str = Field(..., description="Metric identifier")
    name: str = Field(..., description="Display name")
    score: float = Field(..., description="Score 0-100 (or -1 for error)")
    status: str = Field(..., description="Status: low, normal, elevated, high")
    explanation: MetricExplanationResponse = Field(..., description="Rich explanation")
    data_sources: list[str] = Field(..., description="Alpha Vantage endpoints used")
    last_updated: datetime = Field(..., description="When calculated")
    raw_data: dict[str, Any] = Field(..., description="Raw calculation data")


class CompositeScoreResponse(BaseModel):
    """Response model for composite score."""

    score: float = Field(..., ge=0, le=100, description="Weighted composite score")
    status: str = Field(..., description="Overall status")
    weights: dict[str, float] = Field(..., description="Weight per metric")
    breakdown: dict[str, float] = Field(
        ..., description="Score contribution per metric"
    )
    interpretation: str = Field(..., description="Human-readable interpretation")


class CategoryMetadataResponse(BaseModel):
    """Lightweight category info for listing."""

    id: str = Field(..., description="Category identifier")
    name: str = Field(..., description="Display name")
    icon: str = Field(..., description="Emoji icon")
    description: str = Field(..., description="Category purpose")
    metric_count: int = Field(..., description="Number of metrics")
    last_updated: datetime | None = Field(default=None, description="Last calculation")


class InsightCategoryResponse(BaseModel):
    """Complete category response with all metrics."""

    id: str = Field(..., description="Category identifier")
    name: str = Field(..., description="Display name")
    icon: str = Field(..., description="Emoji icon")
    description: str = Field(..., description="Category purpose")
    metrics: list[InsightMetricResponse] = Field(..., description="All metrics")
    composite: CompositeScoreResponse | None = Field(
        default=None, description="Weighted composite score"
    )
    last_updated: datetime = Field(..., description="Last calculation time")


class CategoriesListResponse(BaseModel):
    """Response model for category listing."""

    categories: list[CategoryMetadataResponse] = Field(
        ..., description="Available categories"
    )
    count: int = Field(..., description="Total category count")


class RefreshResponse(BaseModel):
    """Response model for refresh operation."""

    success: bool = Field(..., description="Whether refresh succeeded")
    category_id: str = Field(..., description="Category that was refreshed")
    message: str = Field(..., description="Status message")
    last_updated: datetime = Field(..., description="New last_updated timestamp")
