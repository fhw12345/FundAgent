"""
Alpaca Paper Trading Service - Backward Compatibility Module.

This module maintains backward compatibility for existing code that imports:
    from ...services.alpaca_trading_service import AlpacaTradingService

The actual implementation has been split into a modular structure:
    backend/src/services/alpaca/
    ├── __init__.py           # Re-exports AlpacaTradingService
    ├── base.py               # Base service: initialization, client setup
    ├── orders.py             # Order operations: submit_order, get_orders
    ├── positions.py          # Position operations: get_positions, get_portfolio
    ├── helpers.py            # Helpers: validation, formatting
    └── service.py            # Main service combining all operations

For new code, prefer importing from the package:
    from ...services.alpaca import AlpacaTradingService

This provides better organization and keeps file sizes under 500 lines.
"""

# Re-export for backward compatibility
from .alpaca import AlpacaTradingService

__all__ = ["AlpacaTradingService"]
