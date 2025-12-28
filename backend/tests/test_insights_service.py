"""Tests for the Market Insights Platform service layer."""

import pytest

from src.core.config import Settings
from src.services.insights import (
    InsightCategoryBase,
    InsightsCategoryRegistry,
    MetricStatus,
    ThresholdConfig,
)
from src.services.insights.categories.ai_sector_risk import AISectorRiskCategory


class TestThresholdConfig:
    """Tests for ThresholdConfig model."""

    def test_default_thresholds(self) -> None:
        """Test default threshold values."""
        config = ThresholdConfig()
        assert config.low == 25
        assert config.normal == 50
        assert config.elevated == 75
        assert config.high == 100

    def test_get_status_low(self) -> None:
        """Test status for low scores."""
        config = ThresholdConfig()
        assert config.get_status(0) == MetricStatus.LOW
        assert config.get_status(10) == MetricStatus.LOW
        assert config.get_status(24.9) == MetricStatus.LOW

    def test_get_status_normal(self) -> None:
        """Test status for normal scores."""
        config = ThresholdConfig()
        assert config.get_status(25) == MetricStatus.NORMAL
        assert config.get_status(35) == MetricStatus.NORMAL
        assert config.get_status(49.9) == MetricStatus.NORMAL

    def test_get_status_elevated(self) -> None:
        """Test status for elevated scores."""
        config = ThresholdConfig()
        assert config.get_status(50) == MetricStatus.ELEVATED
        assert config.get_status(60) == MetricStatus.ELEVATED
        assert config.get_status(74.9) == MetricStatus.ELEVATED

    def test_get_status_high(self) -> None:
        """Test status for high scores."""
        config = ThresholdConfig()
        assert config.get_status(75) == MetricStatus.HIGH
        assert config.get_status(85) == MetricStatus.HIGH
        assert config.get_status(100) == MetricStatus.HIGH


class TestInsightCategoryBase:
    """Tests for InsightCategoryBase utility methods."""

    def test_normalize_score_basic(self) -> None:
        """Test basic score normalization."""
        # Middle of range should be 50
        assert InsightCategoryBase.normalize_score(50, 0, 100) == 50.0

        # Min value should be 0
        assert InsightCategoryBase.normalize_score(0, 0, 100) == 0.0

        # Max value should be 100
        assert InsightCategoryBase.normalize_score(100, 0, 100) == 100.0

    def test_normalize_score_clamping(self) -> None:
        """Test score clamping to 0-100 range."""
        # Below min should clamp to 0
        assert InsightCategoryBase.normalize_score(-50, 0, 100) == 0.0

        # Above max should clamp to 100
        assert InsightCategoryBase.normalize_score(150, 0, 100) == 100.0

    def test_normalize_score_inverted(self) -> None:
        """Test inverted normalization."""
        # High value should become low score when inverted
        assert InsightCategoryBase.normalize_score(100, 0, 100, invert=True) == 0.0

        # Low value should become high score when inverted
        assert InsightCategoryBase.normalize_score(0, 0, 100, invert=True) == 100.0

    def test_normalize_score_custom_range(self) -> None:
        """Test normalization with custom range."""
        # Z-score range: -3 to +3
        assert InsightCategoryBase.normalize_score(0, -3, 3) == 50.0
        assert InsightCategoryBase.normalize_score(-3, -3, 3) == 0.0
        assert InsightCategoryBase.normalize_score(3, -3, 3) == 100.0


class TestAISectorRiskCategory:
    """Tests for AISectorRiskCategory."""

    @pytest.fixture
    def category(self) -> AISectorRiskCategory:
        """Create category instance for testing."""
        settings = Settings()
        return AISectorRiskCategory(settings=settings)

    def test_category_metadata(self, category: AISectorRiskCategory) -> None:
        """Test category metadata."""
        assert category.CATEGORY_ID == "ai_sector_risk"
        assert category.CATEGORY_NAME == "AI Sector Risk"
        assert category.CATEGORY_ICON == "🎯"
        assert "bubble risk" in category.CATEGORY_DESCRIPTION.lower()

    def test_get_metadata(self, category: AISectorRiskCategory) -> None:
        """Test metadata retrieval."""
        metadata = category.get_metadata()
        assert metadata.id == "ai_sector_risk"
        assert metadata.name == "AI Sector Risk"
        assert metadata.icon == "🎯"
        assert metadata.metric_count == 6

    def test_get_metric_definitions(self, category: AISectorRiskCategory) -> None:
        """Test metric definitions."""
        definitions = category.get_metric_definitions()
        assert len(definitions) == 6

        # Check all expected metrics exist
        metric_ids = {d["id"] for d in definitions}
        expected_ids = {
            "ai_price_anomaly",
            "news_sentiment",
            "smart_money_flow",
            "ipo_heat",
            "yield_curve",
            "fed_expectations",
        }
        assert metric_ids == expected_ids

    def test_get_composite_weights(self, category: AISectorRiskCategory) -> None:
        """Test composite weights sum to 1.0."""
        weights = category.get_composite_weights()
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.001, f"Weights sum to {total}, expected 1.0"

    @pytest.mark.asyncio
    async def test_calculate_metrics(self, category: AISectorRiskCategory) -> None:
        """Test metric calculation returns valid metrics."""
        metrics = await category.calculate_metrics()

        assert len(metrics) == 6

        for metric in metrics:
            # Check basic structure
            assert metric.id
            assert metric.name
            assert 0 <= metric.score <= 100 or metric.score == -1  # -1 for errors
            assert metric.explanation.summary
            assert metric.explanation.detail
            assert metric.explanation.methodology

    @pytest.mark.asyncio
    async def test_get_category_data(self, category: AISectorRiskCategory) -> None:
        """Test full category data retrieval."""
        data = await category.get_category_data()

        assert data.id == "ai_sector_risk"
        assert data.name == "AI Sector Risk"
        assert len(data.metrics) == 6
        assert data.composite is not None
        assert 0 <= data.composite.score <= 100


class TestInsightsCategoryRegistry:
    """Tests for InsightsCategoryRegistry."""

    @pytest.fixture
    def registry(self) -> InsightsCategoryRegistry:
        """Create registry instance for testing."""
        settings = Settings()
        return InsightsCategoryRegistry(settings=settings)

    def test_registry_initialization(self, registry: InsightsCategoryRegistry) -> None:
        """Test registry initializes with categories."""
        assert registry.category_count >= 1
        assert "ai_sector_risk" in registry.category_ids

    def test_list_categories(self, registry: InsightsCategoryRegistry) -> None:
        """Test category listing."""
        categories = registry.list_categories()
        assert len(categories) >= 1

        # Check AI Sector Risk is present
        ai_risk = next((c for c in categories if c.id == "ai_sector_risk"), None)
        assert ai_risk is not None
        assert ai_risk.name == "AI Sector Risk"

    def test_get_category_instance(self, registry: InsightsCategoryRegistry) -> None:
        """Test getting category instance."""
        instance = registry.get_category_instance("ai_sector_risk")
        assert instance is not None
        assert isinstance(instance, AISectorRiskCategory)

    def test_get_category_instance_not_found(
        self, registry: InsightsCategoryRegistry
    ) -> None:
        """Test getting non-existent category returns None."""
        instance = registry.get_category_instance("nonexistent")
        assert instance is None

    @pytest.mark.asyncio
    async def test_get_category_data(self, registry: InsightsCategoryRegistry) -> None:
        """Test getting category data via registry."""
        data = await registry.get_category_data("ai_sector_risk")
        assert data is not None
        assert data.id == "ai_sector_risk"
        assert len(data.metrics) == 6

    @pytest.mark.asyncio
    async def test_get_category_data_not_found(
        self, registry: InsightsCategoryRegistry
    ) -> None:
        """Test getting data for non-existent category."""
        data = await registry.get_category_data("nonexistent")
        assert data is None
