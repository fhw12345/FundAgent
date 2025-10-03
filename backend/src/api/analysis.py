"""
Financial Analysis API endpoints.
Provides REST API access to core financial analysis functionality.
"""

import time
from datetime import datetime, date
from typing import Optional

import structlog
from fastapi import APIRouter, HTTPException, Depends

from ..core.financial_analysis import FibonacciAnalyzer, MacroAnalyzer, StockAnalyzer, StochasticAnalyzer
from ..database.redis import RedisCache
from .health import get_redis
from .models import (
    FibonacciAnalysisRequest,
    FibonacciAnalysisResponse,
    MacroAnalysisRequest,
    MacroSentimentResponse,
    StockFundamentalsRequest,
    StockFundamentalsResponse,
    StochasticAnalysisRequest,
    StochasticAnalysisResponse,
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


logger = structlog.get_logger()
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
    request_start_time = time.time()

    # Log incoming request details
    logger.info(
        "Fibonacci analysis request received",
        symbol=request.symbol,
        start_date=request.start_date,
        end_date=request.end_date,
        timeframe=request.timeframe,
        include_chart=request.include_chart
    )

    try:
        # Validate date range first
        validate_date_range(request.start_date, request.end_date)

        # Require both start and end dates for Fibonacci analysis
        if not request.start_date or not request.end_date:
            logger.error(
                "Fibonacci analysis request failed - missing date range",
                symbol=request.symbol,
                start_date=request.start_date,
                end_date=request.end_date
            )
            raise ValueError("Both start_date and end_date are required for Fibonacci analysis")

        # Check cache first
        cache_start_time = time.time()
        cache_key = f"fibonacci:{request.symbol}:{request.start_date}:{request.end_date}:{request.timeframe}"

        logger.info(
            "Checking cache for Fibonacci analysis",
            cache_key=cache_key,
            symbol=request.symbol
        )

        cached_result = await redis_cache.get(cache_key)
        cache_check_duration = time.time() - cache_start_time

        if cached_result:
            total_duration = time.time() - request_start_time
            logger.info(
                "Fibonacci analysis cache HIT - returning cached result",
                symbol=request.symbol,
                cache_key=cache_key,
                cache_check_duration_ms=round(cache_check_duration * 1000, 2),
                total_duration_ms=round(total_duration * 1000, 2)
            )
            return FibonacciAnalysisResponse.model_validate(cached_result)

        logger.info(
            "Fibonacci analysis cache MISS - proceeding with calculation",
            symbol=request.symbol,
            cache_key=cache_key,
            cache_check_duration_ms=round(cache_check_duration * 1000, 2)
        )

        # Perform analysis with timeframe parameter
        analysis_start_time = time.time()
        logger.info(
            "Starting Fibonacci analysis calculation",
            symbol=request.symbol,
            timeframe=request.timeframe,
            date_range_days=(datetime.strptime(request.end_date, "%Y-%m-%d") - datetime.strptime(request.start_date, "%Y-%m-%d")).days
        )

        analyzer = FibonacciAnalyzer()
        result = await analyzer.analyze(
            symbol=request.symbol,
            start_date=request.start_date,
            end_date=request.end_date,
            timeframe=request.timeframe
        )

        analysis_duration = time.time() - analysis_start_time
        logger.info(
            "Fibonacci analysis calculation completed",
            symbol=result.symbol,
            timeframe=result.timeframe,
            confidence_score=result.confidence_score,
            fibonacci_levels_count=len(result.fibonacci_levels),
            analysis_duration_ms=round(analysis_duration * 1000, 2)
        )

        # Cache the result for 5 minutes
        cache_store_start_time = time.time()
        await redis_cache.set(cache_key, result.model_dump(), ttl_seconds=300)
        cache_store_duration = time.time() - cache_store_start_time

        total_duration = time.time() - request_start_time
        logger.info(
            "Fibonacci analysis request completed successfully",
            symbol=result.symbol,
            cache_key=cache_key,
            cache_stored=True,
            cache_ttl_seconds=300,
            cache_store_duration_ms=round(cache_store_duration * 1000, 2),
            analysis_duration_ms=round(analysis_duration * 1000, 2),
            total_duration_ms=round(total_duration * 1000, 2)
        )

        return result

    except ValueError as e:
        total_duration = time.time() - request_start_time
        logger.error(
            "Fibonacci analysis request failed - invalid input",
            symbol=request.symbol,
            error=str(e),
            total_duration_ms=round(total_duration * 1000, 2)
        )
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
    except Exception as e:
        total_duration = time.time() - request_start_time
        logger.error(
            "Fibonacci analysis request failed - unexpected error",
            symbol=request.symbol,
            error=str(e),
            error_type=type(e).__name__,
            total_duration_ms=round(total_duration * 1000, 2)
        )
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


@router.post("/stochastic", response_model=StochasticAnalysisResponse)
async def stochastic_analysis(
    request: StochasticAnalysisRequest,
    redis_cache: RedisCache = Depends(get_redis),
) -> StochasticAnalysisResponse:
    """
    Perform Stochastic Oscillator technical analysis on a stock symbol.

    Analyzes overbought/oversold conditions, crossover signals, and potential
    reversals using the Stochastic Oscillator indicator.
    """
    request_start_time = time.time()

    # Log incoming request details
    logger.info(
        "Stochastic analysis request received",
        symbol=request.symbol,
        start_date=request.start_date,
        end_date=request.end_date,
        timeframe=request.timeframe,
        k_period=request.k_period,
        d_period=request.d_period
    )

    try:
        # Validate date range if provided
        validate_date_range(request.start_date, request.end_date)

        # Check cache first
        cache_start_time = time.time()
        cache_key = f"stochastic:{request.symbol}:{request.start_date}:{request.end_date}:{request.timeframe}:{request.k_period}:{request.d_period}"

        logger.info(
            "Checking cache for Stochastic analysis",
            cache_key=cache_key,
            symbol=request.symbol
        )

        cached_result = await redis_cache.get(cache_key)
        cache_check_duration = time.time() - cache_start_time

        if cached_result:
            total_duration = time.time() - request_start_time
            logger.info(
                "Stochastic analysis cache HIT - returning cached result",
                symbol=request.symbol,
                cache_key=cache_key,
                cache_check_duration_ms=round(cache_check_duration * 1000, 2),
                total_duration_ms=round(total_duration * 1000, 2)
            )
            return StochasticAnalysisResponse.model_validate(cached_result)

        logger.info(
            "Stochastic analysis cache MISS - proceeding with calculation",
            symbol=request.symbol,
            cache_key=cache_key,
            cache_check_duration_ms=round(cache_check_duration * 1000, 2)
        )

        # Perform analysis
        analysis_start_time = time.time()
        logger.info(
            "Starting Stochastic analysis calculation",
            symbol=request.symbol,
            timeframe=request.timeframe,
            k_period=request.k_period,
            d_period=request.d_period
        )

        # Initialize TickerDataService and analyzer
        from ..core.data.ticker_data_service import TickerDataService
        ticker_service = TickerDataService(redis_cache)
        analyzer = StochasticAnalyzer(ticker_service)

        result = await analyzer.analyze(
            symbol=request.symbol,
            start_date=request.start_date,
            end_date=request.end_date,
            timeframe=request.timeframe,
            k_period=request.k_period,
            d_period=request.d_period
        )

        analysis_duration = time.time() - analysis_start_time
        logger.info(
            "Stochastic analysis calculation completed",
            symbol=result.symbol,
            timeframe=result.timeframe,
            current_signal=result.current_signal,
            k_value=result.current_k,
            d_value=result.current_d,
            analysis_duration_ms=round(analysis_duration * 1000, 2)
        )

        # Cache the result for 5 minutes (same as technical indicators)
        cache_store_start_time = time.time()
        await redis_cache.set(cache_key, result.model_dump(), ttl_seconds=300)
        cache_store_duration = time.time() - cache_store_start_time

        total_duration = time.time() - request_start_time
        logger.info(
            "Stochastic analysis request completed successfully",
            symbol=result.symbol,
            cache_key=cache_key,
            cache_stored=True,
            cache_ttl_seconds=300,
            cache_store_duration_ms=round(cache_store_duration * 1000, 2),
            analysis_duration_ms=round(analysis_duration * 1000, 2),
            total_duration_ms=round(total_duration * 1000, 2)
        )

        return result

    except ValueError as e:
        total_duration = time.time() - request_start_time
        logger.error(
            "Stochastic analysis request failed - invalid input",
            symbol=request.symbol,
            error=str(e),
            total_duration_ms=round(total_duration * 1000, 2)
        )
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
    except Exception as e:
        total_duration = time.time() - request_start_time
        logger.error(
            "Stochastic analysis request failed - unexpected error",
            symbol=request.symbol,
            error=str(e),
            error_type=type(e).__name__,
            total_duration_ms=round(total_duration * 1000, 2)
        )
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


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


