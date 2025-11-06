"""
Dependencies for portfolio API endpoints.
"""

from fastapi import Depends

from ...core.config import Settings, get_settings
from ...core.data.ticker_data_service import TickerDataService
from ...database.mongodb import MongoDB
from ...database.redis import RedisCache
from ...database.repositories.holding_repository import HoldingRepository
from ...services.alpaca_data_service import AlpacaDataService
from ...services.alpaca_trading_service import AlpacaTradingService
from ...services.portfolio_service import PortfolioService
from .auth import get_mongodb  # Import shared auth
from .chat_deps import get_redis


def get_holding_repository(
    mongodb: MongoDB = Depends(get_mongodb),
) -> HoldingRepository:
    """Get holding repository instance."""
    holdings_collection = mongodb.get_collection("holdings")
    return HoldingRepository(holdings_collection)


def get_alpaca_data_service(
    settings: Settings = Depends(get_settings),
) -> AlpacaDataService | None:
    """Get Alpaca data service instance (returns None if credentials not set)."""
    if not settings.alpaca_api_key or not settings.alpaca_secret_key:
        return None
    return AlpacaDataService(settings=settings)


def get_ticker_data_service(
    redis_cache: RedisCache = Depends(get_redis),
    alpaca_service: AlpacaDataService | None = Depends(get_alpaca_data_service),
) -> TickerDataService:
    """Get ticker data service instance."""
    return TickerDataService(
        redis_cache=redis_cache,
        alpaca_data_service=alpaca_service,  # Can be None, will fall back to yfinance
    )


def get_alpaca_trading_service(
    settings: Settings = Depends(get_settings),
) -> AlpacaTradingService | None:
    """Get Alpaca trading service instance (returns None if credentials not set)."""
    if not settings.alpaca_api_key or not settings.alpaca_secret_key:
        return None
    return AlpacaTradingService(settings=settings)


def get_portfolio_service(
    holding_repo: HoldingRepository = Depends(get_holding_repository),
    ticker_service: TickerDataService = Depends(get_ticker_data_service),
    settings: Settings = Depends(get_settings),
) -> PortfolioService:
    """Get portfolio service instance."""
    return PortfolioService(
        holding_repo=holding_repo,
        ticker_service=ticker_service,
        settings=settings,
    )
