"""
Alpaca Paper Trading Service for portfolio management.

Provides order execution, position tracking, and portfolio history
using Alpaca's Paper Trading API (FREE for testing).

Based on verification results from scripts/alpaca_test_results.json
"""

from ...core.config import Settings
from .orders import OrderOperations
from .positions import PositionOperations


class AlpacaTradingService(OrderOperations, PositionOperations):
    """
    Alpaca Paper Trading API integration.

    Provides:
    1. Order execution with audit trail (client_order_id)
    2. Position tracking
    3. Portfolio summary
    4. Order history

    Free tier: Paper trading with $1M virtual portfolio

    This class combines order operations and position operations
    through multiple inheritance, maintaining backward compatibility
    with the original monolithic service.
    """

    def __init__(self, settings: Settings):
        """
        Initialize Alpaca trading client.

        Args:
            settings: Application settings with Alpaca credentials
        """
        # Initialize base class (which initializes the Alpaca client)
        super().__init__(settings)
