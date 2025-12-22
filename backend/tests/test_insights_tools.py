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

from src.agent.tools.insights_tools import _get_status_emoji, create_insights_tools
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
