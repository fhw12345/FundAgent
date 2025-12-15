"""
Alpaca Trading Service - Modular Implementation.

This package provides a modular implementation of the Alpaca Paper Trading Service:

- base.py: Base service initialization and client setup
- orders.py: Order placement and retrieval operations
- positions.py: Position tracking and portfolio summary
- helpers.py: Validation and conversion utilities
- service.py: Main service class combining all operations

The main AlpacaTradingService class is exported for backward compatibility
with code that imports from the original monolithic module.
"""

from .service import AlpacaTradingService

__all__ = ["AlpacaTradingService"]
