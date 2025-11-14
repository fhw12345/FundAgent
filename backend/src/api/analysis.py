"""
Financial Analysis API endpoints.
Provides REST API access to core financial analysis functionality.
"""

import time
from datetime import date, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException

from ..core.config import get_settings
from ..core.financial_analysis import (
    FibonacciAnalyzer,
    MacroAnalyzer,
    StochasticAnalyzer,
)
from ..database.redis import RedisCache
from ..services.alphavantage_market_data import AlphaVantageMarketDataService
from .dependencies.auth import get_current_user_id
from .health import get_redis
from .models import (
    BalanceSheetResponse,
    CashFlowResponse,
    ChartGenerationResponse,
    ChartRequest,
    CompanyOverviewResponse,
    FibonacciAnalysisRequest,
    FibonacciAnalysisResponse,
    MacroAnalysisRequest,
    MacroSentimentResponse,
    MarketMover,
    MarketMoversResponse,
    NewsArticle,
    NewsSentimentResponse,
    StochasticAnalysisRequest,
    StochasticAnalysisResponse,
    StockFundamentalsRequest,
    StockFundamentalsResponse,
    ToolCall,
)

# Tool Registry for UI Metadata
TOOL_REGISTRY = {
    "fibonacci": {"title": "Fibonacci Analysis", "icon": "📊"},
    "macro": {"title": "Macro Sentiment", "icon": "🌍"},
    "company_overview": {"title": "Company Overview", "icon": "🏢"},
    "stochastic": {"title": "Stochastic Oscillator", "icon": "📈"},
    "cash_flow": {"title": "Cash Flow", "icon": "💵"},
    "balance_sheet": {"title": "Balance Sheet", "icon": "📋"},
    "news_sentiment": {"title": "News Sentiment", "icon": "📰"},
    "market_movers": {"title": "Market Movers", "icon": "🔥"},
}


def create_tool_call(
    tool_name: str, symbol: str | None = None, **metadata: Any
) -> ToolCall:
    """
    Helper to create ToolCall object with metadata from registry.

    Args:
        tool_name: Tool identifier (e.g., 'company_overview')
        symbol: Stock symbol if applicable (e.g., 'TSLA')
        **metadata: Additional tool-specific data

    Returns:
        ToolCall object with title, icon, and metadata populated
    """
    tool_info = TOOL_REGISTRY.get(tool_name, {"title": tool_name, "icon": "🔧"})
    return ToolCall(
        tool_name=tool_name,
        title=tool_info["title"],
        icon=tool_info["icon"],
        symbol=symbol,
        metadata=metadata,
    )


def get_market_service() -> AlphaVantageMarketDataService:
    """Dependency to get market data service from app state."""
    from ..main import app

    market_service: AlphaVantageMarketDataService = app.state.market_service
    return market_service


def validate_date_range(start_date: str | None, end_date: str | None) -> None:
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
                raise ValueError(
                    f"Start date {start_date} cannot be in the future. Latest allowed date is {today}"
                )
        except ValueError as e:
            if "cannot be in the future" in str(e):
                raise
            raise ValueError(
                f"Invalid start date format: {start_date}. Expected YYYY-MM-DD"
            ) from None

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
            if end_dt > today:
                raise ValueError(
                    f"End date {end_date} cannot be in the future. Latest allowed date is {today}"
                )
        except ValueError as e:
            if "cannot be in the future" in str(e):
                raise
            raise ValueError(
                f"Invalid end date format: {end_date}. Expected YYYY-MM-DD"
            ) from None

    if start_date and end_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        if start_dt > end_dt:
            raise ValueError(
                f"Start date {start_date} cannot be after end date {end_date}"
            )

        # Check if date range is too long (more than 5 years)
        if (end_dt - start_dt).days > 5 * 365:
            raise ValueError("Date range is too long. Maximum allowed range is 5 years")


logger = structlog.get_logger()
router = APIRouter(prefix="/api/analysis", tags=["Financial Analysis"])


@router.post("/fibonacci", response_model=FibonacciAnalysisResponse)
async def fibonacci_analysis(
    request: FibonacciAnalysisRequest,
    user_id: str = Depends(get_current_user_id),
    redis_cache: RedisCache = Depends(get_redis),
    market_service: AlphaVantageMarketDataService = Depends(get_market_service),
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
        include_chart=request.include_chart,
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
                end_date=request.end_date,
            )
            raise ValueError(
                "Both start_date and end_date are required for Fibonacci analysis"
            )

        # Check cache first
        cache_start_time = time.time()
        cache_key = f"fibonacci:{request.symbol}:{request.start_date}:{request.end_date}:{request.timeframe}"

        logger.info(
            "Checking cache for Fibonacci analysis",
            cache_key=cache_key,
            symbol=request.symbol,
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
                total_duration_ms=round(total_duration * 1000, 2),
            )
            return FibonacciAnalysisResponse.model_validate(cached_result)

        logger.info(
            "Fibonacci analysis cache MISS - proceeding with calculation",
            symbol=request.symbol,
            cache_key=cache_key,
            cache_check_duration_ms=round(cache_check_duration * 1000, 2),
        )

        # Perform analysis with timeframe parameter
        analysis_start_time = time.time()
        logger.info(
            "Starting Fibonacci analysis calculation",
            symbol=request.symbol,
            timeframe=request.timeframe,
            date_range_days=(
                datetime.strptime(request.end_date, "%Y-%m-%d")
                - datetime.strptime(request.start_date, "%Y-%m-%d")
            ).days,
        )

        analyzer = FibonacciAnalyzer(market_service)
        result = await analyzer.analyze(
            symbol=request.symbol,
            start_date=request.start_date,
            end_date=request.end_date,
            timeframe=request.timeframe,
        )

        analysis_duration = time.time() - analysis_start_time
        logger.info(
            "Fibonacci analysis calculation completed",
            symbol=result.symbol,
            timeframe=result.timeframe,
            confidence_score=result.confidence_score,
            fibonacci_levels_count=len(result.fibonacci_levels),
            analysis_duration_ms=round(analysis_duration * 1000, 2),
        )

        # Cache for 1 hour - Fibonacci levels don't change significantly intraday
        # Date-based cache key ensures data refreshes daily
        cache_store_start_time = time.time()
        await redis_cache.set(cache_key, result.model_dump(), ttl_seconds=3600)
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
            total_duration_ms=round(total_duration * 1000, 2),
        )

        return result

    except ValueError as e:
        total_duration = time.time() - request_start_time
        logger.error(
            "Fibonacci analysis request failed - invalid input",
            symbol=request.symbol,
            error=str(e),
            total_duration_ms=round(total_duration * 1000, 2),
        )
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}") from e
    except Exception as e:
        total_duration = time.time() - request_start_time
        logger.error(
            "Fibonacci analysis request failed - unexpected error",
            symbol=request.symbol,
            error=str(e),
            error_type=type(e).__name__,
            total_duration_ms=round(total_duration * 1000, 2),
        )
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}") from e


@router.post("/macro", response_model=MacroSentimentResponse)
async def macro_sentiment_analysis(
    request: MacroAnalysisRequest,
    user_id: str = Depends(get_current_user_id),
    redis_cache: RedisCache = Depends(get_redis),
) -> MacroSentimentResponse:
    """
    Analyze macro market sentiment using VIX, major indices, and sector performance.

    Provides fear/greed analysis and overall market outlook based on current conditions.
    """
    try:
        # Check cache first (shorter cache time for macro data)
        # Include date to prevent serving stale data from previous day
        from datetime import UTC, datetime

        current_date = datetime.now(UTC).strftime("%Y-%m-%d")
        cache_key = (
            f"macro:{current_date}:{request.include_sectors}:{request.include_indices}"
        )
        cached_result = await redis_cache.get(cache_key)
        if cached_result:
            return MacroSentimentResponse.model_validate(cached_result)

        # Perform analysis
        analyzer = MacroAnalyzer()
        result = await analyzer.analyze(
            include_sectors=request.include_sectors,
            include_indices=request.include_indices,
        )

        # Cache for 1 hour - Macro sentiment provides daily market overview
        # Date-based cache key ensures fresh data each day
        await redis_cache.set(cache_key, result.model_dump(), ttl_seconds=3600)

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Macro analysis failed: {str(e)}"
        ) from e


@router.post("/fundamentals", response_model=StockFundamentalsResponse)
async def stock_fundamentals(
    request: StockFundamentalsRequest,
    user_id: str = Depends(get_current_user_id),
    redis_cache: RedisCache = Depends(get_redis),
    market_service: AlphaVantageMarketDataService = Depends(get_market_service),
) -> StockFundamentalsResponse:
    """
    Get comprehensive fundamental analysis for a stock symbol.

    Uses Alpha Vantage COMPANY_OVERVIEW for fundamentals data.
    Includes valuation metrics, financial health indicators, and market data.
    """
    try:
        # Check cache first
        # Include date to prevent serving stale price data from previous day
        from datetime import UTC, datetime

        current_date = datetime.now(UTC).strftime("%Y-%m-%d")
        cache_key = f"fundamentals:{request.symbol}:{current_date}"
        cached_result = await redis_cache.get(cache_key)
        if cached_result:
            return StockFundamentalsResponse.model_validate(cached_result)

        logger.info("Fetching fundamentals from Alpha Vantage", symbol=request.symbol)

        # Get company overview from Alpha Vantage
        overview = await market_service.get_company_overview(request.symbol)

        if not overview or "Symbol" not in overview:
            raise ValueError(
                f"'{request.symbol}' is not a valid stock symbol or no data available. "
                "Please check the symbol and try again."
            )

        # Helper function to safely convert string to float
        def safe_float(value: str | None, default: float = 0.0) -> float:
            if not value or value == "None":
                return default
            try:
                return float(value)
            except (ValueError, TypeError):
                return default

        # Extract fundamental metrics from Alpha Vantage OVERVIEW
        symbol = overview.get("Symbol", request.symbol)
        company_name = overview.get("Name", symbol)

        # Price Data
        current_price = safe_float(
            overview.get("50DayMovingAverage")
        )  # Use MA as proxy
        fifty_two_week_high = safe_float(overview.get("52WeekHigh"), current_price)
        fifty_two_week_low = safe_float(overview.get("52WeekLow"), current_price)

        # Market Metrics
        market_cap = safe_float(overview.get("MarketCapitalization"))

        # Valuation Ratios
        pe_ratio = (
            safe_float(overview.get("PERatio"))
            if overview.get("PERatio") != "None"
            else None
        )
        forward_pe = (
            safe_float(overview.get("ForwardPE"))
            if overview.get("ForwardPE") != "None"
            else None
        )
        pb_ratio = (
            safe_float(overview.get("PriceToBookRatio"))
            if overview.get("PriceToBookRatio") != "None"
            else None
        )
        peg_ratio = (
            safe_float(overview.get("PEGRatio"))
            if overview.get("PEGRatio") != "None"
            else None
        )
        price_to_sales = (
            safe_float(overview.get("PriceToSalesRatioTTM"))
            if overview.get("PriceToSalesRatioTTM") != "None"
            else None
        )

        # Profitability Metrics
        eps = safe_float(overview.get("EPS")) if overview.get("EPS") != "None" else None
        profit_margin_decimal = safe_float(overview.get("ProfitMargin"))
        profit_margin = (
            profit_margin_decimal * 100 if profit_margin_decimal > 0 else None
        )
        operating_margin_decimal = safe_float(overview.get("OperatingMarginTTM"))
        operating_margin = (
            operating_margin_decimal * 100 if operating_margin_decimal > 0 else None
        )

        # Return Metrics
        roe_decimal = safe_float(overview.get("ReturnOnEquityTTM"))
        roe = roe_decimal * 100 if roe_decimal > 0 else None
        roa_decimal = safe_float(overview.get("ReturnOnAssetsTTM"))
        roa = roa_decimal * 100 if roa_decimal > 0 else None

        # Growth Metrics
        revenue_ttm = safe_float(overview.get("RevenueTTM"))
        quarterly_earnings_growth_decimal = safe_float(
            overview.get("QuarterlyEarningsGrowthYOY")
        )
        quarterly_earnings_growth = (
            quarterly_earnings_growth_decimal * 100
            if quarterly_earnings_growth_decimal != 0
            else None
        )
        quarterly_revenue_growth_decimal = safe_float(
            overview.get("QuarterlyRevenueGrowthYOY")
        )
        quarterly_revenue_growth = (
            quarterly_revenue_growth_decimal * 100
            if quarterly_revenue_growth_decimal != 0
            else None
        )

        # Dividend & Risk
        dividend_yield_decimal = safe_float(overview.get("DividendYield"))
        dividend_yield = (
            dividend_yield_decimal * 100 if dividend_yield_decimal > 0 else None
        )
        beta = (
            safe_float(overview.get("Beta")) if overview.get("Beta") != "None" else None
        )

        # Analyst Data
        analyst_target_price = (
            safe_float(overview.get("AnalystTargetPrice"))
            if overview.get("AnalystTargetPrice") != "None"
            else None
        )

        # Calculate price position in 52-week range
        price_range = fifty_two_week_high - fifty_two_week_low
        position_in_range = (
            ((current_price - fifty_two_week_low) / price_range * 100)
            if price_range > 0
            else 50
        )

        # Market cap classification
        if market_cap > 200_000_000_000:
            cap_class = "mega-cap"
        elif market_cap > 10_000_000_000:
            cap_class = "large-cap"
        elif market_cap > 2_000_000_000:
            cap_class = "mid-cap"
        elif market_cap > 300_000_000:
            cap_class = "small-cap"
        else:
            cap_class = "micro-cap"

        # Generate summary
        summary = (
            f"{symbol} is a {cap_class} stock trading at ${current_price:.2f}, "
            f"which is {position_in_range:.1f}% of its 52-week range. "
        )

        if market_cap > 0:
            summary += f"Market cap: ${market_cap/1e9:.1f}B. "

        key_metrics = [
            f"52-Week Range: ${fifty_two_week_low:.2f} - ${fifty_two_week_high:.2f}",
            f"Position in Range: {position_in_range:.1f}%",
            f"Market Cap Class: {cap_class.title()}",
        ]

        # Valuation Ratios Section
        if pe_ratio is not None and pe_ratio > 0:
            pe_interpretation = (
                "expensive"
                if pe_ratio > 25
                else "reasonable" if pe_ratio > 15 else "cheap"
            )
            key_metrics.append(f"P/E Ratio (TTM): {pe_ratio:.2f} ({pe_interpretation})")
            summary += (
                f"P/E ratio of {pe_ratio:.2f} suggests {pe_interpretation} valuation. "
            )

        if forward_pe is not None and forward_pe > 0:
            key_metrics.append(f"Forward P/E: {forward_pe:.2f}")

        if pb_ratio is not None and pb_ratio > 0:
            pb_interpretation = (
                "premium" if pb_ratio > 3 else "fair" if pb_ratio > 1 else "discount"
            )
            key_metrics.append(f"P/B Ratio: {pb_ratio:.2f} ({pb_interpretation})")

        if peg_ratio is not None and peg_ratio > 0:
            peg_interpretation = (
                "attractive"
                if peg_ratio < 1
                else "fair" if peg_ratio < 2 else "expensive"
            )
            key_metrics.append(f"PEG Ratio: {peg_ratio:.2f} ({peg_interpretation})")

        if price_to_sales is not None and price_to_sales > 0:
            key_metrics.append(f"Price/Sales (TTM): {price_to_sales:.2f}")

        # Profitability Section
        if eps is not None:
            key_metrics.append(f"EPS (TTM): ${eps:.2f}")

        if profit_margin is not None:
            margin_quality = (
                "excellent"
                if profit_margin > 20
                else "good" if profit_margin > 10 else "moderate"
            )
            key_metrics.append(
                f"Profit Margin: {profit_margin:.1f}% ({margin_quality})"
            )

        if operating_margin is not None:
            key_metrics.append(f"Operating Margin: {operating_margin:.1f}%")

        # Return Metrics Section
        if roe is not None:
            roe_quality = "strong" if roe > 15 else "average" if roe > 10 else "weak"
            key_metrics.append(f"Return on Equity: {roe:.1f}% ({roe_quality})")

        if roa is not None:
            key_metrics.append(f"Return on Assets: {roa:.1f}%")

        # Growth Metrics Section
        if revenue_ttm > 0:
            key_metrics.append(f"Revenue (TTM): ${revenue_ttm/1e9:.2f}B")

        if quarterly_earnings_growth is not None:
            growth_trend = "growing" if quarterly_earnings_growth > 0 else "declining"
            key_metrics.append(
                f"Q Earnings Growth YoY: {quarterly_earnings_growth:+.1f}% ({growth_trend})"
            )

        if quarterly_revenue_growth is not None:
            growth_trend = "growing" if quarterly_revenue_growth > 0 else "declining"
            key_metrics.append(
                f"Q Revenue Growth YoY: {quarterly_revenue_growth:+.1f}% ({growth_trend})"
            )

        # Dividend & Risk Section
        if dividend_yield is not None and dividend_yield > 0:
            div_quality = (
                "high income"
                if dividend_yield > 4
                else "moderate income" if dividend_yield > 2 else "low income"
            )
            key_metrics.append(f"Dividend Yield: {dividend_yield:.2f}% ({div_quality})")
            if dividend_yield > 4:
                summary += "High dividend yield suggests income focus. "

        if beta is not None:
            volatility = "high" if beta > 1.5 else "moderate" if beta > 0.5 else "low"
            key_metrics.append(f"Beta: {beta:.2f} ({volatility} volatility)")

        # Analyst Target
        if analyst_target_price is not None and analyst_target_price > 0:
            upside_pct = (analyst_target_price - current_price) / current_price * 100
            upside_dir = "upside" if upside_pct > 0 else "downside"
            key_metrics.append(
                f"Analyst Target: ${analyst_target_price:.2f} ({upside_pct:+.1f}% {upside_dir})"
            )

        result = StockFundamentalsResponse(
            symbol=symbol,
            company_name=company_name,
            analysis_date=datetime.now(UTC).isoformat(),
            current_price=current_price,
            price_change=0.0,  # Not available from Alpha Vantage OVERVIEW
            price_change_percent=0.0,
            volume=0,  # Not available from Alpha Vantage OVERVIEW
            avg_volume=0,
            market_cap=market_cap,
            pe_ratio=pe_ratio,
            pb_ratio=pb_ratio,
            dividend_yield=dividend_yield,
            beta=beta,
            fifty_two_week_high=fifty_two_week_high,
            fifty_two_week_low=fifty_two_week_low,
            fundamental_summary=summary,
            key_metrics=key_metrics,
        )

        # Cache for 4 hours - Fundamentals change quarterly (earnings), only price updates intraday
        # Date-based cache key ensures fresh daily data
        await redis_cache.set(cache_key, result.model_dump(), ttl_seconds=14400)

        logger.info("Fundamentals analysis completed", symbol=symbol)
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid symbol: {str(e)}") from e
    except Exception as e:
        logger.error(
            "Fundamentals analysis failed", symbol=request.symbol, error=str(e)
        )
        raise HTTPException(
            status_code=500, detail=f"Fundamentals analysis failed: {str(e)}"
        ) from e


@router.post("/company-overview", response_model=CompanyOverviewResponse)
async def company_overview(
    request: StockFundamentalsRequest,
    user_id: str = Depends(get_current_user_id),
    redis_cache: RedisCache = Depends(get_redis),
    market_service: AlphaVantageMarketDataService = Depends(get_market_service),
) -> CompanyOverviewResponse:
    """
    Get comprehensive company overview with key metrics and ownership data.

    Uses Alpha Vantage COMPANY_OVERVIEW for company information.
    Returns formatted overview with description, metrics, and ownership percentages.
    """
    try:
        # Check cache first
        from datetime import UTC, datetime

        current_date = datetime.now(UTC).strftime("%Y-%m-%d")
        cache_key = f"company_overview:{request.symbol}:{current_date}"
        cached_result = await redis_cache.get(cache_key)
        if cached_result:
            return CompanyOverviewResponse.model_validate(cached_result)

        logger.info(
            "Fetching company overview from Alpha Vantage", symbol=request.symbol
        )

        # Get company overview from Alpha Vantage
        overview = await market_service.get_company_overview(request.symbol)

        if not overview or "Symbol" not in overview:
            raise ValueError(
                f"'{request.symbol}' is not a valid stock symbol or no data available. "
                "Please check the symbol and try again."
            )

        # Helper function for safe float conversion
        def safe_float(value, default=None):
            try:
                return float(value) if value and value != "None" else default
            except (ValueError, TypeError):
                return default

        # Extract company info
        symbol = overview.get("Symbol", request.symbol)
        company_name = overview.get("Name", symbol)
        description = overview.get("Description", "N/A")
        industry = overview.get("Industry", "N/A")
        sector = overview.get("Sector", "N/A")
        exchange = overview.get("Exchange", "N/A")
        country = overview.get("Country", "N/A")

        # Extract key metrics
        market_cap = safe_float(overview.get("MarketCapitalization"))
        pe_ratio = safe_float(overview.get("PERatio"))
        eps = safe_float(overview.get("EPS"))
        profit_margin_decimal = safe_float(overview.get("ProfitMargin"))
        profit_margin = profit_margin_decimal * 100 if profit_margin_decimal else None
        revenue_ttm = safe_float(overview.get("RevenueTTM"))
        dividend_yield_decimal = safe_float(overview.get("DividendYield"))
        dividend_yield = (
            dividend_yield_decimal * 100 if dividend_yield_decimal else None
        )
        beta = safe_float(overview.get("Beta"))

        # Ownership metrics (Alpha Vantage returns these as percentages already, not decimals)
        percent_insiders = safe_float(overview.get("PercentInsiders"))
        percent_institutions = safe_float(overview.get("PercentInstitutions"))

        # Price metrics
        week_52_high = safe_float(overview.get("52WeekHigh"))
        week_52_low = safe_float(overview.get("52WeekLow"))

        # Build overview summary
        summary = f"{company_name} ({symbol}) operates in the {industry} industry within the {sector} sector. "
        summary += f"Listed on {exchange}. "

        # Build key metrics list
        key_metrics = []

        if market_cap:
            key_metrics.append(f"Market Cap: ${market_cap/1e9:.2f}B")
        if pe_ratio:
            key_metrics.append(f"P/E Ratio: {pe_ratio:.2f}")
        if eps:
            key_metrics.append(f"EPS: ${eps:.2f}")
        if profit_margin:
            key_metrics.append(f"Profit Margin: {profit_margin:.2f}%")
        if revenue_ttm:
            key_metrics.append(f"Revenue (TTM): ${revenue_ttm/1e9:.2f}B")
        if dividend_yield:
            key_metrics.append(f"Dividend Yield: {dividend_yield:.2f}%")
        if beta:
            key_metrics.append(f"Beta: {beta:.2f}")
        if percent_insiders:
            key_metrics.append(f"% Insiders: {percent_insiders:.2f}%")
        if percent_institutions:
            key_metrics.append(f"% Institutions: {percent_institutions:.2f}%")
        if week_52_high:
            key_metrics.append(f"52W High: ${week_52_high:.2f}")
        if week_52_low:
            key_metrics.append(f"52W Low: ${week_52_low:.2f}")

        result = CompanyOverviewResponse(
            symbol=symbol,
            company_name=company_name,
            description=description,
            industry=industry,
            sector=sector,
            exchange=exchange,
            country=country,
            market_cap=market_cap,
            pe_ratio=pe_ratio,
            eps=eps,
            profit_margin=profit_margin,
            revenue_ttm=revenue_ttm,
            dividend_yield=dividend_yield,
            beta=beta,
            percent_insiders=percent_insiders,
            percent_institutions=percent_institutions,
            week_52_high=week_52_high,
            week_52_low=week_52_low,
            overview_summary=summary,
            key_metrics=key_metrics,
        )

        # Cache for 4 hours - Company info rarely changes
        await redis_cache.set(cache_key, result.model_dump(), ttl_seconds=14400)

        logger.info(
            "Company overview completed", symbol=symbol, company_name=company_name
        )
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid symbol: {str(e)}") from e
    except Exception as e:
        logger.error("Company overview failed", symbol=request.symbol, error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Company overview failed: {str(e)}"
        ) from e


@router.post("/cash-flow", response_model=CashFlowResponse)
async def cash_flow(
    request: StockFundamentalsRequest,
    user_id: str = Depends(get_current_user_id),
    redis_cache: RedisCache = Depends(get_redis),
    market_service: AlphaVantageMarketDataService = Depends(get_market_service),
) -> CashFlowResponse:
    """Get cash flow statement for a company."""
    try:
        from datetime import UTC, datetime

        current_date = datetime.now(UTC).strftime("%Y-%m-%d")
        cache_key = f"cash_flow:{request.symbol}:{current_date}"
        cached_result = await redis_cache.get(cache_key)
        if cached_result:
            return CashFlowResponse.model_validate(cached_result)

        logger.info("Fetching cash flow from Alpha Vantage", symbol=request.symbol)

        data = await market_service.get_cash_flow(request.symbol)
        annual = data.get("annualReports", [])

        if not annual:
            raise ValueError(f"No cash flow data available for {request.symbol}")

        latest = annual[0]
        company_name = data.get("symbol", request.symbol)

        def safe_float(value, default=None):
            try:
                return float(value) if value and value != "None" else default
            except (ValueError, TypeError):
                return default

        operating_cf = safe_float(latest.get("operatingCashflow"))
        capex = safe_float(latest.get("capitalExpenditures"))
        free_cf = (operating_cf - abs(capex)) if operating_cf and capex else None
        dividend = safe_float(latest.get("dividendPayout"))

        summary = f"Latest annual cash flow for {company_name} ({latest.get('fiscalDateEnding')}). "
        if operating_cf:
            summary += f"Operating cash flow: ${operating_cf/1e6:.1f}M. "
        if free_cf:
            summary += f"Free cash flow: ${free_cf/1e6:.1f}M. "

        result = CashFlowResponse(
            symbol=request.symbol,
            company_name=company_name,
            fiscal_date_ending=latest.get("fiscalDateEnding", "N/A"),
            operating_cashflow=operating_cf,
            capital_expenditures=capex,
            free_cashflow=free_cf,
            dividend_payout=dividend,
            cashflow_summary=summary,
        )

        await redis_cache.set(cache_key, result.model_dump(), ttl_seconds=14400)
        logger.info("Cash flow completed", symbol=request.symbol)
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid symbol: {str(e)}") from e
    except Exception as e:
        logger.error("Cash flow failed", symbol=request.symbol, error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Cash flow failed: {str(e)}"
        ) from e


@router.post("/balance-sheet", response_model=BalanceSheetResponse)
async def balance_sheet(
    request: StockFundamentalsRequest,
    user_id: str = Depends(get_current_user_id),
    redis_cache: RedisCache = Depends(get_redis),
    market_service: AlphaVantageMarketDataService = Depends(get_market_service),
) -> BalanceSheetResponse:
    """Get balance sheet for a company."""
    try:
        from datetime import UTC, datetime

        current_date = datetime.now(UTC).strftime("%Y-%m-%d")
        cache_key = f"balance_sheet:{request.symbol}:{current_date}"
        cached_result = await redis_cache.get(cache_key)
        if cached_result:
            return BalanceSheetResponse.model_validate(cached_result)

        logger.info("Fetching balance sheet from Alpha Vantage", symbol=request.symbol)

        data = await market_service.get_balance_sheet(request.symbol)
        annual = data.get("annualReports", [])

        if not annual:
            raise ValueError(f"No balance sheet data available for {request.symbol}")

        latest = annual[0]
        company_name = data.get("symbol", request.symbol)

        def safe_float(value, default=None):
            try:
                return float(value) if value and value != "None" else default
            except (ValueError, TypeError):
                return default

        total_assets = safe_float(latest.get("totalAssets"))
        total_liabilities = safe_float(latest.get("totalLiabilities"))
        equity = safe_float(latest.get("totalShareholderEquity"))
        current_assets = safe_float(latest.get("currentAssets"))
        current_liabilities = safe_float(latest.get("currentLiabilities"))
        cash = safe_float(latest.get("cashAndCashEquivalentsAtCarryingValue"))

        summary = f"Latest annual balance sheet for {company_name} ({latest.get('fiscalDateEnding')}). "
        if total_assets:
            summary += f"Total assets: ${total_assets/1e6:.1f}M. "
        if equity:
            summary += f"Shareholder equity: ${equity/1e6:.1f}M. "

        result = BalanceSheetResponse(
            symbol=request.symbol,
            company_name=company_name,
            fiscal_date_ending=latest.get("fiscalDateEnding", "N/A"),
            total_assets=total_assets,
            total_liabilities=total_liabilities,
            total_shareholder_equity=equity,
            current_assets=current_assets,
            current_liabilities=current_liabilities,
            cash_and_equivalents=cash,
            balance_sheet_summary=summary,
        )

        await redis_cache.set(cache_key, result.model_dump(), ttl_seconds=14400)
        logger.info("Balance sheet completed", symbol=request.symbol)
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid symbol: {str(e)}") from e
    except Exception as e:
        logger.error("Balance sheet failed", symbol=request.symbol, error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Balance sheet failed: {str(e)}"
        ) from e


@router.post("/news-sentiment", response_model=NewsSentimentResponse)
async def news_sentiment(
    request: StockFundamentalsRequest,
    user_id: str = Depends(get_current_user_id),
    redis_cache: RedisCache = Depends(get_redis),
    market_service: AlphaVantageMarketDataService = Depends(get_market_service),
) -> NewsSentimentResponse:
    """Get news sentiment for a stock."""
    try:
        from datetime import UTC, datetime

        current_date = datetime.now(UTC).strftime("%Y-%m-%d")
        cache_key = f"news_sentiment:{request.symbol}:{current_date}"
        cached_result = await redis_cache.get(cache_key)
        if cached_result:
            return NewsSentimentResponse.model_validate(cached_result)

        logger.info("Fetching news sentiment from Alpha Vantage", symbol=request.symbol)

        data = await market_service.get_news_sentiment(
            tickers=request.symbol, limit=50, sort="LATEST"
        )
        feed = data.get("feed", [])

        if not feed:
            raise ValueError(f"No news available for {request.symbol}")

        # Filter by sentiment
        positive = [
            NewsArticle(
                title=item["title"],
                url=item["url"],
                source=item.get("source", "Unknown"),
                sentiment_score=item["overall_sentiment_score"],
                sentiment_label="Bullish",
            )
            for item in feed
            if item.get("overall_sentiment_score", 0) > 0.15
        ][:3]

        negative = [
            NewsArticle(
                title=item["title"],
                url=item["url"],
                source=item.get("source", "Unknown"),
                sentiment_score=item["overall_sentiment_score"],
                sentiment_label="Bearish",
            )
            for item in feed
            if item.get("overall_sentiment_score", 0) < -0.15
        ][:3]

        overall = f"Found {len(positive)} positive and {len(negative)} negative articles for {request.symbol}"

        result = NewsSentimentResponse(
            symbol=request.symbol,
            positive_news=positive,
            negative_news=negative,
            overall_sentiment=overall,
        )

        await redis_cache.set(
            cache_key, result.model_dump(), ttl_seconds=3600
        )  # 1 hour
        logger.info("News sentiment completed", symbol=request.symbol)
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid symbol: {str(e)}") from e
    except Exception as e:
        logger.error("News sentiment failed", symbol=request.symbol, error=str(e))
        raise HTTPException(
            status_code=500, detail=f"News sentiment failed: {str(e)}"
        ) from e


@router.get("/market-movers", response_model=MarketMoversResponse)
async def market_movers(
    user_id: str = Depends(get_current_user_id),
    redis_cache: RedisCache = Depends(get_redis),
    market_service: AlphaVantageMarketDataService = Depends(get_market_service),
) -> MarketMoversResponse:
    """Get today's market movers (gainers, losers, most active)."""
    try:
        from datetime import UTC, datetime

        current_date = datetime.now(UTC).strftime("%Y-%m-%d")
        cache_key = f"market_movers:{current_date}"
        cached_result = await redis_cache.get(cache_key)
        if cached_result:
            return MarketMoversResponse.model_validate(cached_result)

        logger.info("Fetching market movers from Alpha Vantage")

        data = await market_service.get_top_gainers_losers()

        gainers = [
            MarketMover(
                ticker=item["ticker"],
                price=float(item["price"]),
                change_amount=float(item["change_amount"]),
                change_percentage=item["change_percentage"],
                volume=int(item["volume"]),
            )
            for item in data.get("top_gainers", [])[:5]
        ]

        losers = [
            MarketMover(
                ticker=item["ticker"],
                price=float(item["price"]),
                change_amount=float(item["change_amount"]),
                change_percentage=item["change_percentage"],
                volume=int(item["volume"]),
            )
            for item in data.get("top_losers", [])[:5]
        ]

        active = [
            MarketMover(
                ticker=item["ticker"],
                price=float(item["price"]),
                change_amount=float(item["change_amount"]),
                change_percentage=item["change_percentage"],
                volume=int(item["volume"]),
            )
            for item in data.get("most_actively_traded", [])[:5]
        ]

        result = MarketMoversResponse(
            top_gainers=gainers,
            top_losers=losers,
            most_active=active,
            last_updated=datetime.now(UTC).isoformat(),
        )

        await redis_cache.set(
            cache_key, result.model_dump(), ttl_seconds=3600
        )  # 1 hour
        logger.info("Market movers completed")
        return result

    except Exception as e:
        logger.error("Market movers failed", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Market movers failed: {str(e)}"
        ) from e


@router.post("/stochastic", response_model=StochasticAnalysisResponse)
async def stochastic_analysis(
    request: StochasticAnalysisRequest,
    user_id: str = Depends(get_current_user_id),
    redis_cache: RedisCache = Depends(get_redis),
    market_service: AlphaVantageMarketDataService = Depends(get_market_service),
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
        d_period=request.d_period,
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
            symbol=request.symbol,
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
                total_duration_ms=round(total_duration * 1000, 2),
            )
            return StochasticAnalysisResponse.model_validate(cached_result)

        logger.info(
            "Stochastic analysis cache MISS - proceeding with calculation",
            symbol=request.symbol,
            cache_key=cache_key,
            cache_check_duration_ms=round(cache_check_duration * 1000, 2),
        )

        # Perform analysis
        analysis_start_time = time.time()
        logger.info(
            "Starting Stochastic analysis calculation",
            symbol=request.symbol,
            timeframe=request.timeframe,
            k_period=request.k_period,
            d_period=request.d_period,
        )

        # Initialize TickerDataService and analyzer with AlphaVantage
        from ..core.data.ticker_data_service import TickerDataService

        ticker_service = TickerDataService(
            redis_cache=redis_cache, alpha_vantage_service=market_service
        )
        analyzer = StochasticAnalyzer(ticker_service)

        result = await analyzer.analyze(
            symbol=request.symbol,
            start_date=request.start_date,
            end_date=request.end_date,
            timeframe=request.timeframe,
            k_period=request.k_period,
            d_period=request.d_period,
        )

        analysis_duration = time.time() - analysis_start_time
        logger.info(
            "Stochastic analysis calculation completed",
            symbol=result.symbol,
            timeframe=result.timeframe,
            current_signal=result.current_signal,
            k_value=result.current_k,
            d_value=result.current_d,
            analysis_duration_ms=round(analysis_duration * 1000, 2),
        )

        # Cache for 1 hour - Stochastic oscillator values stable for daily analysis
        # Date-based cache key ensures data refreshes daily
        cache_store_start_time = time.time()
        await redis_cache.set(cache_key, result.model_dump(), ttl_seconds=3600)
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
            total_duration_ms=round(total_duration * 1000, 2),
        )

        return result

    except ValueError as e:
        total_duration = time.time() - request_start_time
        logger.error(
            "Stochastic analysis request failed - invalid input",
            symbol=request.symbol,
            error=str(e),
            total_duration_ms=round(total_duration * 1000, 2),
        )
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}") from e
    except Exception as e:
        total_duration = time.time() - request_start_time
        logger.error(
            "Stochastic analysis request failed - unexpected error",
            symbol=request.symbol,
            error=str(e),
            error_type=type(e).__name__,
            total_duration_ms=round(total_duration * 1000, 2),
        )
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}") from e


@router.post("/chart", response_model=ChartGenerationResponse)
async def generate_chart(
    request: ChartRequest,
    user_id: str = Depends(get_current_user_id),
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
        generation_date = datetime.now().isoformat()
        chart_data: dict[str, Any] = {
            "symbol": request.symbol,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "chart_type": request.chart_type,
            "includes_indicators": request.include_indicators,
            "data_points": [],  # Will be populated with actual chart data
            "generated_at": generation_date,
        }

        result = ChartGenerationResponse(
            symbol=request.symbol,
            chart_type=request.chart_type,
            chart_url=None,  # Will be set when image generation is implemented
            chart_data=chart_data,
            generation_date=generation_date,
            success=True,
            error_message=None,
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


@router.get("/history")
async def get_analysis_history(
    symbol: str | None = None,
    analysis_id: str | None = None,
    limit: int = 100,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """
    Get analysis history messages.

    Query parameters:
    - symbol: Filter by stock symbol (e.g., AAPL)
    - analysis_id: Filter by specific analysis workflow ID
    - limit: Maximum number of messages to return (default: 100)

    Returns analysis messages from the message collection grouped by analysis_id.
    Used for portfolio chart markers and analysis timeline.
    """
    try:
        from ..database.repositories.message_repository import MessageRepository

        # Get MongoDB connection
        from .health import get_mongodb

        mongodb = await get_mongodb()
        messages_collection = mongodb.get_collection("messages")
        message_repo = MessageRepository(messages_collection)

        # Query analysis messages
        messages = await message_repo.get_analysis_messages(
            symbol=symbol,
            analysis_id=analysis_id,
            limit=limit,
        )

        # Group by analysis_id
        analysis_sessions: dict[str, list] = {}
        for msg in messages:
            aid = msg.metadata.analysis_id or "unknown"
            if aid not in analysis_sessions:
                analysis_sessions[aid] = []

            analysis_sessions[aid].append(
                {
                    "message_id": msg.message_id,
                    "timestamp": msg.timestamp.isoformat(),
                    "symbol": msg.metadata.symbol,
                    "content": msg.content[:200],  # Truncate for summary
                    "selected_tool": msg.metadata.selected_tool,
                    "confidence_score": msg.metadata.confidence_score,
                    "trend_direction": msg.metadata.trend_direction,
                }
            )

        logger.info(
            "Analysis history queried",
            symbol=symbol,
            analysis_id=analysis_id,
            message_count=len(messages),
            session_count=len(analysis_sessions),
        )

        return {
            "symbol": symbol,
            "analysis_id": analysis_id,
            "total_messages": len(messages),
            "analysis_sessions": analysis_sessions,
        }

    except Exception as e:
        logger.error(
            "Failed to get analysis history",
            symbol=symbol,
            analysis_id=analysis_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to get analysis history: {str(e)}"
        ) from e
