"""
Data Manager Layer (DML) - Single source of truth for all data access.

This module provides a unified interface for fetching and caching market data,
ensuring consistent cache key naming, TTL strategies, and no duplicate API calls.

Usage:
    from services.data_manager import DataManager, CacheKeys

    # Initialize with dependencies
    dm = DataManager(settings, redis_cache, av_service)

    # Fetch with automatic caching
    ohlcv = await dm.get_ohlcv("AAPL", "daily")
    treasury = await dm.get_treasury("2y")

Cache Key Convention:
    {domain}:{granularity/type}:{identifier}

    Examples:
    - market:daily:AAPL
    - macro:treasury:2y
    - sentiment:news:technology
    - insights:ai_sector_risk:latest
"""

from .cache import CacheOperations
from .keys import CacheKeys
from .manager import DataManager
from .types import (
    DataFetchError,
    Granularity,
    IPOData,
    MetricStatus,
    NewsData,
    OHLCVData,
    OptionContract,
    QuoteData,
    SharedDataContext,
    TreasuryData,
    TrendPoint,
)

__all__ = [
    "DataManager",
    "CacheKeys",
    "CacheOperations",
    "OHLCVData",
    "TreasuryData",
    "NewsData",
    "IPOData",
    "TrendPoint",
    "QuoteData",
    "OptionContract",
    "SharedDataContext",
    "DataFetchError",
    "Granularity",
    "MetricStatus",
]
