"""
Tests for request timing middleware.

Validates P50/P95/P99 percentile calculation and request timing functionality.
"""

import pytest

from src.api.dependencies.timing_middleware import EndpointMetrics, TimingMiddleware


class TestEndpointMetrics:
    """Test suite for EndpointMetrics class."""

    def test_add_sample_stores_value(self):
        """Test that add_sample stores response times."""
        metrics = EndpointMetrics()
        metrics.add_sample(100.0)
        metrics.add_sample(200.0)

        assert len(metrics.response_times) == 2
        assert 100.0 in metrics.response_times
        assert 200.0 in metrics.response_times

    def test_add_sample_trims_to_max(self):
        """Test that samples are trimmed to max_samples."""
        metrics = EndpointMetrics(max_samples=10)

        # Add more than max samples
        for i in range(15):
            metrics.add_sample(float(i))

        # Should only keep the last 10
        assert len(metrics.response_times) == 10
        # Should keep the most recent ones (5-14)
        assert metrics.response_times == [float(i) for i in range(5, 15)]

    def test_get_percentiles_empty(self):
        """Test percentiles with no data returns None values."""
        metrics = EndpointMetrics()
        result = metrics.get_percentiles()

        assert result["p50"] is None
        assert result["p95"] is None
        assert result["p99"] is None
        assert result["count"] == 0

    def test_get_percentiles_single_value(self):
        """Test percentiles with single value."""
        metrics = EndpointMetrics()
        metrics.add_sample(100.0)
        result = metrics.get_percentiles()

        assert result["p50"] == 100.0
        assert result["p95"] == 100.0
        assert result["p99"] == 100.0
        assert result["count"] == 1

    def test_get_percentiles_multiple_values(self):
        """Test percentiles with multiple values."""
        metrics = EndpointMetrics()
        # Add 100 samples: 1, 2, 3, ..., 100
        for i in range(1, 101):
            metrics.add_sample(float(i))

        result = metrics.get_percentiles()

        # P50 should be around 50
        assert 49 <= result["p50"] <= 51
        # P95 should be around 95
        assert 94 <= result["p95"] <= 96
        # P99 should be around 99
        assert 98 <= result["p99"] <= 100
        assert result["count"] == 100
        assert result["min"] == 1.0
        assert result["max"] == 100.0
        assert 49 <= result["avg"] <= 51  # Average should be ~50.5

    def test_percentile_calculation_accuracy(self):
        """Test exact percentile calculation."""
        metrics = EndpointMetrics()
        # Known values for easy verification
        values = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        for v in values:
            metrics.add_sample(v)

        result = metrics.get_percentiles()

        # With 10 values, P50 should be around 55 (between 50 and 60)
        assert 50 <= result["p50"] <= 60
        assert result["min"] == 10.0
        assert result["max"] == 100.0


class TestTimingMiddleware:
    """Test suite for TimingMiddleware class."""

    def setup_method(self):
        """Clear metrics before each test."""
        TimingMiddleware.clear_metrics()

    def test_clear_metrics(self):
        """Test that clear_metrics removes all stored data."""
        # Add some data
        TimingMiddleware.metrics["test_endpoint"].add_sample(100.0)
        assert "test_endpoint" in TimingMiddleware.metrics

        # Clear
        TimingMiddleware.clear_metrics()

        # Verify cleared
        assert len(TimingMiddleware.metrics) == 0

    def test_get_all_metrics_empty(self):
        """Test get_all_metrics with no data."""
        result = TimingMiddleware.get_all_metrics()
        assert result == {}

    def test_get_all_metrics_with_data(self):
        """Test get_all_metrics returns all endpoint data."""
        TimingMiddleware.metrics["GET /api/health"].add_sample(50.0)
        TimingMiddleware.metrics["POST /api/chat"].add_sample(200.0)

        result = TimingMiddleware.get_all_metrics()

        assert "GET /api/health" in result
        assert "POST /api/chat" in result
        assert result["GET /api/health"]["count"] == 1
        assert result["POST /api/chat"]["count"] == 1

    def test_get_endpoint_metrics_exists(self):
        """Test get_endpoint_metrics for existing endpoint."""
        TimingMiddleware.metrics["GET /api/test"].add_sample(100.0)
        TimingMiddleware.metrics["GET /api/test"].add_sample(200.0)

        result = TimingMiddleware.get_endpoint_metrics("GET /api/test")

        assert result["count"] == 2
        assert result["p50"] is not None

    def test_get_endpoint_metrics_not_exists(self):
        """Test get_endpoint_metrics for non-existent endpoint."""
        result = TimingMiddleware.get_endpoint_metrics("GET /api/nonexistent")

        assert result["p50"] is None
        assert result["p95"] is None
        assert result["p99"] is None
        assert result["count"] == 0


class TestTimingMiddlewareIntegration:
    """Integration tests for timing middleware with FastAPI."""

    def setup_method(self):
        """Clear metrics before each test."""
        TimingMiddleware.clear_metrics()

    @pytest.mark.asyncio
    async def test_middleware_records_timing(self):
        """Test that middleware records request timing."""
        from unittest.mock import AsyncMock, MagicMock

        # Create mock request and response
        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/api/test"

        mock_response = MagicMock()
        mock_response.headers = {}
        mock_response.status_code = 200

        # Create async call_next that returns response
        async def mock_call_next(request: MagicMock) -> MagicMock:
            return mock_response

        # Create middleware instance (app is ASGIApp type)
        async def mock_app(scope: dict, receive: AsyncMock, send: AsyncMock) -> None:
            pass

        middleware = TimingMiddleware(
            mock_app, log_all_requests=True, slow_threshold_ms=1000.0
        )

        # Call dispatch
        result = await middleware.dispatch(mock_request, mock_call_next)

        # Verify response was returned
        assert result == mock_response

        # Verify timing was recorded
        assert "GET /api/test" in TimingMiddleware.metrics
        assert TimingMiddleware.metrics["GET /api/test"].response_times

        # Verify header was added
        assert "X-Response-Time-Ms" in mock_response.headers
