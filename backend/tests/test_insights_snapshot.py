"""Unit tests for InsightsSnapshotService.

Tests the daily snapshot creation workflow including:
- Pre-fetch shared data via DML
- Metric calculation
- MongoDB persistence
- Redis cache update
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.data_manager import SharedDataContext
from src.services.insights.models import (
    CompositeScore,
    InsightCategory,
    InsightMetric,
    MetricExplanation,
    MetricStatus,
)
from src.services.insights.snapshot_service import (
    SNAPSHOT_REDIS_TTL,
    SNAPSHOTS_COLLECTION,
    InsightsSnapshotService,
)


@pytest.fixture
def mock_mongodb():
    """Create a mock MongoDB instance."""
    mock = MagicMock()
    mock_collection = AsyncMock()
    mock.get_collection.return_value = mock_collection
    return mock


@pytest.fixture
def mock_redis_cache():
    """Create a mock Redis cache."""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock()
    return mock


@pytest.fixture
def mock_data_manager():
    """Create a mock DataManager."""
    mock = AsyncMock()

    # Mock prefetch_shared to return a SharedDataContext
    shared_context = SharedDataContext(
        ohlcv={"NVDA": [], "MSFT": [], "AMD": [], "PLTR": []},
        treasury={"2y": [], "10y": []},
        news=[],
        ipo=[],
    )
    mock.prefetch_shared = AsyncMock(return_value=shared_context)
    return mock


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    mock = MagicMock()
    mock.alpha_vantage_api_key = "test-key"
    return mock


@pytest.fixture
def mock_registry():
    """Create a mock insights registry."""
    mock = MagicMock()

    # Create proper MetricExplanation object
    explanation = MetricExplanation(
        summary="Test summary",
        detail="Test detail for the metric.",
        methodology="Test methodology description.",
        historical_context="Test historical context.",
        actionable_insight="Test actionable insight.",
    )

    # Create metrics list
    metrics = [
        InsightMetric(
            id="ai_price_anomaly",
            name="AI Price Anomaly",
            score=85.0,
            status=MetricStatus.HIGH,
            explanation=explanation,
            data_sources=["TIME_SERIES_DAILY"],
            last_updated=datetime.now(UTC),
        ),
        InsightMetric(
            id="news_sentiment",
            name="News Sentiment",
            score=65.0,
            status=MetricStatus.ELEVATED,
            explanation=explanation,
            data_sources=["NEWS_SENTIMENT"],
            last_updated=datetime.now(UTC),
        ),
    ]

    # Create composite score
    composite = CompositeScore(
        score=72.5,
        status=MetricStatus.ELEVATED,
        weights={"ai_price_anomaly": 0.2, "news_sentiment": 0.2},
        breakdown={"ai_price_anomaly": 17.0, "news_sentiment": 13.0},
        interpretation="Elevated risk",
    )

    # Create InsightCategory data returned by get_category_data
    category_data = InsightCategory(
        id="ai_sector_risk",
        name="AI Sector Risk",
        icon="🤖",
        description="AI sector risk analysis",
        metrics=metrics,
        composite=composite,
        last_updated=datetime.now(UTC),
    )

    # Create mock category instance
    mock_category = AsyncMock()
    mock_category.get_category_data = AsyncMock(return_value=category_data)

    # Mock get_category_instance (not get_category)
    mock.get_category_instance.return_value = mock_category
    return mock


@pytest.fixture
def snapshot_service(
    mock_mongodb, mock_redis_cache, mock_data_manager, mock_settings, mock_registry
):
    """Create snapshot service with mocked dependencies."""
    return InsightsSnapshotService(
        mongodb=mock_mongodb,
        redis_cache=mock_redis_cache,
        data_manager=mock_data_manager,
        settings=mock_settings,
        registry=mock_registry,
    )


class TestInsightsSnapshotService:
    """Tests for InsightsSnapshotService."""

    @pytest.mark.asyncio
    async def test_ensure_indexes(self, snapshot_service, mock_mongodb):
        """Test that ensure_indexes creates the compound index."""
        await snapshot_service.ensure_indexes()

        mock_mongodb.get_collection.assert_called_with(SNAPSHOTS_COLLECTION)
        mock_collection = mock_mongodb.get_collection.return_value
        mock_collection.create_index.assert_called_once()

        # Verify index parameters
        call_args = mock_collection.create_index.call_args
        index_spec = call_args[0][0]
        assert index_spec == [("category_id", 1), ("date", -1)]
        assert call_args[1]["name"] == "category_date_idx"
        assert call_args[1]["unique"] is True

    @pytest.mark.asyncio
    async def test_create_snapshot_uses_dml_prefetch(
        self, snapshot_service, mock_data_manager
    ):
        """Verify snapshot service uses DataManager.prefetch_shared()."""
        await snapshot_service.create_snapshot(category_id="ai_sector_risk")

        mock_data_manager.prefetch_shared.assert_called_once()
        call_kwargs = mock_data_manager.prefetch_shared.call_args[1]
        assert "symbols" in call_kwargs
        assert "indicators" in call_kwargs
        assert call_kwargs["include_news"] is True
        assert call_kwargs["include_ipo"] is True

    @pytest.mark.asyncio
    async def test_create_snapshot_calculates_all_metrics(
        self, snapshot_service, mock_registry
    ):
        """All metrics should be calculated via get_category_data."""
        await snapshot_service.create_snapshot(category_id="ai_sector_risk")

        mock_category = mock_registry.get_category_instance.return_value
        mock_category.get_category_data.assert_called_once_with(force_refresh=True)

    @pytest.mark.asyncio
    async def test_create_snapshot_saves_to_mongodb(
        self, snapshot_service, mock_mongodb
    ):
        """Snapshot should be saved with correct schema."""
        await snapshot_service.create_snapshot(category_id="ai_sector_risk")

        mock_collection = mock_mongodb.get_collection.return_value
        mock_collection.update_one.assert_called_once()

        # Verify upsert parameters
        call_args = mock_collection.update_one.call_args
        filter_doc = call_args[0][0]
        update_doc = call_args[0][1]

        assert filter_doc["category_id"] == "ai_sector_risk"
        assert "date" in filter_doc
        assert "$set" in update_doc
        assert update_doc["$set"]["composite_score"] == 72.5
        assert update_doc["$set"]["composite_status"] == "elevated"
        assert "metrics" in update_doc["$set"]
        assert call_args[1]["upsert"] is True

    @pytest.mark.asyncio
    async def test_create_snapshot_updates_redis(
        self, snapshot_service, mock_redis_cache
    ):
        """Redis key should be updated with 24hr TTL."""
        await snapshot_service.create_snapshot(category_id="ai_sector_risk")

        mock_redis_cache.set.assert_called_once()

        # Verify cache key and TTL
        call_args = mock_redis_cache.set.call_args
        cache_key = call_args[0][0]
        cache_doc = call_args[0][1]
        ttl = call_args[1]["ttl_seconds"]  # Parameter name is ttl_seconds

        assert cache_key == "insights:ai_sector_risk:latest"
        assert cache_doc["composite_score"] == 72.5
        assert ttl == SNAPSHOT_REDIS_TTL

    @pytest.mark.asyncio
    async def test_create_snapshot_returns_timing(self, snapshot_service):
        """Snapshot result should include timing information."""
        result = await snapshot_service.create_snapshot(category_id="ai_sector_risk")

        assert result["status"] == "success"
        assert "timing" in result
        assert "phase1_prefetch_seconds" in result["timing"]
        assert "phase2_calculate_seconds" in result["timing"]
        assert "phase3_persist_seconds" in result["timing"]
        assert "total_seconds" in result["timing"]

    @pytest.mark.asyncio
    async def test_create_snapshot_handles_partial_failure(
        self, snapshot_service, mock_data_manager
    ):
        """Should continue with available data if some API calls fail."""
        # Simulate partial failure in prefetch
        mock_data_manager.prefetch_shared = AsyncMock(
            side_effect=Exception("API timeout")
        )

        # Should still return a result - the service catches prefetch errors
        # and continues with available data (graceful degradation)
        result = await snapshot_service.create_snapshot(category_id="ai_sector_risk")

        # The service should continue even if prefetch fails
        # This tests graceful degradation behavior
        assert result["status"] == "success"
        assert "timing" in result

    @pytest.mark.asyncio
    async def test_get_latest_snapshot_from_cache(
        self, snapshot_service, mock_redis_cache
    ):
        """Should return cached snapshot if available."""
        cached_doc = {
            "category_id": "ai_sector_risk",
            "composite_score": 72.5,
            "date": "2025-12-28T00:00:00+00:00",
        }
        mock_redis_cache.get = AsyncMock(return_value=cached_doc)

        result = await snapshot_service.get_latest_snapshot("ai_sector_risk")

        assert result == cached_doc
        mock_redis_cache.get.assert_called_with("insights:ai_sector_risk:latest")

    @pytest.mark.asyncio
    async def test_get_latest_snapshot_fallback_to_mongodb(
        self, snapshot_service, mock_redis_cache, mock_mongodb
    ):
        """Should fall back to MongoDB if cache miss."""
        mock_redis_cache.get = AsyncMock(return_value=None)

        mongo_doc = {
            "_id": "test-id",
            "category_id": "ai_sector_risk",
            "composite_score": 72.5,
            "date": datetime.now(UTC),
        }
        mock_collection = mock_mongodb.get_collection.return_value
        mock_collection.find_one = AsyncMock(return_value=mongo_doc)

        result = await snapshot_service.get_latest_snapshot("ai_sector_risk")

        assert result is not None
        assert "_id" not in result  # Should remove MongoDB _id
        assert result["composite_score"] == 72.5

    @pytest.mark.asyncio
    async def test_get_trend_returns_ordered_snapshots(
        self, snapshot_service, mock_mongodb
    ):
        """Trend should return snapshots ordered by date descending."""
        mock_docs = [
            {"date": datetime(2025, 12, 28, tzinfo=UTC), "composite_score": 72.5},
            {"date": datetime(2025, 12, 27, tzinfo=UTC), "composite_score": 70.0},
        ]

        # Create an async iterator for the cursor
        class AsyncCursorIterator:
            def __init__(self, docs):
                self.docs = docs
                self.index = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.index >= len(self.docs):
                    raise StopAsyncIteration
                doc = self.docs[self.index]
                self.index += 1
                return doc

        # Set up the mock properly - use a regular Mock for find()
        # since it returns a cursor (not async), then the cursor is iterated
        mock_collection = MagicMock()
        mock_collection.find.return_value = AsyncCursorIterator(mock_docs)
        mock_mongodb.get_collection.return_value = mock_collection

        result = await snapshot_service.get_trend("ai_sector_risk", days=30)

        assert len(result) == 2
        mock_collection.find.assert_called_once()


class TestSnapshotServiceConstants:
    """Tests for service constants."""

    def test_collection_name(self):
        """Collection name should be insight_snapshots."""
        assert SNAPSHOTS_COLLECTION == "insight_snapshots"

    def test_redis_ttl(self):
        """Redis TTL should be 24 hours."""
        assert SNAPSHOT_REDIS_TTL == 86400
