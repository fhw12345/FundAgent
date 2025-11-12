"""
Market Data API endpoints using hybrid Alpaca + Polygon.io provider.
Replaces yfinance to avoid rate limiting in cloud environments.
"""

from datetime import datetime
from functools import lru_cache

import pandas as pd
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.config import Settings
from ..core.utils import (
    get_valid_frontend_intervals,
)
from ..services.alphavantage_market_data import AlphaVantageMarketDataService
from .dependencies.auth import get_current_user_id

router = APIRouter(prefix="/api/market", tags=["Market Data"])
logger = structlog.get_logger()


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def get_market_service() -> AlphaVantageMarketDataService:
    """Dependency to get market data service."""
    return AlphaVantageMarketDataService(get_settings())


class SymbolSearchResult(BaseModel):
    """Symbol search result."""

    symbol: str = Field(..., description="Stock symbol (e.g., AAPL)")
    name: str = Field(..., description="Company name")
    exchange: str = Field(default="", description="Exchange name")
    type: str = Field(default="", description="Security type")
    match_type: str = Field(
        default="",
        description="Match classification: exact_symbol | symbol_prefix | name_prefix | fuzzy",
    )
    confidence: float = Field(
        default=0.0, description="Confidence score 0-1 for ranking"
    )


class SymbolSearchResponse(BaseModel):
    """Symbol search response."""

    query: str = Field(..., description="Original search query")
    results: list[SymbolSearchResult] = Field(..., description="Search results")


class PriceDataPoint(BaseModel):
    """Single price data point."""

    time: str = Field(
        ..., description="Timestamp (YYYY-MM-DD format for daily, ISO for intraday)"
    )
    open: float = Field(..., description="Opening price")
    high: float = Field(..., description="High price")
    low: float = Field(..., description="Low price")
    close: float = Field(..., description="Closing price")
    volume: int = Field(..., description="Trading volume")


class PriceDataResponse(BaseModel):
    """Price data response."""

    symbol: str = Field(..., description="Stock symbol")
    interval: str = Field(..., description="Data interval")
    data: list[PriceDataPoint] = Field(..., description="Price data points")
    last_updated: str = Field(..., description="Last updated timestamp")


@router.get("/search", response_model=SymbolSearchResponse)
async def search_symbols(
    q: str = Query(
        ...,
        min_length=1,
        max_length=50,
        description="Search query (company name or partial symbol)",
    ),
    user_id: str = Depends(get_current_user_id),
    service: AlphaVantageMarketDataService = Depends(get_market_service),
) -> SymbolSearchResponse:
    """
    Search for stock symbols using Alpaca assets with fuzzy matching.

    Supports queries like 'apple', 'microsoft', 'AAPL', etc.
    Uses client-side fuzzy matching on Alpaca's asset list.
    """
    try:
        # Clean query
        query = q.strip()
        if len(query) < 1:
            raise ValueError("Search query must be at least 1 character")

        logger.info("Symbol search started", query=query, user_id=user_id)

        # Use hybrid service
        raw_results = await service.search_symbols(query, limit=10)

        # Convert to response model
        results = [
            SymbolSearchResult(
                symbol=r["symbol"],
                name=r["name"],
                exchange=r["exchange"],
                type=r["type"],
                match_type=r["match_type"],
                confidence=r["confidence"],
            )
            for r in raw_results
        ]

        logger.info(
            "Symbol search completed",
            query=query,
            result_count=len(results),
        )

        return SymbolSearchResponse(query=query, results=results)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("Symbol search failed", query=q, error=str(e), error_type=type(e).__name__)
        raise HTTPException(
            status_code=500, detail=f"Symbol search failed: {str(e)}"
        ) from e


@router.get("/price/{symbol}", response_model=PriceDataResponse)
async def get_price_data(
    symbol: str,
    user_id: str = Depends(get_current_user_id),
    service: AlphaVantageMarketDataService = Depends(get_market_service),
    interval: str = Query(
        default="1d",
        description="Data interval: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo",
    ),
    period: str = Query(
        default="6mo",
        description="Data period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max",
    ),
    start_date: str | None = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: str | None = Query(default=None, description="End date (YYYY-MM-DD)"),
) -> PriceDataResponse:
    """
    Get price data using Alpha Vantage with extended hours support.

    Supports multiple time intervals:
    - Intraday: 1m, 5m, 15m, 30m, 60m
    - Daily+: 1d, 1wk, 1mo

    Uses Alpha Vantage TIME_SERIES_INTRADAY with extended_hours=true for pre/post market data.
    """
    try:
        # Validate symbol
        symbol = symbol.upper().strip()
        if not symbol:
            raise ValueError("Symbol is required")

        # Validate interval
        valid_intervals = get_valid_frontend_intervals()
        if interval not in valid_intervals:
            raise ValueError(f"Invalid interval. Must be one of: {valid_intervals}")

        logger.info(
            "Price data request",
            symbol=symbol,
            interval=interval,
            period=period,
            user_id=user_id,
        )

        # Fetch data using Alpha Vantage
        data = await service.get_price_bars(
            symbol=symbol,
            interval=interval,
            period=period,
            start_date=start_date,
            end_date=end_date,
        )

        if data.empty:
            logger.warning("No price data available", symbol=symbol, period=period)
            raise HTTPException(
                status_code=400,
                detail={
                    "message": f"No data available for symbol {symbol}",
                    "suggestions": [],
                },
            )

        # Convert to response format
        price_points = []
        for index, row in data.iterrows():
            # Format time based on interval
            if interval in ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"]:
                # Intraday: use full timestamp
                time_str = index.strftime("%Y-%m-%dT%H:%M:%S")
            else:
                # Daily+: use date only
                time_str = index.strftime("%Y-%m-%d")

            price_point = PriceDataPoint(
                time=time_str,
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=int(row["Volume"]) if not pd.isna(row["Volume"]) else 0,
            )
            price_points.append(price_point)

        logger.info(
            "Price data fetched successfully",
            symbol=symbol,
            bars_count=len(price_points),
            interval=interval,
        )

        return PriceDataResponse(
            symbol=symbol,
            interval=interval,
            data=price_points,
            last_updated=datetime.now().isoformat(),
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(
            "Price data fetch failed",
            symbol=symbol,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch price data: {str(e)}"
        ) from e


@router.get("/info/{symbol}")
async def get_symbol_info(
    symbol: str,
    user_id: str = Depends(get_current_user_id),
    service: AlphaVantageMarketDataService = Depends(get_market_service),
) -> dict[str, str]:
    """
    Get basic symbol information from Alpaca.

    Returns symbol, name, exchange for autocomplete enhancement.
    Note: Alpaca provides limited fundamental data compared to yfinance.
    """
    try:
        symbol = symbol.upper().strip()

        # Get assets and find matching symbol
        assets = await service._get_alpaca_assets()
        matching_asset = next((a for a in assets if a.symbol == symbol), None)

        if not matching_asset:
            raise ValueError(f"Symbol {symbol} not found")

        return {
            "symbol": matching_asset.symbol,
            "name": matching_asset.name,
            "exchange": matching_asset.exchange.value if hasattr(matching_asset.exchange, "value") else str(matching_asset.exchange),
            "type": matching_asset.asset_class.value if hasattr(matching_asset.asset_class, "value") else "EQUITY",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("Symbol info fetch failed", symbol=symbol, error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch symbol info: {str(e)}"
        ) from e
