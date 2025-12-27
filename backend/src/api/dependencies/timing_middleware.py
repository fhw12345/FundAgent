"""
Request timing middleware for API performance profiling.

Logs P50/P95/P99 response times per endpoint for performance optimization.
Uses structlog for structured logging and stores timing data in memory
for real-time percentile calculation.
"""

import statistics
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = structlog.get_logger()


@dataclass
class EndpointMetrics:
    """Stores timing data for a single endpoint."""

    # Store last 1000 response times for percentile calculation
    response_times: list[float] = field(default_factory=list)
    max_samples: int = 1000

    def add_sample(self, response_time_ms: float) -> None:
        """Add a response time sample, keeping only recent samples."""
        self.response_times.append(response_time_ms)
        # Keep only the most recent samples to avoid memory growth
        if len(self.response_times) > self.max_samples:
            self.response_times = self.response_times[-self.max_samples :]

    def get_percentiles(self) -> dict[str, float | None]:
        """Calculate P50, P95, P99 percentiles."""
        if not self.response_times:
            return {"p50": None, "p95": None, "p99": None, "count": 0}

        sorted_times = sorted(self.response_times)
        count = len(sorted_times)

        return {
            "p50": self._percentile(sorted_times, 50),
            "p95": self._percentile(sorted_times, 95),
            "p99": self._percentile(sorted_times, 99),
            "count": count,
            "min": min(sorted_times),
            "max": max(sorted_times),
            "avg": statistics.mean(sorted_times),
        }

    @staticmethod
    def _percentile(sorted_data: list[float], percentile: int) -> float:
        """Calculate percentile from sorted data."""
        if not sorted_data:
            return 0.0
        index = (len(sorted_data) - 1) * percentile / 100
        lower = int(index)
        upper = lower + 1
        if upper >= len(sorted_data):
            return sorted_data[-1]
        weight = index - lower
        return sorted_data[lower] * (1 - weight) + sorted_data[upper] * weight


class TimingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that tracks request timing and calculates percentiles.

    Logs timing for each request and provides endpoint-level P50/P95/P99 metrics.
    """

    # Class-level metrics storage (shared across requests)
    metrics: dict[str, EndpointMetrics] = defaultdict(EndpointMetrics)

    def __init__(
        self,
        app: ASGIApp,
        log_all_requests: bool = False,
        slow_threshold_ms: float = 500.0,
    ) -> None:
        """
        Initialize timing middleware.

        Args:
            app: The FastAPI application
            log_all_requests: If True, log every request. If False, only log slow requests.
            slow_threshold_ms: Threshold in ms above which to always log the request.
        """
        super().__init__(app)
        self.log_all_requests = log_all_requests
        self.slow_threshold_ms = slow_threshold_ms

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process request and track timing."""
        start_time = time.perf_counter()

        # Process the request
        response = await call_next(request)

        # Calculate response time in milliseconds
        response_time_ms = (time.perf_counter() - start_time) * 1000

        # Create endpoint key (method + path pattern)
        endpoint_key = f"{request.method} {request.url.path}"

        # Store the timing
        self.metrics[endpoint_key].add_sample(response_time_ms)

        # Add timing header to response
        response.headers["X-Response-Time-Ms"] = f"{response_time_ms:.2f}"

        # Log based on configuration
        is_slow = response_time_ms > self.slow_threshold_ms
        if self.log_all_requests or is_slow:
            log_method = logger.warning if is_slow else logger.info
            log_method(
                "Request completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                response_time_ms=round(response_time_ms, 2),
                slow=is_slow,
            )

        return response

    @classmethod
    def get_all_metrics(cls) -> dict[str, dict[str, float | None]]:
        """Get percentile metrics for all endpoints."""
        return {
            endpoint: metrics.get_percentiles()
            for endpoint, metrics in cls.metrics.items()
        }

    @classmethod
    def get_endpoint_metrics(cls, endpoint: str) -> dict[str, float | None]:
        """Get percentile metrics for a specific endpoint."""
        if endpoint in cls.metrics:
            return cls.metrics[endpoint].get_percentiles()
        return {"p50": None, "p95": None, "p99": None, "count": 0}

    @classmethod
    def clear_metrics(cls) -> None:
        """Clear all stored metrics (useful for testing)."""
        cls.metrics.clear()
