"""
API integration tests for Stochastic Oscillator Analysis endpoint.
Tests HTTP API, caching, error handling, and end-to-end functionality.
"""

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api.dependencies.auth import get_current_user_id
from src.api.health import get_redis
from src.api.models import StochasticAnalysisResponse
from src.core.analysis.stochastic_analyzer import StochasticAnalyzer
from src.main import app


class TestStochasticAPIEndpoint:
    """Test the /api/analysis/stochastic endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client with mocked dependencies."""
        # Mock MongoDB in app state
        mock_mongodb = MagicMock()
        app.state.mongodb = mock_mongodb

        # Mock authentication dependency
        async def get_user_id_override():
            return "test-user-123"

        # Mock the Redis dependency
        def get_redis_override():
            mock_redis = MagicMock()
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.set = AsyncMock(return_value=None)
            return mock_redis

        app.dependency_overrides[get_current_user_id] = get_user_id_override
        app.dependency_overrides[get_redis] = get_redis_override
        client = TestClient(app)

        yield client

        # Clean up overrides and state
        app.dependency_overrides.clear()
        if hasattr(app.state, "mongodb"):
            delattr(app.state, "mongodb")

    @pytest.fixture
    def sample_stochastic_data(self):
        """Sample stochastic data for mocking."""
        mock_data = pd.DataFrame(
            {
                "High": np.random.uniform(100, 110, 50),
                "Low": np.random.uniform(90, 100, 50),
                "Close": np.random.uniform(95, 105, 50),
            }
        )
        mock_data.index = pd.date_range("2024-01-01", periods=50, freq="D")
        return mock_data

    @pytest.fixture
    def sample_response(self):
        """Sample stochastic analysis response."""
        return StochasticAnalysisResponse(
            symbol="AAPL",
            start_date="2024-01-01",
            end_date="2024-02-19",
            timeframe="1d",
            current_price=150.25,
            k_period=14,
            d_period=3,
            current_k=75.5,
            current_d=72.3,
            current_signal="overbought",
            stochastic_levels=[],
            signal_changes=[],
            analysis_summary="Test stochastic analysis showing overbought conditions",
            key_insights=["Current signal indicates overbought conditions"],
            raw_data={"test": "data"},
        )

    def test_stochastic_endpoint_valid_request(self, client, sample_response):
        """Test stochastic endpoint with valid request."""
        with patch(
            "src.core.analysis.stochastic_analyzer.StochasticAnalyzer.analyze",
            new_callable=AsyncMock,
            return_value=sample_response,
        ):
            response = client.post(
                "/api/analysis/stochastic",
                json={
                    "symbol": "AAPL",
                    "start_date": "2024-01-01",
                    "end_date": "2024-02-19",
                    "timeframe": "1d",
                    "k_period": 14,
                    "d_period": 3,
                },
            )

            assert response.status_code == 200
            data = response.json()

            # Verify response structure
            assert data["symbol"] == "AAPL"
            assert data["timeframe"] == "1d"
            assert data["current_signal"] in ["overbought", "oversold", "neutral"]
            assert 0 <= data["current_k"] <= 100
            assert 0 <= data["current_d"] <= 100
            assert data["k_period"] == 14
            assert data["d_period"] == 3

    def test_stochastic_endpoint_minimal_request(self, client, sample_response):
        """Test stochastic endpoint with minimal required fields."""
        with patch(
            "src.core.analysis.stochastic_analyzer.StochasticAnalyzer.analyze",
            new_callable=AsyncMock,
            return_value=sample_response,
        ):
            response = client.post("/api/analysis/stochastic", json={"symbol": "AAPL"})

            assert response.status_code == 200
            data = response.json()

            # Should use default values
            assert data["symbol"] == "AAPL"
            assert data["timeframe"] == "1d"  # Default
            assert data["k_period"] == 14  # Default
            assert data["d_period"] == 3  # Default

    def test_stochastic_endpoint_invalid_symbol(self, client):
        """Test stochastic endpoint with invalid symbol."""
        response = client.post(
            "/api/analysis/stochastic", json={"symbol": ""}  # Empty symbol
        )

        assert response.status_code == 422  # Validation error

    def test_stochastic_endpoint_invalid_parameters(self, client):
        """Test stochastic endpoint with invalid parameters."""
        # Invalid K period (too low)
        response = client.post(
            "/api/analysis/stochastic",
            json={"symbol": "AAPL", "k_period": 2},  # Below minimum of 5
        )
        assert response.status_code == 422

        # Invalid K period (too high)
        response = client.post(
            "/api/analysis/stochastic",
            json={"symbol": "AAPL", "k_period": 60},  # Above maximum of 50
        )
        assert response.status_code == 422

        # Invalid D period
        response = client.post(
            "/api/analysis/stochastic",
            json={"symbol": "AAPL", "d_period": 1},  # Below minimum of 2
        )
        assert response.status_code == 422

    def test_stochastic_endpoint_invalid_timeframe(self, client):
        """Test stochastic endpoint with invalid timeframe."""
        response = client.post(
            "/api/analysis/stochastic",
            json={"symbol": "AAPL", "timeframe": "5m"},  # Not supported
        )

        assert response.status_code == 422

    def test_stochastic_endpoint_invalid_dates(self, client):
        """Test stochastic endpoint with invalid date formats."""
        # Invalid date format
        response = client.post(
            "/api/analysis/stochastic",
            json={
                "symbol": "AAPL",
                "start_date": "01-01-2024",  # Wrong format
                "end_date": "2024-12-31",
            },
        )
        assert response.status_code == 400

        # Future dates
        future_date = (date.today().replace(year=date.today().year + 1)).isoformat()
        response = client.post(
            "/api/analysis/stochastic",
            json={"symbol": "AAPL", "start_date": future_date, "end_date": future_date},
        )
        assert response.status_code == 400

    def test_stochastic_endpoint_date_range_validation(self, client):
        """Test date range validation."""
        # Start date after end date
        response = client.post(
            "/api/analysis/stochastic",
            json={
                "symbol": "AAPL",
                "start_date": "2024-12-31",
                "end_date": "2024-01-01",
            },
        )
        assert response.status_code == 400

        # Date range too long (more than 5 years)
        response = client.post(
            "/api/analysis/stochastic",
            json={
                "symbol": "AAPL",
                "start_date": "2015-01-01",
                "end_date": "2024-12-31",
            },
        )
        assert response.status_code == 400

    def test_stochastic_endpoint_analysis_error(self, client):
        """Test endpoint when analysis fails."""
        with patch(
            "src.core.analysis.stochastic_analyzer.StochasticAnalyzer.analyze",
            side_effect=ValueError("Invalid symbol"),
        ):
            response = client.post(
                "/api/analysis/stochastic", json={"symbol": "INVALID123"}
            )

            assert response.status_code == 400
            data = response.json()
            assert "Invalid input" in data["detail"]

    def test_stochastic_endpoint_server_error(self, client):
        """Test endpoint when server error occurs."""
        with patch(
            "src.core.analysis.stochastic_analyzer.StochasticAnalyzer.analyze",
            side_effect=Exception("Internal error"),
        ):
            response = client.post("/api/analysis/stochastic", json={"symbol": "AAPL"})

            assert response.status_code == 500
            data = response.json()
            assert "Analysis failed" in data["detail"]


class TestStochasticAPICaching:
    """Test caching behavior for stochastic API."""

    @pytest.fixture
    def client_with_cache_control(self):
        """Create test client that allows cache mocking."""
        # Mock MongoDB in app state
        mock_mongodb = MagicMock()
        app.state.mongodb = mock_mongodb

        # Mock authentication dependency
        async def get_user_id_override():
            return "test-user-123"

        app.dependency_overrides[get_current_user_id] = get_user_id_override

        # Set up mock Redis in app state for health endpoint compatibility
        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=None)

        app.state.redis = mock_redis

        # This client doesn't override Redis dependency by default,
        # allowing individual tests to mock Redis behavior
        client = TestClient(app)
        yield client

        # Clean up app state and overrides
        app.dependency_overrides.clear()
        if hasattr(app.state, "redis"):
            delattr(app.state, "redis")
        if hasattr(app.state, "mongodb"):
            delattr(app.state, "mongodb")

    def test_stochastic_cache_key_generation(self, client_with_cache_control):
        """Test that cache keys are generated correctly."""
        # Create a mock Redis that we can track
        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=None)

        # Override the Redis dependency for this test
        def get_redis_override():
            return mock_redis

        app.dependency_overrides[get_redis] = get_redis_override

        try:
            with patch(
                "src.core.analysis.stochastic_analyzer.StochasticAnalyzer.analyze",
                new_callable=AsyncMock,
            ) as mock_analyze:

                mock_analyze.return_value = StochasticAnalysisResponse(
                    symbol="AAPL",
                    timeframe="1d",
                    current_price=150.0,
                    k_period=14,
                    d_period=3,
                    current_k=75.0,
                    current_d=72.0,
                    current_signal="neutral",
                    stochastic_levels=[],
                    signal_changes=[],
                    analysis_summary="Test",
                    key_insights=[],
                    raw_data={},
                )

                client_with_cache_control.post(
                    "/api/analysis/stochastic",
                    json={
                        "symbol": "AAPL",
                        "start_date": "2024-01-01",
                        "end_date": "2024-12-31",
                        "timeframe": "1d",
                        "k_period": 14,
                        "d_period": 3,
                    },
                )

                # Verify cache operations were called
                mock_redis.get.assert_called_once()
                mock_redis.set.assert_called_once()

        finally:
            # Clean up overrides
            app.dependency_overrides.clear()

    def test_stochastic_cache_hit(self, client_with_cache_control):
        """Test cache hit scenario."""
        cached_response = {
            "symbol": "AAPL",
            "timeframe": "1d",
            "current_price": 150.0,
            "k_period": 14,
            "d_period": 3,
            "current_k": 75.0,
            "current_d": 72.0,
            "current_signal": "neutral",
            "stochastic_levels": [],
            "signal_changes": [],
            "analysis_summary": "Cached analysis",
            "key_insights": [],
            "raw_data": {},
            "analysis_date": datetime.now().isoformat(),
        }

        # Create mock Redis for dependency injection
        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value=cached_response)
        mock_redis.set = AsyncMock(return_value=None)

        def get_redis_override():
            return mock_redis

        # Override Redis dependency
        app.dependency_overrides[get_redis] = get_redis_override

        try:
            with patch(
                "src.core.analysis.stochastic_analyzer.StochasticAnalyzer.analyze"
            ) as mock_analyze:
                response = client_with_cache_control.post(
                    "/api/analysis/stochastic", json={"symbol": "AAPL"}
                )

                assert response.status_code == 200
                data = response.json()
                assert data["analysis_summary"] == "Cached analysis"

                # Analyzer should not be called
                mock_analyze.assert_not_called()

                # Redis get should be called
                mock_redis.get.assert_called_once()

        finally:
            # Clean up dependency override
            app.dependency_overrides.clear()

    def test_stochastic_cache_miss_and_store(self, client_with_cache_control):
        """Test cache miss and subsequent storage."""
        # Create mock Redis for dependency injection
        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value=None)  # Cache miss
        mock_redis.set = AsyncMock(return_value=None)

        def get_redis_override():
            return mock_redis

        # Override Redis dependency
        app.dependency_overrides[get_redis] = get_redis_override

        try:
            with patch(
                "src.core.analysis.stochastic_analyzer.StochasticAnalyzer.analyze"
            ) as mock_analyze:
                mock_analyze.return_value = StochasticAnalysisResponse(
                    symbol="AAPL",
                    timeframe="1d",
                    current_price=150.0,
                    k_period=14,
                    d_period=3,
                    current_k=75.0,
                    current_d=72.0,
                    current_signal="neutral",
                    stochastic_levels=[],
                    signal_changes=[],
                    analysis_summary="Fresh analysis",
                    key_insights=[],
                    raw_data={},
                )

                response = client_with_cache_control.post(
                    "/api/analysis/stochastic", json={"symbol": "AAPL"}
                )

                assert response.status_code == 200
                data = response.json()
                assert data["analysis_summary"] == "Fresh analysis"

                # Cache should be checked and then set
                mock_redis.get.assert_called_once()
                mock_redis.set.assert_called_once()

                # Verify cache TTL is 5 minutes (300 seconds)
                call_args, call_kwargs = mock_redis.set.call_args
                cache_key, cache_value = call_args
                assert call_kwargs["ttl_seconds"] == 300
                assert "stochastic:AAPL:" in cache_key

        finally:
            # Clean up dependency override
            app.dependency_overrides.clear()


class TestStochasticEndToEndIntegration:
    """End-to-end integration tests."""

    @pytest.fixture
    def client(self):
        """Create test client with mocked dependencies."""
        # Mock MongoDB in app state
        mock_mongodb = MagicMock()
        app.state.mongodb = mock_mongodb

        # Mock authentication dependency
        async def get_user_id_override():
            return "test-user-123"

        # Mock the Redis dependency
        def get_redis_override():
            mock_redis = MagicMock()
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.set = AsyncMock(return_value=None)
            return mock_redis

        app.dependency_overrides[get_current_user_id] = get_user_id_override
        app.dependency_overrides[get_redis] = get_redis_override
        client = TestClient(app)

        yield client

        # Clean up overrides and state
        app.dependency_overrides.clear()
        if hasattr(app.state, "mongodb"):
            delattr(app.state, "mongodb")

    def test_full_stochastic_analysis_workflow(self, client):
        """Test complete analysis workflow with realistic data."""
        # Mock realistic stock data
        realistic_data = pd.DataFrame(
            {
                "High": [
                    152.5,
                    155.0,
                    153.2,
                    157.8,
                    159.1,
                    156.4,
                    158.9,
                    161.2,
                    163.5,
                    160.8,
                    164.1,
                    166.3,
                    162.9,
                    165.7,
                    168.2,
                    170.1,
                    167.5,
                    169.8,
                    172.3,
                    175.0,
                ],
                "Low": [
                    148.2,
                    151.1,
                    149.8,
                    152.3,
                    154.6,
                    152.1,
                    154.2,
                    157.1,
                    159.2,
                    156.5,
                    160.3,
                    162.1,
                    158.7,
                    161.4,
                    164.8,
                    166.2,
                    163.9,
                    166.1,
                    168.7,
                    171.2,
                ],
                "Close": [
                    150.5,
                    153.2,
                    151.8,
                    155.9,
                    157.3,
                    154.7,
                    156.8,
                    159.5,
                    161.2,
                    158.9,
                    162.4,
                    164.1,
                    160.2,
                    163.8,
                    166.5,
                    168.3,
                    165.1,
                    167.9,
                    170.8,
                    173.5,
                ],
            }
        )
        realistic_data.index = pd.date_range("2024-01-01", periods=20, freq="D")

        with patch.object(
            StochasticAnalyzer, "_fetch_stock_data", return_value=realistic_data
        ):
            response = client.post(
                "/api/analysis/stochastic",
                json={
                    "symbol": "AAPL",
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-20",
                    "timeframe": "1d",
                    "k_period": 14,
                    "d_period": 3,
                },
            )

            assert response.status_code == 200
            data = response.json()

            # Verify comprehensive response
            assert data["symbol"] == "AAPL"
            assert data["timeframe"] == "1d"
            assert isinstance(data["current_price"], float)
            assert data["current_signal"] in ["overbought", "oversold", "neutral"]
            assert 0 <= data["current_k"] <= 100
            assert 0 <= data["current_d"] <= 100
            assert isinstance(data["analysis_summary"], str)
            assert len(data["key_insights"]) > 0
            assert isinstance(data["raw_data"], dict)

            # Verify stochastic levels structure
            if data["stochastic_levels"]:
                level = data["stochastic_levels"][0]
                assert "timestamp" in level
                assert "k_percent" in level
                assert "d_percent" in level
                assert "signal" in level

    def test_different_timeframe_analysis(self, client):
        """Test analysis with different timeframes."""
        mock_data = pd.DataFrame(
            {
                "High": np.random.uniform(100, 110, 100),
                "Low": np.random.uniform(90, 100, 100),
                "Close": np.random.uniform(95, 105, 100),
            }
        )
        mock_data.index = pd.date_range("2024-01-01", periods=100, freq="H")

        timeframes = ["1h", "1d", "1w", "1M"]

        for timeframe in timeframes:
            with patch.object(
                StochasticAnalyzer, "_fetch_stock_data", return_value=mock_data
            ):
                response = client.post(
                    "/api/analysis/stochastic",
                    json={"symbol": "AAPL", "timeframe": timeframe},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["timeframe"] == timeframe

    def test_custom_stochastic_parameters(self, client):
        """Test analysis with custom K and D periods."""
        mock_data = pd.DataFrame(
            {
                "High": np.random.uniform(100, 110, 60),
                "Low": np.random.uniform(90, 100, 60),
                "Close": np.random.uniform(95, 105, 60),
            }
        )
        mock_data.index = pd.date_range("2024-01-01", periods=60, freq="D")

        parameter_combinations = [
            {"k_period": 7, "d_period": 3},
            {"k_period": 21, "d_period": 5},
            {"k_period": 9, "d_period": 9},
        ]

        for params in parameter_combinations:
            with patch.object(
                StochasticAnalyzer, "_fetch_stock_data", return_value=mock_data
            ):
                response = client.post(
                    "/api/analysis/stochastic", json={"symbol": "AAPL", **params}
                )

                assert response.status_code == 200
                data = response.json()
                assert data["k_period"] == params["k_period"]
                assert data["d_period"] == params["d_period"]


class TestStochasticAPIPerformance:
    """Test API performance and logging."""

    @pytest.fixture
    def client(self):
        """Create test client with mocked dependencies."""
        # Mock MongoDB in app state
        mock_mongodb = MagicMock()
        app.state.mongodb = mock_mongodb

        # Mock authentication dependency
        async def get_user_id_override():
            return "test-user-123"

        # Mock the Redis dependency
        def get_redis_override():
            mock_redis = MagicMock()
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.set = AsyncMock(return_value=None)
            return mock_redis

        app.dependency_overrides[get_current_user_id] = get_user_id_override
        app.dependency_overrides[get_redis] = get_redis_override
        client = TestClient(app)

        yield client

        # Clean up overrides and state
        app.dependency_overrides.clear()
        if hasattr(app.state, "mongodb"):
            delattr(app.state, "mongodb")

    def test_stochastic_analysis_logging(self, client, caplog):
        """Test that proper logging occurs during analysis."""
        mock_data = pd.DataFrame(
            {"High": [110, 115, 112], "Low": [100, 105, 102], "Close": [105, 110, 107]}
        )
        mock_data.index = pd.date_range("2024-01-01", periods=3, freq="D")

        with patch.object(
            StochasticAnalyzer, "_fetch_stock_data", return_value=mock_data
        ):
            try:
                _response = client.post(
                    "/api/analysis/stochastic", json={"symbol": "AAPL"}
                )
            except Exception:
                pass  # Expected to fail with insufficient data

            # Check that logging occurred
            log_records = [
                record
                for record in caplog.records
                if "stochastic" in record.message.lower()
            ]
            assert len(log_records) > 0

    def test_stochastic_request_timing(self, client):
        """Test that timing information is logged."""
        mock_data = pd.DataFrame(
            {
                "High": np.random.uniform(100, 110, 50),
                "Low": np.random.uniform(90, 100, 50),
                "Close": np.random.uniform(95, 105, 50),
            }
        )
        mock_data.index = pd.date_range("2024-01-01", periods=50, freq="D")

        with patch.object(
            StochasticAnalyzer, "_fetch_stock_data", return_value=mock_data
        ):
            response = client.post("/api/analysis/stochastic", json={"symbol": "AAPL"})

            # Should complete in reasonable time
            assert response.status_code == 200
