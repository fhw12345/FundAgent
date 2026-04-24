"""Per-analysis tool result cache — deduplicates tool calls across sub-agents."""

from collections.abc import Callable
from typing import Any

import structlog

logger = structlog.get_logger()


class AnalysisToolCache:
    """Cache tool results within a single analysis run to avoid duplicate API calls."""

    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}
        self._hits = 0
        self._misses = 0

    def wrap_tools(self, tools: list[Any]) -> list[Any]:
        """Wrap tools with caching — passthrough for now."""
        return tools

    def log_stats(self) -> None:
        logger.info("Analysis cache stats", hits=self._hits, misses=self._misses, cached_keys=len(self._cache))
