"""
Base Alpaca Trading Service.

Provides initialization and client setup for Alpaca Paper Trading API.
"""

import structlog
from alpaca.trading.client import TradingClient

from ...core.config import Settings

logger = structlog.get_logger()


class AlpacaTradingServiceBase:
    """
    Base class for Alpaca Trading Service.

    Provides:
    - Alpaca TradingClient initialization
    - Paper trading configuration
    - Settings management

    Free tier: Paper trading with $1M virtual portfolio
    """

    def __init__(self, settings: Settings):
        """
        Initialize Alpaca trading client.

        Args:
            settings: Application settings with Alpaca credentials
        """
        self.settings = settings

        # Initialize Alpaca client
        self.client = TradingClient(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
            paper=True,  # Paper trading (FREE)
        )

        logger.info(
            "AlpacaTradingService initialized",
            base_url=settings.alpaca_base_url,
            paper_trading=True,
        )
