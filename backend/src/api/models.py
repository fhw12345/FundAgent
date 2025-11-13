"""
Pydantic models for Financial Analysis API responses.
Designed to be easily consumable by both frontend and future LangChain agents.
"""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# Base models for common structures
class PricePoint(BaseModel):
    """Price point with date and value."""

    price: float = Field(..., description="Price value")
    date: str = Field(..., description="Date in YYYY-MM-DD format")


class FibonacciLevel(BaseModel):
    """Fibonacci retracement level."""

    level: float = Field(..., ge=0, description="Fibonacci ratio (e.g., 0.618)")
    price: float = Field(..., description="Price at this level")
    percentage: str = Field(..., description="Percentage string (e.g., '61.8%')")
    is_key_level: bool = Field(
        default=False, description="Whether this is a key level (38.2%, 50%, 61.8%)"
    )


class MarketStructure(BaseModel):
    """Market structure analysis results."""

    trend_direction: Literal["uptrend", "downtrend", "sideways"] = Field(
        ..., description="Overall trend direction"
    )
    swing_high: PricePoint = Field(
        ..., description="Most recent significant swing high"
    )
    swing_low: PricePoint = Field(..., description="Most recent significant swing low")
    structure_quality: Literal["high", "medium", "low"] = Field(
        ..., description="Quality of market structure"
    )
    phase: str = Field(..., description="Current market phase description")


# Main analysis response models
class FibonacciAnalysisResponse(BaseModel):
    """Complete Fibonacci analysis response."""

    symbol: str = Field(..., description="Stock symbol analyzed")
    start_date: str | None = Field(None, description="Analysis start date (YYYY-MM-DD)")
    end_date: str | None = Field(None, description="Analysis end date (YYYY-MM-DD)")
    timeframe: str = Field(..., description="Analysis timeframe (1d, 1w, 1M)")
    current_price: float = Field(..., description="Current stock price")
    analysis_date: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="Analysis date in ISO format",
    )

    # Core Fibonacci data
    fibonacci_levels: list[FibonacciLevel] = Field(
        ..., description="All Fibonacci retracement levels"
    )
    market_structure: MarketStructure = Field(
        ..., description="Market structure analysis"
    )

    # Analysis insights
    confidence_score: float = Field(
        ..., ge=0, le=1, description="Analysis confidence (0-1)"
    )
    pressure_zone: dict[str, float] | None = Field(
        None, description="Key pressure zone around 61.8%"
    )
    trend_strength: str = Field(..., description="Trend strength assessment")

    # Educational context
    analysis_summary: str = Field(..., description="Human-readable analysis summary")
    key_insights: list[str] = Field(
        ..., description="List of key insights from the analysis"
    )

    # Metadata for agent use
    raw_data: dict[str, Any] = Field(
        ..., description="Raw calculation data for debugging"
    )


class MacroSentimentResponse(BaseModel):
    """Macro market sentiment analysis response."""

    analysis_date: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="Analysis date in ISO format",
    )

    # VIX analysis
    vix_level: float = Field(..., description="Current VIX level")
    vix_interpretation: str = Field(
        ..., description="VIX interpretation (fearful/neutral/greedy)"
    )
    fear_greed_score: int = Field(
        ...,
        ge=0,
        le=100,
        description="Fear/Greed score (0=extreme fear, 100=extreme greed)",
    )

    # Market indices
    major_indices: dict[str, float] = Field(
        ..., description="Major market index performance"
    )
    sector_performance: dict[str, float] = Field(
        ..., description="Sector ETF performance"
    )

    # Overall assessment
    market_sentiment: Literal["fearful", "neutral", "greedy"] = Field(
        ..., description="Overall market sentiment"
    )
    confidence_level: float = Field(
        ..., ge=0, le=1, description="Sentiment analysis confidence"
    )
    sentiment_summary: str = Field(..., description="Human-readable sentiment summary")

    # Recommendations
    market_outlook: str = Field(..., description="Short-term market outlook")
    key_factors: list[str] = Field(..., description="Key factors influencing sentiment")


class StockFundamentalsResponse(BaseModel):
    """Stock fundamentals and company information."""

    symbol: str = Field(..., description="Stock symbol")
    company_name: str = Field(..., description="Company name")
    analysis_date: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="Analysis date in ISO format",
    )

    # Price data
    current_price: float = Field(..., description="Current stock price")
    price_change: float = Field(..., description="Price change from previous day")
    price_change_percent: float = Field(..., description="Price change percentage")

    # Volume and market data
    volume: int = Field(..., description="Current volume")
    avg_volume: int = Field(..., description="Average volume")
    market_cap: float = Field(..., description="Market capitalization")

    # Valuation metrics
    pe_ratio: float | None = Field(None, description="Price-to-earnings ratio")
    pb_ratio: float | None = Field(None, description="Price-to-book ratio")
    dividend_yield: float | None = Field(
        None,
        ge=0,
        le=25,
        description="Dividend yield percentage. We cap at 25% to reject unrealistic data.",
    )

    # Financial health
    beta: float | None = Field(None, description="Stock beta (volatility vs market)")
    fifty_two_week_high: float = Field(..., description="52-week high price")
    fifty_two_week_low: float = Field(..., description="52-week low price")

    # Summary
    fundamental_summary: str = Field(..., description="Summary of fundamental analysis")
    key_metrics: list[str] = Field(
        ..., description="Key fundamental metrics highlighted"
    )


class CompanyOverviewResponse(BaseModel):
    """Company overview with key metrics and ownership data."""

    symbol: str = Field(..., description="Stock symbol")
    company_name: str = Field(..., description="Company name")
    description: str = Field(..., description="Company business description")
    industry: str = Field(..., description="Industry")
    sector: str = Field(..., description="Sector")
    exchange: str = Field(..., description="Exchange where stock is listed")
    country: str = Field(..., description="Country of incorporation")

    # Key metrics
    market_cap: float | None = Field(None, description="Market capitalization")
    pe_ratio: float | None = Field(None, description="Price-to-earnings ratio")
    eps: float | None = Field(None, description="Earnings per share")
    profit_margin: float | None = Field(None, description="Profit margin percentage")
    revenue_ttm: float | None = Field(None, description="Revenue trailing twelve months")
    dividend_yield: float | None = Field(None, description="Dividend yield percentage")
    beta: float | None = Field(None, description="Stock beta")

    # Ownership
    percent_insiders: float | None = Field(None, description="Percent held by insiders")
    percent_institutions: float | None = Field(None, description="Percent held by institutions")

    # Price metrics
    week_52_high: float | None = Field(None, description="52-week high")
    week_52_low: float | None = Field(None, description="52-week low")

    # Formatted summary
    overview_summary: str = Field(..., description="Formatted company overview summary")
    key_metrics: list[str] = Field(..., description="Key metrics highlighted")


class CashFlowResponse(BaseModel):
    """Cash flow statement response."""

    symbol: str = Field(..., description="Stock symbol")
    company_name: str = Field(..., description="Company name")
    fiscal_date_ending: str = Field(..., description="Fiscal date ending")
    operating_cashflow: float | None = Field(None, description="Operating cash flow")
    capital_expenditures: float | None = Field(None, description="Capital expenditures")
    free_cashflow: float | None = Field(None, description="Free cash flow")
    dividend_payout: float | None = Field(None, description="Dividend payout")
    cashflow_summary: str = Field(..., description="Cash flow summary")


class BalanceSheetResponse(BaseModel):
    """Balance sheet response."""

    symbol: str = Field(..., description="Stock symbol")
    company_name: str = Field(..., description="Company name")
    fiscal_date_ending: str = Field(..., description="Fiscal date ending")
    total_assets: float | None = Field(None, description="Total assets")
    total_liabilities: float | None = Field(None, description="Total liabilities")
    total_shareholder_equity: float | None = Field(None, description="Total shareholder equity")
    current_assets: float | None = Field(None, description="Current assets")
    current_liabilities: float | None = Field(None, description="Current liabilities")
    cash_and_equivalents: float | None = Field(None, description="Cash and cash equivalents")
    balance_sheet_summary: str = Field(..., description="Balance sheet summary")


class NewsArticle(BaseModel):
    """Single news article with sentiment."""

    title: str = Field(..., description="Article title")
    url: str = Field(..., description="Article URL")
    source: str = Field(..., description="News source")
    sentiment_score: float = Field(..., description="Sentiment score (-1 to 1)")
    sentiment_label: str = Field(..., description="Sentiment label (Bullish/Bearish/Neutral)")


class NewsSentimentResponse(BaseModel):
    """News sentiment response."""

    symbol: str = Field(..., description="Stock symbol")
    positive_news: list[NewsArticle] = Field(..., description="Positive sentiment news")
    negative_news: list[NewsArticle] = Field(..., description="Negative sentiment news")
    overall_sentiment: str = Field(..., description="Overall sentiment summary")


class MarketMover(BaseModel):
    """Single market mover entry."""

    ticker: str = Field(..., description="Stock ticker")
    price: float = Field(..., description="Current price")
    change_amount: float = Field(..., description="Change amount")
    change_percentage: str = Field(..., description="Change percentage")
    volume: int = Field(..., description="Trading volume")


class MarketMoversResponse(BaseModel):
    """Market movers response."""

    top_gainers: list[MarketMover] = Field(..., description="Top gaining stocks")
    top_losers: list[MarketMover] = Field(..., description="Top losing stocks")
    most_active: list[MarketMover] = Field(..., description="Most actively traded stocks")
    last_updated: str = Field(..., description="Last updated timestamp")


class ChartGenerationResponse(BaseModel):
    """Chart generation response."""

    symbol: str = Field(..., description="Stock symbol for the chart")
    chart_type: str = Field(..., description="Type of chart generated")
    chart_url: str | None = Field(None, description="URL to the generated chart image")
    chart_data: dict[str, Any] = Field(
        ..., description="Chart data for frontend rendering"
    )
    generation_date: str = Field(..., description="Chart generation date")
    success: bool = Field(..., description="Whether chart generation was successful")
    error_message: str | None = Field(
        None, description="Error message if generation failed"
    )


class StochasticLevel(BaseModel):
    """Stochastic oscillator level reading."""

    timestamp: str = Field(..., description="Timestamp for this reading")
    k_percent: float = Field(..., ge=0, le=100, description="%K line value")
    d_percent: float = Field(..., ge=0, le=100, description="%D line value")
    signal: Literal["overbought", "oversold", "neutral"] = Field(
        ..., description="Signal interpretation"
    )


class StochasticAnalysisResponse(BaseModel):
    """Complete stochastic oscillator analysis response."""

    symbol: str = Field(..., description="Stock symbol analyzed")
    start_date: str | None = Field(None, description="Analysis start date (YYYY-MM-DD)")
    end_date: str | None = Field(None, description="Analysis end date (YYYY-MM-DD)")
    timeframe: str = Field(..., description="Analysis timeframe (1h, 1d, 1w, 1M)")
    current_price: float = Field(..., description="Current stock price")
    analysis_date: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="Analysis date in ISO format",
    )

    # Stochastic parameters
    k_period: int = Field(..., description="K% period used")
    d_period: int = Field(..., description="D% period used")

    # Current readings
    current_k: float = Field(..., ge=0, le=100, description="Current %K value")
    current_d: float = Field(..., ge=0, le=100, description="Current %D value")
    current_signal: Literal["overbought", "oversold", "neutral"] = Field(
        ..., description="Current signal interpretation"
    )

    # Analysis results
    stochastic_levels: list[StochasticLevel] = Field(
        ..., description="Historical stochastic levels"
    )
    signal_changes: list[dict[str, Any]] = Field(
        ..., description="Signal change events (crossovers)"
    )

    # Insights
    analysis_summary: str = Field(..., description="Human-readable analysis summary")
    key_insights: list[str] = Field(
        ..., description="List of key insights from the analysis"
    )

    # Metadata for debugging and advanced features
    raw_data: dict[str, Any] = Field(
        ..., description="Raw calculation data for debugging"
    )


# Request models
class FibonacciAnalysisRequest(BaseModel):
    """Request model for Fibonacci analysis."""

    symbol: str = Field(..., description="Stock symbol to analyze")
    start_date: str | None = Field(default=None, description="Start date (YYYY-MM-DD)")
    end_date: str | None = Field(default=None, description="End date (YYYY-MM-DD)")
    timeframe: Literal["1h", "1d", "1w", "1mo", "1M"] = Field(
        default="1d", description="Analysis timeframe (1h, 1d, 1w, 1mo)"
    )
    include_chart: bool = Field(default=True, description="Whether to generate a chart")


class MacroAnalysisRequest(BaseModel):
    """Request model for macro analysis."""

    include_sectors: bool = Field(
        default=True, description="Include sector rotation analysis"
    )
    include_indices: bool = Field(
        default=True, description="Include major indices analysis"
    )


class StockFundamentalsRequest(BaseModel):
    """Request model for stock fundamentals."""

    symbol: str = Field(
        ...,
        min_length=1,
        pattern=r"^\S+$",
        description="Stock symbol to analyze",
    )


class ChartRequest(BaseModel):
    """Request model for chart generation."""

    symbol: str = Field(..., description="Stock symbol for chart")
    start_date: str | None = Field(default=None, description="Start date (YYYY-MM-DD)")
    end_date: str | None = Field(default=None, description="End date (YYYY-MM-DD)")
    chart_type: Literal["price", "fibonacci", "volume"] = Field(
        default="fibonacci", description="Type of chart to generate"
    )
    include_indicators: bool = Field(
        default=True, description="Include technical indicators"
    )


class StochasticAnalysisRequest(BaseModel):
    """Request model for stochastic oscillator analysis."""

    symbol: str = Field(
        ...,
        min_length=1,
        pattern=r"^\S+$",
        description="Stock symbol to analyze",
    )
    start_date: str | None = Field(default=None, description="Start date (YYYY-MM-DD)")
    end_date: str | None = Field(default=None, description="End date (YYYY-MM-DD)")
    timeframe: Literal["1h", "1d", "1w", "1mo", "1M"] = Field(
        default="1d", description="Analysis timeframe (1h, 1d, 1w, 1mo)"
    )
    k_period: int = Field(
        default=14,
        ge=5,
        le=50,
        description="K% period for stochastic calculation",
    )
    d_period: int = Field(
        default=3,
        ge=2,
        le=20,
        description="D% period for signal line smoothing",
    )


# Tool invocation metadata for UI rendering
class ToolCall(BaseModel):
    """
    Tool invocation metadata for collapsible UI wrapper.

    Used by both button-triggered analysis and agent-invoked tools
    to provide consistent UI rendering with title, icon, and metadata.
    """

    tool_name: str = Field(
        ...,
        description="Tool identifier (e.g., 'company_overview', 'fibonacci')",
    )
    title: str = Field(
        ..., description="Display title for UI (e.g., 'Company Overview')"
    )
    icon: str = Field(..., description="Emoji icon for tool (e.g., '🏢')")
    symbol: str | None = Field(
        None, description="Stock symbol if applicable (e.g., 'TSLA')"
    )
    invoked_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="ISO timestamp of tool invocation",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional tool-specific data"
    )
