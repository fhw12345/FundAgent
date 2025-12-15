"""
Alpha Vantage Agent Tools for LLM Access.

DEPRECATED: This module is now a simple re-export for backward compatibility.
Please import from `agent.tools.alpha_vantage` instead.

Provides rich markdown outputs with metadata and trend analysis.
All tools use AlphaVantageMarketDataService for market data access.
"""

from .alpha_vantage import create_alpha_vantage_tools

__all__ = ["create_alpha_vantage_tools"]
