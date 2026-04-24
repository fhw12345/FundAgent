"""Tool categorization for sub-agent tool routing — stub for fund domain."""

from collections.abc import Callable
from typing import Any


def get_tools_for_subagent(
    tools: list[Any],
    subagent_name: str,
) -> dict[str, Callable]:
    """Return all tools for now — fund-specific filtering added later."""
    return {getattr(t, "name", str(i)): t for i, t in enumerate(tools)}


def get_all_tools_dict(tools: list[Any]) -> dict[str, Any]:
    """Convert tool list to name→tool dict."""
    return {getattr(t, "name", str(i)): t for i, t in enumerate(tools)}
