"""
Admin-only API models for system monitoring and health checks.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class DatabaseStats(BaseModel):
    """Statistics for a single MongoDB collection."""

    collection: str = Field(..., description="Collection name")
    document_count: int = Field(..., description="Number of documents")
    size_bytes: int = Field(..., description="Collection size in bytes")
    size_mb: float = Field(..., description="Collection size in megabytes")
    avg_document_size_bytes: int = Field(..., description="Average document size")


class PodMetrics(BaseModel):
    """Kubernetes pod resource usage metrics."""

    name: str = Field(..., description="Pod name")
    cpu_usage: str = Field(..., description="CPU usage (e.g., '150m')")
    memory_usage: str = Field(..., description="Memory usage (e.g., '256Mi')")
    cpu_percentage: float = Field(..., description="CPU usage as percentage of request")
    memory_percentage: float = Field(
        ..., description="Memory usage as percentage of request"
    )
    node_name: str | None = Field(None, description="Node where pod is running")
    node_pool: str | None = Field(None, description="Node pool name")
    cpu_request: str | None = Field(None, description="CPU request (e.g., '100m')")
    cpu_limit: str | None = Field(None, description="CPU limit (e.g., '1')")
    memory_request: str | None = Field(
        None, description="Memory request (e.g., '256Mi')"
    )
    memory_limit: str | None = Field(None, description="Memory limit (e.g., '512Mi')")


class NodeMetrics(BaseModel):
    """Kubernetes node resource usage metrics."""

    name: str = Field(..., description="Node name")
    cpu_usage: str = Field(..., description="CPU usage")
    memory_usage: str = Field(..., description="Memory usage")
    cpu_capacity: str = Field(..., description="Total CPU capacity")
    memory_capacity: str = Field(..., description="Total memory capacity")
    cpu_percentage: float = Field(
        ..., description="CPU usage as percentage of capacity"
    )
    memory_percentage: float = Field(
        ..., description="Memory usage as percentage of capacity"
    )


class SystemMetrics(BaseModel):
    """Complete system health metrics for admin dashboard."""

    timestamp: datetime = Field(..., description="Metrics collection timestamp")
    database: list[DatabaseStats] = Field(
        ..., description="Database collection statistics"
    )
    pods: list[PodMetrics] | None = Field(
        None, description="Pod metrics (None if Kubernetes unavailable)"
    )
    nodes: list[NodeMetrics] | None = Field(
        None, description="Node metrics (None if Kubernetes unavailable)"
    )
    health_status: str = Field(
        ...,
        description="Overall health status",
        pattern="^(healthy|warning|critical|degraded)$",
    )
    kubernetes_available: bool = Field(
        ..., description="Whether Kubernetes metrics are available"
    )


class HealthResponse(SystemMetrics):
    """Admin health endpoint response (alias for SystemMetrics)."""

    pass
