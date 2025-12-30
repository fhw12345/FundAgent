"""Category registry for the Market Insights Platform.

The registry provides plugin-style auto-discovery of insight categories.
New categories are automatically registered when they inherit from
InsightCategoryBase and are imported from the categories/ directory.
"""

from typing import Any

import structlog

from ...core.config import Settings
from ...database.redis import RedisCache
from .base import InsightCategoryBase
from .models import CategoryMetadata, InsightCategory

logger = structlog.get_logger()

# Global registry of category classes
_category_registry: dict[str, type[InsightCategoryBase]] = {}


def register_category(
    category_class: type[InsightCategoryBase],
) -> type[InsightCategoryBase]:
    """Decorator to register a category class.

    Usage:
        @register_category
        class AISectorRiskCategory(InsightCategoryBase):
            CATEGORY_ID = "ai_sector_risk"
            ...
    """
    category_id = category_class.CATEGORY_ID
    if not category_id:
        raise ValueError(
            f"Category class {category_class.__name__} must define CATEGORY_ID"
        )

    if category_id in _category_registry:
        logger.warning(
            "Category already registered, overwriting",
            category_id=category_id,
            old_class=_category_registry[category_id].__name__,
            new_class=category_class.__name__,
        )

    _category_registry[category_id] = category_class
    logger.info(
        "Category registered",
        category_id=category_id,
        class_name=category_class.__name__,
    )
    return category_class


def get_registered_categories() -> dict[str, type[InsightCategoryBase]]:
    """Get all registered category classes.

    Returns:
        Dict mapping category_id to category class
    """
    return _category_registry.copy()


class InsightsCategoryRegistry:
    """Runtime registry managing instantiated category instances.

    This class manages the lifecycle of category instances,
    providing dependency injection and caching.
    """

    def __init__(
        self,
        settings: Settings,
        redis_cache: RedisCache | None = None,
        market_service: Any | None = None,
        fred_service: Any | None = None,
    ) -> None:
        """Initialize registry with dependencies.

        Args:
            settings: Application settings
            redis_cache: Optional Redis cache
            market_service: AlphaVantageMarketDataService instance
            fred_service: FREDService instance for liquidity metrics
        """
        self.settings = settings
        self.redis_cache = redis_cache
        self.market_service = market_service
        self.fred_service = fred_service
        self._instances: dict[str, InsightCategoryBase] = {}

        # Auto-discover and load categories
        self._load_categories()

    def _load_categories(self) -> None:
        """Load and instantiate all registered categories."""
        # Import categories module to trigger registration
        # This import must happen here to avoid circular imports
        try:
            from . import categories  # noqa: F401

            logger.info(
                "Categories module loaded",
                registered_count=len(_category_registry),
            )
        except ImportError as e:
            logger.warning(
                "Failed to import categories module",
                error=str(e),
            )

        # Instantiate each registered category
        for category_id, category_class in _category_registry.items():
            try:
                instance = category_class(
                    settings=self.settings,
                    redis_cache=self.redis_cache,
                    market_service=self.market_service,
                    fred_service=self.fred_service,
                )
                self._instances[category_id] = instance
                logger.info(
                    "Category instantiated",
                    category_id=category_id,
                )
            except Exception as e:
                logger.error(
                    "Failed to instantiate category",
                    category_id=category_id,
                    error=str(e),
                )

    def list_categories(self) -> list[CategoryMetadata]:
        """List all available categories with metadata.

        Returns:
            List of CategoryMetadata objects
        """
        return [instance.get_metadata() for instance in self._instances.values()]

    def get_category_instance(self, category_id: str) -> InsightCategoryBase | None:
        """Get a category instance by ID.

        Args:
            category_id: The category identifier

        Returns:
            InsightCategoryBase instance or None if not found
        """
        return self._instances.get(category_id)

    async def get_category_data(
        self,
        category_id: str,
        force_refresh: bool = False,
    ) -> InsightCategory | None:
        """Get complete data for a category.

        Args:
            category_id: The category identifier
            force_refresh: If True, bypass cache

        Returns:
            InsightCategory or None if not found
        """
        instance = self.get_category_instance(category_id)
        if instance is None:
            logger.warning("Category not found", category_id=category_id)
            return None

        return await instance.get_category_data(force_refresh=force_refresh)

    async def get_all_categories_data(
        self,
        force_refresh: bool = False,
    ) -> list[InsightCategory]:
        """Get data for all categories.

        Args:
            force_refresh: If True, bypass cache for all

        Returns:
            List of InsightCategory objects
        """
        results = []
        for category_id in self._instances:
            data = await self.get_category_data(category_id, force_refresh)
            if data:
                results.append(data)
        return results

    async def refresh_category(self, category_id: str) -> InsightCategory | None:
        """Force refresh a category's data.

        Args:
            category_id: The category identifier

        Returns:
            Fresh InsightCategory or None if not found
        """
        instance = self.get_category_instance(category_id)
        if instance is None:
            return None

        return await instance.refresh()

    async def refresh_all(self) -> list[InsightCategory]:
        """Force refresh all categories.

        Returns:
            List of fresh InsightCategory objects
        """
        results = []
        for category_id, instance in self._instances.items():
            try:
                data = await instance.refresh()
                results.append(data)
            except Exception as e:
                logger.error(
                    "Failed to refresh category",
                    category_id=category_id,
                    error=str(e),
                )
        return results

    @property
    def category_count(self) -> int:
        """Number of registered categories."""
        return len(self._instances)

    @property
    def category_ids(self) -> list[str]:
        """List of all category IDs."""
        return list(self._instances.keys())
