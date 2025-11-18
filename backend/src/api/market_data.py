"""
Market Data API endpoints using hybrid Alpaca + Polygon.io provider.
Replaces yfinance to avoid rate limiting in cloud environments.
"""

from datetime import datetime, timedelta
from functools import lru_cache

import pandas as pd
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.config import Settings
from ..core.utils import (
    get_valid_frontend_intervals,
)
from ..core.utils.cache_utils import get_tool_ttl
from ..database.redis import RedisCache
from ..services.alphavantage_market_data import (
    AlphaVantageMarketDataService,
    get_market_session,
    validate_date_range,
)
from .dependencies.auth import get_current_user_id
from .dependencies.chat_deps import get_redis

router = APIRouter(prefix="/api/market", tags=["Market Data"])
logger = structlog.get_logger()


@lru_cache
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
    market_session: str | None = Field(
        None,
        description="Market session indicator for intraday data: pre (pre-market), regular (regular hours), post (post-market), closed (after hours/weekends)",
    )


class PriceDataResponse(BaseModel):
    """Price data response."""

    symbol: str = Field(..., description="Stock symbol")
    interval: str = Field(..., description="Data interval")
    data: list[PriceDataPoint] = Field(..., description="Price data points")
    last_updated: str = Field(..., description="Last updated timestamp")


class MarketStatusResponse(BaseModel):
    """Market status response."""

    is_open: bool = Field(..., description="Whether market is currently open for trading")
    current_session: str = Field(..., description="Current market session: pre, regular, post, or closed")
    next_open: str | None = Field(None, description="Next market open time (ISO format)")
    next_close: str | None = Field(None, description="Next market close time (ISO format)")
    timestamp: str = Field(..., description="Current timestamp (ISO format)")


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
        logger.error(
            "Symbol search failed", query=q, error=str(e), error_type=type(e).__name__
        )
        raise HTTPException(
            status_code=500, detail=f"Symbol search failed: {str(e)}"
        ) from e


@router.get("/price/{symbol}", response_model=PriceDataResponse)
async def get_price_data(
    symbol: str,
    user_id: str = Depends(get_current_user_id),
    service: AlphaVantageMarketDataService = Depends(get_market_service),
    redis_cache: RedisCache = Depends(get_redis),
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

        # Validate custom date range if provided
        if start_date or end_date:
            is_valid, error_msg = validate_date_range(start_date, end_date, interval)
            if not is_valid:
                raise ValueError(error_msg)

        logger.info(
            "Price data request",
            symbol=symbol,
            interval=interval,
            period=period,
            start_date=start_date,
            end_date=end_date,
            user_id=user_id,
        )

        # Generate cache key
        cache_key = f"price:{symbol}:{interval}:{period}"
        if start_date or end_date:
            cache_key += f":{start_date or 'none'}:{end_date or 'none'}"

        # Check cache first
        cached_response = await redis_cache.get(cache_key)
        if cached_response is not None:
            logger.info(
                "Price data cache hit",
                symbol=symbol,
                interval=interval,
                user_id=user_id,
            )
            return PriceDataResponse(**cached_response)

        logger.info(
            "Price data cache miss, fetching from API",
            symbol=symbol,
            interval=interval,
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
            # Note: "1h" is an alias for "60m" but already in the intraday list
            if interval in ["1m", "5m", "15m", "30m", "60m", "1h"]:
                # Intraday: use full timestamp and add market session indicator
                time_str = index.strftime("%Y-%m-%dT%H:%M:%S")
                market_session = get_market_session(index)
            else:
                # Daily+: use date only, no market session indicator
                time_str = index.strftime("%Y-%m-%d")
                market_session = None

            price_point = PriceDataPoint(
                time=time_str,
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=int(row["Volume"]) if not pd.isna(row["Volume"]) else 0,
                market_session=market_session,
            )
            price_points.append(price_point)

        logger.info(
            "Price data fetched successfully",
            symbol=symbol,
            bars_count=len(price_points),
            interval=interval,
        )

        response = PriceDataResponse(
            symbol=symbol,
            interval=interval,
            data=price_points,
            last_updated=datetime.now().isoformat(),
        )

        # Cache with interval-appropriate TTL
        # 1m: 60s, 5m: 300s, 15m: 900s, 1h: 3600s, 1d+: 3600s
        ttl_map = {
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "30m": 1800,
            "60m": 3600,
            "1h": 3600,
            "1d": 3600,
            "1wk": 3600,
            "1mo": 3600,
        }
        ttl = ttl_map.get(interval, 3600)
        await redis_cache.set(cache_key, response.model_dump(), ttl_seconds=ttl)

        logger.info(
            "Price data cached",
            symbol=symbol,
            interval=interval,
            ttl_seconds=ttl,
        )

        return response

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


@router.get("/status", response_model=MarketStatusResponse)
async def get_market_status(
    user_id: str = Depends(get_current_user_id),
) -> MarketStatusResponse:
    """
    Get current market status (open/closed, current session).

    Returns real-time market hours status for UI controls and intraday trading restrictions.

    Market hours (US Eastern Time):
    - Pre-market: 4:00 AM - 9:30 AM
    - Regular: 9:30 AM - 4:00 PM
    - Post-market: 4:00 PM - 8:00 PM
    - Closed: 8:00 PM - 4:00 AM, weekends
    """
    try:
        # Get current time in Eastern Time
        now = pd.Timestamp.now(tz='America/New_York')

        # Get current session
        current_session = get_market_session(now)
        is_open = current_session in ["pre", "regular", "post"]

        # Calculate next open/close times
        next_open = None
        next_close = None

        if current_session == "closed":
            # If closed, calculate when market opens next
            # If weekend, next open is Monday 4:00 AM ET
            # If weeknight (after 8 PM), next open is tomorrow 4:00 AM ET
            if now.weekday() >= 5:  # Weekend
                days_until_monday = (7 - now.weekday()) % 7
                if days_until_monday == 0:
                    days_until_monday = 1  # If Sunday, next Monday
                next_open_dt = now + timedelta(days=days_until_monday)
                next_open_dt = next_open_dt.replace(hour=4, minute=0, second=0, microsecond=0)
            else:  # Weeknight
                next_open_dt = now + timedelta(days=1)
                next_open_dt = next_open_dt.replace(hour=4, minute=0, second=0, microsecond=0)

            next_open = next_open_dt.isoformat()

        elif current_session == "pre":
            # Pre-market: next close is 9:30 AM (when regular opens)
            # But we consider "close" as market close at 4 PM
            next_close_dt = now.replace(hour=16, minute=0, second=0, microsecond=0)
            next_close = next_close_dt.isoformat()

        elif current_session == "regular":
            # Regular hours: next close is 4:00 PM
            next_close_dt = now.replace(hour=16, minute=0, second=0, microsecond=0)
            next_close = next_close_dt.isoformat()

        elif current_session == "post":
            # Post-market: next close is 8:00 PM
            next_close_dt = now.replace(hour=20, minute=0, second=0, microsecond=0)
            next_close = next_close_dt.isoformat()

        logger.info(
            "Market status checked",
            user_id=user_id,
            current_session=current_session,
            is_open=is_open,
        )

        return MarketStatusResponse(
            is_open=is_open,
            current_session=current_session,
            next_open=next_open,
            next_close=next_close,
            timestamp=now.isoformat(),
        )

    except Exception as e:
        logger.error("Market status check failed", error=str(e), error_type=type(e).__name__)
        raise HTTPException(
            status_code=500, detail=f"Failed to check market status: {str(e)}"
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
            "exchange": (
                matching_asset.exchange.value
                if hasattr(matching_asset.exchange, "value")
                else str(matching_asset.exchange)
            ),
            "type": (
                matching_asset.asset_class.value
                if hasattr(matching_asset.asset_class, "value")
                else "EQUITY"
            ),
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("Symbol info fetch failed", symbol=symbol, error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch symbol info: {str(e)}"
        ) from e


@router.get("/overview/{symbol}")
async def get_company_overview(
    symbol: str,
    user_id: str = Depends(get_current_user_id),
    service: AlphaVantageMarketDataService = Depends(get_market_service),
) -> dict:
    """
    Get comprehensive company overview and fundamentals.

    Returns raw Alpha Vantage OVERVIEW response including:
    - Company info (Symbol, Name, Description, Exchange, Currency)
    - Market metrics (MarketCapitalization, EBITDA, PERatio, EPS)
    - Financial ratios (ProfitMargin, RevenuePerShareTTM, DividendYield)
    - Price metrics (52WeekHigh, 52WeekLow, Beta, MovingAverages)
    """
    try:
        symbol = symbol.upper().strip()
        if not symbol:
            raise ValueError("Symbol is required")

        logger.info("Company overview request", symbol=symbol, user_id=user_id)

        data = await service.get_company_overview(symbol)

        logger.info(
            "Company overview fetched", symbol=symbol, company_name=data.get("Name")
        )

        return data

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("Company overview fetch failed", symbol=symbol, error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch company overview: {str(e)}"
        ) from e


@router.get("/news-sentiment/{symbol}")
async def get_news_sentiment(
    symbol: str,
    user_id: str = Depends(get_current_user_id),
    service: AlphaVantageMarketDataService = Depends(get_market_service),
    limit: int = Query(50, ge=1, le=1000, description="Max news items (1-1000)"),
    sort: str = Query(
        "LATEST", description="Sort order: LATEST | EARLIEST | RELEVANCE"
    ),
) -> dict:
    """
    Get news articles with sentiment analysis for a stock.

    Returns news feed with:
    - Title, URL, published time, summary, source
    - Overall sentiment score and label (Bullish/Bearish/Neutral)
    - Ticker-specific sentiment scores
    - Relevance scores
    """
    try:
        symbol = symbol.upper().strip()
        if not symbol:
            raise ValueError("Symbol is required")

        logger.info(
            "News sentiment request", symbol=symbol, user_id=user_id, limit=limit
        )

        data = await service.get_news_sentiment(tickers=symbol, limit=limit, sort=sort)

        logger.info(
            "News sentiment fetched",
            symbol=symbol,
            news_count=len(data.get("feed", [])),
        )

        return data

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("News sentiment fetch failed", symbol=symbol, error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch news sentiment: {str(e)}"
        ) from e


@router.get("/cash-flow/{symbol}")
async def get_cash_flow(
    symbol: str,
    user_id: str = Depends(get_current_user_id),
    service: AlphaVantageMarketDataService = Depends(get_market_service),
) -> dict:
    """
    Get cash flow statements (annual and quarterly).

    Returns:
    - annualReports: List of annual cash flow statements
    - quarterlyReports: List of quarterly cash flow statements

    Each report includes:
    - operatingCashflow, capitalExpenditures
    - cashflowFromInvestment, cashflowFromFinancing
    - dividendPayout, changeInCashAndCashEquivalents
    """
    try:
        symbol = symbol.upper().strip()
        if not symbol:
            raise ValueError("Symbol is required")

        logger.info("Cash flow request", symbol=symbol, user_id=user_id)

        data = await service.get_cash_flow(symbol)

        logger.info(
            "Cash flow fetched",
            symbol=symbol,
            annual_count=len(data.get("annualReports", [])),
            quarterly_count=len(data.get("quarterlyReports", [])),
        )

        return data

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("Cash flow fetch failed", symbol=symbol, error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch cash flow: {str(e)}"
        ) from e


@router.get("/balance-sheet/{symbol}")
async def get_balance_sheet(
    symbol: str,
    user_id: str = Depends(get_current_user_id),
    service: AlphaVantageMarketDataService = Depends(get_market_service),
) -> dict:
    """
    Get balance sheet statements (annual and quarterly).

    Returns:
    - annualReports: List of annual balance sheets
    - quarterlyReports: List of quarterly balance sheets

    Each report includes:
    - totalAssets, totalLiabilities, totalShareholderEquity
    - cash, currentDebt, longTermDebt
    - inventory, goodwill, intangibleAssets
    """
    try:
        symbol = symbol.upper().strip()
        if not symbol:
            raise ValueError("Symbol is required")

        logger.info("Balance sheet request", symbol=symbol, user_id=user_id)

        data = await service.get_balance_sheet(symbol)

        logger.info(
            "Balance sheet fetched",
            symbol=symbol,
            annual_count=len(data.get("annualReports", [])),
            quarterly_count=len(data.get("quarterlyReports", [])),
        )

        return data

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("Balance sheet fetch failed", symbol=symbol, error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch balance sheet: {str(e)}"
        ) from e


@router.get("/market-movers")
async def get_market_movers(
    user_id: str = Depends(get_current_user_id),
    service: AlphaVantageMarketDataService = Depends(get_market_service),
    redis_cache: RedisCache = Depends(get_redis),
) -> dict:
    """
    Get today's top market movers with 30-minute caching.

    Returns:
    - top_gainers: Top 20 stocks with highest price increase (% and $)
    - top_losers: Top 20 stocks with largest price decrease (% and $)
    - most_actively_traded: Top 20 stocks by trading volume

    Each entry includes: ticker, price, change_amount, change_percentage, volume

    Cache Duration: 30 minutes (configured in cache_utils.py)
    - Market movers change throughout trading day but not every second
    - 30-min refresh balances freshness vs API efficiency
    - Reduces Alpha Vantage API calls by 12x per 6-hour period
    """
    try:
        logger.info("Market movers request", user_id=user_id)

        # Generate cache key
        cache_key = "market_movers:top_gainers_losers"

        # Check cache first
        cached_data = await redis_cache.get(cache_key)
        if cached_data is not None:
            logger.info("Market movers cache hit", user_id=user_id)
            return cached_data

        logger.info("Market movers cache miss, fetching from API", user_id=user_id)

        # Fetch from Alpha Vantage API
        data = await service.get_top_gainers_losers()

        # Cache with 30-minute TTL (configured in TOOL_TTL_MAP)
        ttl = get_tool_ttl("TOP_GAINERS_LOSERS")  # Returns 1800 seconds (30 minutes)
        await redis_cache.set(cache_key, data, ttl_seconds=ttl)

        logger.info(
            "Market movers fetched and cached",
            gainers_count=len(data.get("top_gainers", [])),
            losers_count=len(data.get("top_losers", [])),
            active_count=len(data.get("most_actively_traded", [])),
            ttl_seconds=ttl,
        )

        return data

    except Exception as e:
        logger.error("Market movers fetch failed", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch market movers: {str(e)}"
        ) from e
