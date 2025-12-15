"""
Watchlist Analyzer Service - Backward Compatibility Layer.

This module maintains backward compatibility by re-exporting
the WatchlistAnalyzer from the new modular structure.

DEPRECATED: Import from src.services.watchlist instead.
"""

from .watchlist import WatchlistAnalyzer

__all__ = ["WatchlistAnalyzer"]
