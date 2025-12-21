"""Market Insights Platform service module.

This module provides the backend service layer for the Market Insights
Platform, featuring an extensible category system with plugin-style
registration.

Key Components:
- InsightCategoryBase: Abstract base class for categories
- InsightsCategoryRegistry: Runtime registry for category management
- Models: Pydantic models for metrics, explanations, and categories

Usage:
    from src.services.insights import InsightsCategoryRegistry
    from src.core.config import Settings

    settings = Settings()
    registry = InsightsCategoryRegistry(
        settings=settings,
        redis_cache=redis_cache,
        market_service=market_service,
    )

    # List all categories
    categories = registry.list_categories()

    # Get data for a specific category
    data = await registry.get_category_data("ai_sector_risk")

Adding New Categories:
    1. Create file in categories/ (e.g., sector_rotation.py)
    2. Inherit from InsightCategoryBase
    3. Use @register_category decorator
    4. Import in categories/__init__.py
"""

from .base import InsightCategoryBase
from .models import (
    CategoryMetadata,
    CompositeScore,
    InsightCategory,
    InsightMetric,
    MetricExplanation,
    MetricStatus,
    ThresholdConfig,
)
from .registry import InsightsCategoryRegistry, register_category

__all__ = [
    # Base class
    "InsightCategoryBase",
    # Registry
    "InsightsCategoryRegistry",
    "register_category",
    # Models
    "CategoryMetadata",
    "CompositeScore",
    "InsightCategory",
    "InsightMetric",
    "MetricExplanation",
    "MetricStatus",
    "ThresholdConfig",
]
