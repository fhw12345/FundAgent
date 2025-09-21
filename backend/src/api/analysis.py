"""
Financial Analysis API endpoints.
Provides REST API access to core financial analysis functionality.
"""

from datetime import datetime, date
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends

from ..core.financial_analysis import FibonacciAnalyzer, MacroAnalyzer, StockAnalyzer
from ..database.redis import RedisCache
from .health import get_redis
from .models import (
    FibonacciAnalysisRequest,
    FibonacciAnalysisResponse,
    MacroAnalysisRequest,
    MacroSentimentResponse,
    StockFundamentalsRequest,
    StockFundamentalsResponse,
    ChartRequest,
    ChartGenerationResponse,
    ErrorResponse,
)

def validate_date_range(start_date: Optional[str], end_date: Optional[str]) -> None:
    """
    Validate date range inputs.

    Raises:
        ValueError: If dates are invalid or in the future
    """
    today = date.today()

    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
            if start_dt > today:
                raise ValueError(f"Start date {start_date} cannot be in the future. Latest allowed date is {today}")
        except ValueError as e:
            if "cannot be in the future" in str(e):
                raise
            raise ValueError(f"Invalid start date format: {start_date}. Expected YYYY-MM-DD")

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
            if end_dt > today:
                raise ValueError(f"End date {end_date} cannot be in the future. Latest allowed date is {today}")
        except ValueError as e:
            if "cannot be in the future" in str(e):
                raise
            raise ValueError(f"Invalid end date format: {end_date}. Expected YYYY-MM-DD")

    if start_date and end_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        if start_dt > end_dt:
            raise ValueError(f"Start date {start_date} cannot be after end date {end_date}")

        # Check if date range is too long (more than 5 years)
        if (end_dt - start_dt).days > 5 * 365:
            raise ValueError(f"Date range is too long. Maximum allowed range is 5 years")


router = APIRouter(prefix="/api/analysis", tags=["Financial Analysis"])


@router.post("/fibonacci", response_model=FibonacciAnalysisResponse)
async def fibonacci_analysis(
    request: FibonacciAnalysisRequest,
    redis_cache: RedisCache = Depends(get_redis),
) -> FibonacciAnalysisResponse:
    """
    Perform Fibonacci retracement analysis on a stock symbol.

    This endpoint analyzes market structure and calculates Fibonacci retracement levels
    for the specified stock symbol and date range.
    """
    try:
        # Validate date range first
        validate_date_range(request.start_date, request.end_date)

        # Check cache first
        cache_key = f"fibonacci:{request.symbol}:{request.start_date}:{request.end_date}"
        cached_result = await redis_cache.get(cache_key)
        if cached_result:
            return FibonacciAnalysisResponse.model_validate(cached_result)

        # Perform analysis
        analyzer = FibonacciAnalyzer()
        result = await analyzer.analyze(
            symbol=request.symbol,
            start_date=request.start_date,
            end_date=request.end_date
        )

        # Cache the result for 5 minutes
        await redis_cache.set(cache_key, result.model_dump(), ttl_seconds=300)

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/macro", response_model=MacroSentimentResponse)
async def macro_sentiment_analysis(
    request: MacroAnalysisRequest,
    redis_cache: RedisCache = Depends(get_redis),
) -> MacroSentimentResponse:
    """
    Analyze macro market sentiment using VIX, major indices, and sector performance.

    Provides fear/greed analysis and overall market outlook based on current conditions.
    """
    try:
        # Check cache first (shorter cache time for macro data)
        cache_key = f"macro:{request.include_sectors}:{request.include_indices}"
        cached_result = await redis_cache.get(cache_key)
        if cached_result:
            return MacroSentimentResponse.model_validate(cached_result)

        # Perform analysis
        analyzer = MacroAnalyzer()
        result = await analyzer.analyze(
            include_sectors=request.include_sectors,
            include_indices=request.include_indices
        )

        # Cache for 2 minutes (macro data changes frequently)
        await redis_cache.set(cache_key, result.model_dump(), ttl_seconds=120)

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Macro analysis failed: {str(e)}")


@router.post("/fundamentals", response_model=StockFundamentalsResponse)
async def stock_fundamentals(
    request: StockFundamentalsRequest,
    redis_cache: RedisCache = Depends(get_redis),
) -> StockFundamentalsResponse:
    """
    Get comprehensive fundamental analysis for a stock symbol.

    Includes valuation metrics, financial health indicators, and market data.
    """
    try:
        # Check cache first
        cache_key = f"fundamentals:{request.symbol}"
        cached_result = await redis_cache.get(cache_key)
        if cached_result:
            return StockFundamentalsResponse.model_validate(cached_result)

        # Perform analysis
        analyzer = StockAnalyzer()
        result = await analyzer.get_fundamentals(symbol=request.symbol)

        # Cache for 30 minutes (fundamental data doesn't change frequently)
        await redis_cache.set(cache_key, result.model_dump(), ttl_seconds=1800)

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid symbol: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fundamentals analysis failed: {str(e)}")


@router.post("/chart", response_model=ChartGenerationResponse)
async def generate_chart(
    request: ChartRequest,
    redis_cache: RedisCache = Depends(get_redis),
) -> ChartGenerationResponse:
    """
    Generate a financial chart for the specified symbol and type.

    Supports various chart types including price, Fibonacci, and volume charts.
    Chart generation happens asynchronously for better performance.
    """
    try:
        # Validate date range first
        validate_date_range(request.start_date, request.end_date)

        # For now, return chart data structure that frontend can use
        # Chart image generation will be implemented in next phase
        chart_data = {
            "symbol": request.symbol,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "chart_type": request.chart_type,
            "includes_indicators": request.include_indicators,
            "data_points": [],  # Will be populated with actual chart data
            "generated_at": datetime.now().isoformat(),
        }

        result = ChartGenerationResponse(
            symbol=request.symbol,
            chart_type=request.chart_type,
            chart_url=None,  # Will be set when image generation is implemented
            chart_data=chart_data,
            generation_date=datetime.now().isoformat(),
            success=True,
        )

        # Chart data returned for frontend use

        return result

    except Exception as e:
        return ChartGenerationResponse(
            symbol=request.symbol,
            chart_type=request.chart_type,
            chart_url=None,
            chart_data={},
            generation_date=datetime.now().isoformat(),
            success=False,
            error_message=str(e),
        )


