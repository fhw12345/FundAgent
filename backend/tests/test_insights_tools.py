"""Tests for Market Insights LangChain tools.

Tests cover:
- list_insight_categories tool
- get_insight_category tool
- get_insight_metric tool
- Error handling for each tool
- Edge cases (empty registry, missing categories/metrics)
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agent.tools.insights_tools import (
    _format_cached_insight,
    _format_trend_response,
    _get_status_emoji,
    _get_trend_direction,
    create_insights_tools,
)
from src.services.insights import InsightsCategoryRegistry
from src.services.insights.models import (
    CategoryMetadata,
    CompositeScore,
    InsightCategory,
    InsightMetric,
    MetricExplanation,
    MetricStatus,
)


@pytest.fixture
def mock_registry() -> MagicMock:
    """Create mock registry for testing."""
    return MagicMock(spec=InsightsCategoryRegistry)


@pytest.fixture
def sample_categories() -> list[CategoryMetadata]:
    """Create sample category metadata."""
    return [
        CategoryMetadata(
            id="ai_sector_risk",
            name="AI Sector Risk",
            icon="🎯",
            description="Measures bubble risk in AI sector",
            metric_count=6,
            last_updated=datetime.now(timezone.utc),
        ),
        CategoryMetadata(
            id="crypto_sentiment",
            name="Crypto Sentiment",
            icon="💎",
            description="Analyzes crypto market sentiment",
            metric_count=4,
            last_updated=datetime.now(timezone.utc),
        ),
    ]


@pytest.fixture
def sample_category_data() -> InsightCategory:
    """Create sample category data with metrics."""
    return InsightCategory(
        id="ai_sector_risk",
        name="AI Sector Risk",
        icon="🎯",
        description="Measures bubble risk",
        metrics=[
            InsightMetric(
                id="ai_price_anomaly",
                name="AI Price Anomaly",
                score=65.0,
                status=MetricStatus.ELEVATED,
                explanation=MetricExplanation(
                    summary="Prices 15% above average",
                    detail="Analysis shows elevated valuations",
                    methodology="Z-score calculation",
                    formula="(current_price - avg_price) / std_dev",
                    historical_context="Higher than 6-month average",
                    actionable_insight="Consider reducing exposure",
                ),
                data_sources=["Alpha Vantage", "Yahoo Finance"],
                last_updated=datetime.now(timezone.utc),
            ),
            InsightMetric(
                id="news_sentiment",
                name="News Sentiment",
                score=42.0,
                status=MetricStatus.NORMAL,
                explanation=MetricExplanation(
                    summary="Neutral sentiment in news",
                    detail="Mixed coverage",
                    methodology="NLP sentiment analysis",
                    historical_context="Consistent with recent weeks",
                    actionable_insight="Monitor for changes",
                ),
                data_sources=["Alpha Vantage News"],
                last_updated=datetime.now(timezone.utc),
            ),
        ],
        composite=CompositeScore(
            score=55.0,
            status=MetricStatus.ELEVATED,
            weights={"ai_price_anomaly": 0.6, "news_sentiment": 0.4},
            breakdown={"ai_price_anomaly": 39.0, "news_sentiment": 16.8},
            interpretation="Elevated risk - monitor positions",
        ),
        last_updated=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_metric() -> InsightMetric:
    """Create sample metric for testing."""
    return InsightMetric(
        id="ai_price_anomaly",
        name="AI Price Anomaly",
        score=65.0,
        status=MetricStatus.ELEVATED,
        explanation=MetricExplanation(
            summary="Prices 15% above average",
            detail="Detailed analysis here",
            methodology="Z-score method",
            formula="z = (x - mu) / sigma",
            historical_context="Higher than usual",
            actionable_insight="Consider reducing exposure",
        ),
        data_sources=["Alpha Vantage"],
        last_updated=datetime.now(timezone.utc),
    )


class TestListInsightCategories:
    """Tests for list_insight_categories tool."""

    @pytest.mark.asyncio
    async def test_list_categories_success(
        self, mock_registry: MagicMock, sample_categories: list[CategoryMetadata]
    ) -> None:
        """Test successful category listing."""
        mock_registry.list_categories.return_value = sample_categories
        tools = create_insights_tools(mock_registry)
        list_tool = tools[0]

        result = await list_tool.ainvoke({})

        assert "AI Sector Risk" in result
        assert "Crypto Sentiment" in result
        assert "ai_sector_risk" in result
        assert "crypto_sentiment" in result
        assert "🎯" in result
        assert "💎" in result

    @pytest.mark.asyncio
    async def test_list_categories_empty(self, mock_registry: MagicMock) -> None:
        """Test listing when no categories exist."""
        mock_registry.list_categories.return_value = []
        tools = create_insights_tools(mock_registry)
        list_tool = tools[0]

        result = await list_tool.ainvoke({})

        assert "no insight categories" in result.lower()

    @pytest.mark.asyncio
    async def test_list_categories_error(self, mock_registry: MagicMock) -> None:
        """Test error handling in list categories."""
        mock_registry.list_categories.side_effect = Exception("Database error")
        tools = create_insights_tools(mock_registry)
        list_tool = tools[0]

        result = await list_tool.ainvoke({})

        assert "error" in result.lower()
        assert "Database error" in result


class TestGetInsightCategory:
    """Tests for get_insight_category tool."""

    @pytest.mark.asyncio
    async def test_get_category_success(
        self,
        mock_registry: MagicMock,
        sample_categories: list[CategoryMetadata],
        sample_category_data: InsightCategory,
    ) -> None:
        """Test successful category retrieval."""
        mock_registry.get_category_data = AsyncMock(return_value=sample_category_data)
        tools = create_insights_tools(mock_registry)
        get_category_tool = tools[1]

        result = await get_category_tool.ainvoke({"category_id": "ai_sector_risk"})

        assert "AI Sector Risk" in result
        assert "55/100" in result  # Composite score
        assert "AI Price Anomaly" in result
        assert "ELEVATED" in result

    @pytest.mark.asyncio
    async def test_get_category_not_found(
        self, mock_registry: MagicMock, sample_categories: list[CategoryMetadata]
    ) -> None:
        """Test 404 when category doesn't exist."""
        mock_registry.get_category_data = AsyncMock(return_value=None)
        mock_registry.list_categories.return_value = sample_categories
        tools = create_insights_tools(mock_registry)
        get_category_tool = tools[1]

        result = await get_category_tool.ainvoke({"category_id": "nonexistent"})

        assert "not found" in result.lower()
        assert "ai_sector_risk" in result  # Suggests available categories

    @pytest.mark.asyncio
    async def test_get_category_error(self, mock_registry: MagicMock) -> None:
        """Test error handling."""
        mock_registry.get_category_data = AsyncMock(
            side_effect=Exception("API timeout")
        )
        tools = create_insights_tools(mock_registry)
        get_category_tool = tools[1]

        result = await get_category_tool.ainvoke({"category_id": "ai_sector_risk"})

        assert "error" in result.lower()


class TestGetInsightMetric:
    """Tests for get_insight_metric tool."""

    @pytest.mark.asyncio
    async def test_get_metric_success(
        self, mock_registry: MagicMock, sample_metric: InsightMetric
    ) -> None:
        """Test successful metric retrieval."""
        mock_instance = MagicMock()
        mock_instance.get_metric = AsyncMock(return_value=sample_metric)
        mock_registry.get_category_instance.return_value = mock_instance
        tools = create_insights_tools(mock_registry)
        get_metric_tool = tools[2]

        result = await get_metric_tool.ainvoke(
            {"category_id": "ai_sector_risk", "metric_id": "ai_price_anomaly"}
        )

        assert "AI Price Anomaly" in result
        assert "65/100" in result
        assert "Z-score method" in result
        assert "z = (x - mu) / sigma" in result
        assert "Alpha Vantage" in result

    @pytest.mark.asyncio
    async def test_get_metric_category_not_found(
        self, mock_registry: MagicMock, sample_categories: list[CategoryMetadata]
    ) -> None:
        """Test when category doesn't exist."""
        mock_registry.get_category_instance.return_value = None
        mock_registry.list_categories.return_value = sample_categories
        tools = create_insights_tools(mock_registry)
        get_metric_tool = tools[2]

        result = await get_metric_tool.ainvoke(
            {"category_id": "nonexistent", "metric_id": "any_metric"}
        )

        assert "not found" in result.lower()
        assert "ai_sector_risk" in result

    @pytest.mark.asyncio
    async def test_get_metric_metric_not_found(
        self, mock_registry: MagicMock, sample_category_data: InsightCategory
    ) -> None:
        """Test when metric doesn't exist."""
        mock_instance = MagicMock()
        mock_instance.get_metric = AsyncMock(return_value=None)
        mock_instance.get_category_data = AsyncMock(return_value=sample_category_data)
        mock_registry.get_category_instance.return_value = mock_instance
        tools = create_insights_tools(mock_registry)
        get_metric_tool = tools[2]

        result = await get_metric_tool.ainvoke(
            {"category_id": "ai_sector_risk", "metric_id": "nonexistent"}
        )

        assert "not found" in result.lower()
        assert "ai_price_anomaly" in result  # Suggests available metrics

    @pytest.mark.asyncio
    async def test_get_metric_error(self, mock_registry: MagicMock) -> None:
        """Test error handling."""
        mock_instance = MagicMock()
        mock_instance.get_metric = AsyncMock(side_effect=Exception("Network error"))
        mock_registry.get_category_instance.return_value = mock_instance
        tools = create_insights_tools(mock_registry)
        get_metric_tool = tools[2]

        result = await get_metric_tool.ainvoke(
            {"category_id": "ai_sector_risk", "metric_id": "ai_price_anomaly"}
        )

        assert "error" in result.lower()


class TestStatusEmoji:
    """Tests for status emoji helper."""

    def test_low_status(self) -> None:
        """Test low status returns green."""
        assert _get_status_emoji("low") == "🟢"

    def test_normal_status(self) -> None:
        """Test normal status returns blue."""
        assert _get_status_emoji("normal") == "🔵"

    def test_elevated_status(self) -> None:
        """Test elevated status returns orange."""
        assert _get_status_emoji("elevated") == "🟠"

    def test_high_status(self) -> None:
        """Test high status returns red."""
        assert _get_status_emoji("high") == "🔴"

    def test_unknown_status(self) -> None:
        """Test unknown status returns white."""
        assert _get_status_emoji("unknown") == "⚪"
        assert _get_status_emoji("") == "⚪"


class TestToolMetadata:
    """Tests for tool metadata and configuration."""

    def test_tools_count(self, mock_registry: MagicMock) -> None:
        """Test that exactly 3 tools are created."""
        tools = create_insights_tools(mock_registry)
        assert len(tools) == 3

    def test_tool_names(self, mock_registry: MagicMock) -> None:
        """Test tool names are correct."""
        tools = create_insights_tools(mock_registry)
        names = [t.name for t in tools]
        assert "list_insight_categories" in names
        assert "get_insight_category" in names
        assert "get_insight_metric" in names

    def test_tool_descriptions(self, mock_registry: MagicMock) -> None:
        """Test tools have descriptions."""
        tools = create_insights_tools(mock_registry)
        for tool in tools:
            assert tool.description
            assert len(tool.description) > 50  # Should be descriptive

    def test_tools_count_with_snapshot_service(self, mock_registry: MagicMock) -> None:
        """Test that 4 tools are created when snapshot_service is provided."""
        mock_snapshot_service = MagicMock()
        tools = create_insights_tools(
            mock_registry, snapshot_service=mock_snapshot_service
        )
        assert len(tools) == 4

    def test_tool_names_with_snapshot_service(self, mock_registry: MagicMock) -> None:
        """Test all tool names when snapshot_service is provided."""
        mock_snapshot_service = MagicMock()
        tools = create_insights_tools(
            mock_registry, snapshot_service=mock_snapshot_service
        )
        names = [t.name for t in tools]
        assert "list_insight_categories" in names
        assert "get_insight_category" in names
        assert "get_insight_metric" in names
        assert "get_insight_trend" in names


# =============================================================================
# Story 2.5: Cache-First and Trend Tests
# =============================================================================


@pytest.fixture
def mock_snapshot_service() -> MagicMock:
    """Create mock snapshot service for testing."""
    return MagicMock()


@pytest.fixture
def sample_cached_snapshot() -> dict:
    """Create sample cached snapshot data."""
    return {
        "category_id": "ai_sector_risk",
        "date": "2025-12-28T00:00:00+00:00",
        "composite_score": 72.5,
        "composite_status": "elevated",
        "metrics": {
            "ai_price_anomaly": {"score": 85.0, "status": "high"},
            "news_sentiment": {"score": 65.0, "status": "elevated"},
            "smart_money_flow": {"score": 52.0, "status": "normal"},
        },
        "cached_at": "2025-12-28T10:00:00+00:00",
    }


@pytest.fixture
def sample_trend_snapshots() -> list[dict]:
    """Create sample trend snapshots (newest first)."""
    return [
        {
            "category_id": "ai_sector_risk",
            "date": "2025-12-28T00:00:00+00:00",
            "composite_score": 72.5,
            "composite_status": "elevated",
            "metrics": {
                "ai_price_anomaly": {"score": 85.0, "status": "high"},
                "news_sentiment": {"score": 65.0, "status": "elevated"},
            },
        },
        {
            "category_id": "ai_sector_risk",
            "date": "2025-11-28T00:00:00+00:00",
            "composite_score": 67.2,
            "composite_status": "elevated",
            "metrics": {
                "ai_price_anomaly": {"score": 77.0, "status": "elevated"},
                "news_sentiment": {"score": 68.0, "status": "elevated"},
            },
        },
    ]


class TestGetInsightCategoryCacheFirst:
    """Tests for cache-first behavior in get_insight_category (Story 2.5)."""

    @pytest.mark.asyncio
    async def test_uses_cache_when_available(
        self,
        mock_registry: MagicMock,
        mock_snapshot_service: MagicMock,
        sample_cached_snapshot: dict,
    ) -> None:
        """Test that tool uses cache when data is available."""
        mock_snapshot_service.get_latest_snapshot = AsyncMock(
            return_value=sample_cached_snapshot
        )
        tools = create_insights_tools(
            mock_registry, snapshot_service=mock_snapshot_service
        )
        get_category_tool = tools[1]

        result = await get_category_tool.ainvoke({"category_id": "ai_sector_risk"})

        # Should use cached data, not registry
        mock_snapshot_service.get_latest_snapshot.assert_called_once_with(
            "ai_sector_risk"
        )
        mock_registry.get_category_data.assert_not_called()
        assert "72/100" in result  # Composite score from cache
        assert "AI Sector Risk" in result

    @pytest.mark.asyncio
    async def test_falls_back_to_registry_on_cache_miss(
        self,
        mock_registry: MagicMock,
        mock_snapshot_service: MagicMock,
        sample_category_data: InsightCategory,
    ) -> None:
        """Test that tool falls back to registry when cache is empty."""
        mock_snapshot_service.get_latest_snapshot = AsyncMock(return_value=None)
        mock_registry.get_category_data = AsyncMock(return_value=sample_category_data)
        tools = create_insights_tools(
            mock_registry, snapshot_service=mock_snapshot_service
        )
        get_category_tool = tools[1]

        result = await get_category_tool.ainvoke({"category_id": "ai_sector_risk"})

        # Should fall back to registry
        mock_snapshot_service.get_latest_snapshot.assert_called_once()
        mock_registry.get_category_data.assert_called_once_with("ai_sector_risk")
        assert "55/100" in result  # Composite score from registry


class TestGetInsightTrend:
    """Tests for get_insight_trend tool (Story 2.5)."""

    @pytest.mark.asyncio
    async def test_get_trend_success(
        self,
        mock_registry: MagicMock,
        mock_snapshot_service: MagicMock,
        sample_trend_snapshots: list[dict],
    ) -> None:
        """Test successful trend retrieval."""
        mock_snapshot_service.get_trend = AsyncMock(return_value=sample_trend_snapshots)
        tools = create_insights_tools(
            mock_registry, snapshot_service=mock_snapshot_service
        )
        get_trend_tool = tools[3]

        result = await get_trend_tool.ainvoke(
            {"category_id": "ai_sector_risk", "days": 30}
        )

        assert "AI Sector Risk" in result
        assert "30 Day Trend" in result
        assert "72.5/100" in result  # Current score
        assert "+5.3" in result  # Change from 67.2 to 72.5

    @pytest.mark.asyncio
    async def test_get_trend_no_snapshot_service(
        self, mock_registry: MagicMock
    ) -> None:
        """Test error when snapshot_service not configured."""
        tools = create_insights_tools(mock_registry, snapshot_service=None)
        # Should only have 3 tools without snapshot_service
        assert len(tools) == 3

    @pytest.mark.asyncio
    async def test_get_trend_empty_data(
        self,
        mock_registry: MagicMock,
        mock_snapshot_service: MagicMock,
    ) -> None:
        """Test handling of empty trend data."""
        mock_snapshot_service.get_trend = AsyncMock(return_value=[])
        tools = create_insights_tools(
            mock_registry, snapshot_service=mock_snapshot_service
        )
        get_trend_tool = tools[3]

        result = await get_trend_tool.ainvoke(
            {"category_id": "ai_sector_risk", "days": 30}
        )

        assert "no trend data" in result.lower()

    @pytest.mark.asyncio
    async def test_get_trend_caps_days_at_90(
        self,
        mock_registry: MagicMock,
        mock_snapshot_service: MagicMock,
        sample_trend_snapshots: list[dict],
    ) -> None:
        """Test that days parameter is capped at 90."""
        mock_snapshot_service.get_trend = AsyncMock(return_value=sample_trend_snapshots)
        tools = create_insights_tools(
            mock_registry, snapshot_service=mock_snapshot_service
        )
        get_trend_tool = tools[3]

        await get_trend_tool.ainvoke({"category_id": "ai_sector_risk", "days": 365})

        # Should cap at 90
        mock_snapshot_service.get_trend.assert_called_once_with("ai_sector_risk", 90)


class TestTrendDirection:
    """Tests for trend direction helper (Story 2.5)."""

    def test_rising_trend(self) -> None:
        """Test rising trend detection."""
        direction, label = _get_trend_direction(5.0)
        assert direction == "↑"
        assert label == "Rising"

    def test_falling_trend(self) -> None:
        """Test falling trend detection."""
        direction, label = _get_trend_direction(-5.0)
        assert direction == "↓"
        assert label == "Falling"

    def test_stable_trend(self) -> None:
        """Test stable trend detection."""
        direction, label = _get_trend_direction(1.0)
        assert direction == "→"
        assert label == "Stable"

    def test_boundary_rising(self) -> None:
        """Test boundary for rising (> 2)."""
        direction, _ = _get_trend_direction(2.1)
        assert direction == "↑"

    def test_boundary_falling(self) -> None:
        """Test boundary for falling (< -2)."""
        direction, _ = _get_trend_direction(-2.1)
        assert direction == "↓"


class TestFormatCachedInsight:
    """Tests for cached insight formatting (Story 2.5)."""

    def test_format_cached_insight_basic(self, sample_cached_snapshot: dict) -> None:
        """Test basic formatting of cached insight."""
        result = _format_cached_insight("ai_sector_risk", sample_cached_snapshot)

        assert "AI Sector Risk" in result
        assert "72/100" in result
        assert "ELEVATED" in result
        assert "Ai Price Anomaly" in result
        assert "85/100" in result

    def test_format_cached_insight_includes_table(
        self, sample_cached_snapshot: dict
    ) -> None:
        """Test that output includes markdown table."""
        result = _format_cached_insight("ai_sector_risk", sample_cached_snapshot)

        assert "| Metric |" in result
        assert "|--------|" in result

    def test_format_cached_insight_unknown_category(self) -> None:
        """Test formatting with unknown category ID."""
        data = {"composite_score": 50.0, "composite_status": "normal", "metrics": {}}
        result = _format_cached_insight("unknown_category", data)

        assert "Unknown Category" in result


class TestFormatTrendResponse:
    """Tests for trend response formatting (Story 2.5)."""

    def test_format_trend_with_data(self, sample_trend_snapshots: list[dict]) -> None:
        """Test trend formatting with multiple snapshots."""
        result = _format_trend_response("ai_sector_risk", sample_trend_snapshots, 30)

        assert "AI Sector Risk - 30 Day Trend" in result
        assert "72.5/100" in result
        assert "+5.3" in result  # Change
        assert "Metric Trends" in result
        assert "Interpretation" in result

    def test_format_trend_single_snapshot(self) -> None:
        """Test trend formatting with only one snapshot."""
        single = [{"composite_score": 72.5, "composite_status": "elevated"}]
        result = _format_trend_response("ai_sector_risk", single, 30)

        assert "72.5/100" in result
        assert "Not enough historical data" in result

    def test_format_trend_empty(self) -> None:
        """Test trend formatting with no data."""
        result = _format_trend_response("ai_sector_risk", [], 30)

        assert "No data available" in result

    def test_format_trend_increasing_risk(
        self, sample_trend_snapshots: list[dict]
    ) -> None:
        """Test interpretation for increasing risk."""
        result = _format_trend_response("ai_sector_risk", sample_trend_snapshots, 30)

        assert "increased" in result.lower()
        assert "growing risk" in result.lower()

    def test_format_trend_decreasing_risk(self) -> None:
        """Test interpretation for decreasing risk."""
        snapshots = [
            {"composite_score": 60.0, "composite_status": "elevated", "metrics": {}},
            {"composite_score": 75.0, "composite_status": "high", "metrics": {}},
        ]
        result = _format_trend_response("ai_sector_risk", snapshots, 30)

        assert "decreased" in result.lower()
        assert "reduced risk" in result.lower()
